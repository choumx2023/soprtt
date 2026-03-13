# core/analyzer.py

from collections import defaultdict
import json
import ipaddress
from utils.time_utils import epoch_to_utc8


class MLTAnalyzer:
    def __init__(self, samples, window_size=1.0, focus_subnet=None, debug=False):
        self.samples = samples
        self.window_size = window_size
        self.focus_subnet = focus_subnet
        self.debug = debug
        self.windows = defaultdict(list)

        if self.debug:
            print("MLTAnalyzer initialized, sample count:", len(self.samples))

    # --------------------------------------------------
    # Utility
    # --------------------------------------------------

    def _upgrade_status(self, current, new):
        priority = {
            "NORMAL": 0,
            "WARNING": 1,
            "CRITICAL": 2,
        }
        return new if priority[new] > priority[current] else current

    def _safe_ip_in_subnet(self, ip_str, network):
        try:
            return ipaddress.ip_address(ip_str) in network
        except Exception:
            return False

    def _percentile_baseline(self, values, ratio=0.05):
        """
        用较低分位近似 baseline，避免单个极小值导致误报。
        """
        if not values:
            return None

        values = sorted(values)
        idx = int(len(values) * ratio)

        if idx >= len(values):
            idx = len(values) - 1

        return values[idx]

    def merge_ranges_smart(
        self,
        ranges,
        max_gap_windows=5,      # 超过这个就绝不合并
        min_side_windows=3,
        tiny_island_windows=2,
    ):
        """
        智能合并异常区间。

        规则：
        1. gap > max_gap_windows，绝不合并
        2. 强合并：gap 足够短，且两侧区间都足够长 -> 可反复合并
        3. 弱合并：如果只有一侧足够长，允许合并一次
        4. 短异常岛：如果中间是很短的小异常岛，也允许合并一次
        """
        if not ranges:
            return []

        ranges = sorted(ranges)
        merged = []
        i = 0

        while i < len(ranges):
            cur_start, cur_end = ranges[i]
            used_soft_merge = False

            while i + 1 < len(ranges):
                next_start, next_end = ranges[i + 1]

                cur_len = cur_end - cur_start + 1
                next_len = next_end - next_start + 1
                gap = next_start - cur_end - 1

                # -----------------------------
                # 硬限制：gap 过长，直接不能并
                # -----------------------------
                if gap > max_gap_windows:
                    break

                # -----------------------------
                # 规则1：强合并（两边都长）
                # 可连续触发
                # -----------------------------
                if cur_len >= min_side_windows and next_len >= min_side_windows:
                    cur_end = next_end
                    i += 1
                    continue

                # -----------------------------
                # 规则2：弱合并（只允许一次）
                # 一边长、一边短
                # -----------------------------
                if (
                    not used_soft_merge
                    and (
                        (cur_len >= min_side_windows and next_len <= tiny_island_windows)
                        or
                        (next_len >= min_side_windows and cur_len <= tiny_island_windows)
                    )
                ):
                    cur_end = next_end
                    used_soft_merge = True
                    i += 1
                    continue

                # -----------------------------
                # 规则3：中间短异常岛
                # A - gap - 小岛 - gap - C
                # 也只允许一次
                # -----------------------------
                if not used_soft_merge and i + 2 < len(ranges):
                    island_start, island_end = ranges[i + 1]
                    third_start, third_end = ranges[i + 2]

                    island_len = island_end - island_start + 1
                    third_len = third_end - third_start + 1

                    gap1 = island_start - cur_end - 1
                    gap2 = third_start - island_end - 1

                    # 任一 gap 超过 max_gap_windows，直接不能并
                    if (
                        gap1 <= max_gap_windows
                        and gap2 <= max_gap_windows
                        and island_len <= tiny_island_windows
                        and (
                            cur_len >= min_side_windows
                            or third_len >= min_side_windows
                        )
                    ):
                        cur_end = third_end
                        used_soft_merge = True
                        i += 2
                        continue
                break

            merged.append((cur_start, cur_end))
            i += 1

        return merged

    def merge_consecutive_windows(self, windows):
        """
        把连续窗口合并成区间。
        例如 [10,11,12,15,16,20] -> [(10,12),(15,16),(20,20)]
        """
        if not windows:
            return []

        windows = sorted(set(windows))
        merged = []

        start = windows[0]
        prev = windows[0]

        for w in windows[1:]:
            if w == prev + 1:
                prev = w
            else:
                merged.append((start, prev))
                start = w
                prev = w

        merged.append((start, prev))
        return merged

    # --------------------------------------------------
    # Build time windows
    # --------------------------------------------------

    def build_windows(self, samples=None):
        self.windows.clear()

        target_samples = samples if samples is not None else self.samples

        total_count = 0
        missing_ack_time = 0
        bad_ack_time = 0
        built_count = 0

        for i, s in enumerate(target_samples):
            total_count += 1

            if self.debug and i < 5:
                print("sample preview:", s)

            ack_time = s.get("ack_time", s.get("timestamp"))

            if ack_time is None:
                missing_ack_time += 1
                continue

            try:
                ack_time = float(ack_time)
            except Exception:
                bad_ack_time += 1
                continue

            window = int(ack_time // self.window_size)
            self.windows[window].append(s)
            built_count += 1

        if self.debug:
            print("build_windows total_count:", total_count)
            print("build_windows missing_ack_time:", missing_ack_time)
            print("build_windows bad_ack_time:", bad_ack_time)
            print("build_windows built_count:", built_count)

    # --------------------------------------------------
    # Link delay detection (SYN + B2B)
    # --------------------------------------------------

    def detect_link_delay_spike(self, absolute_threshold=0.15, min_samples=3):
        """
        逻辑：
        1. 优先用 syn / b2b 样本建立 baseline
        2. 如果 syn / b2b 不足，则退化到所有 mlt 样本
        3. 某窗口中只要存在一个样本 mlt - baseline >= threshold，就判该窗口异常
        4. 再把连续异常窗口合并成区间
        """

        link_mlts = [
            s["mlt"]
            for window_samples in self.windows.values()
            for s in window_samples
            if s.get("type") in ("syn", "b2b") and isinstance(s.get("mlt"), (int, float))
        ]

        all_mlts = [
            s["mlt"]
            for window_samples in self.windows.values()
            for s in window_samples
            if isinstance(s.get("mlt"), (int, float))
        ]
        if self.debug:
            print("Total numeric mlt samples:", len(all_mlts))
            print("Syn/B2B mlt samples:", len(link_mlts))

        if len(link_mlts) >= min_samples:
            baseline_values = link_mlts
            candidate_mode = "syn_b2b"
        elif len(all_mlts) >= min_samples:
            baseline_values = all_mlts
            candidate_mode = "all"
        else:
            if self.debug:
                print("Not enough samples for baseline.")
            return {}, [], []

        baseline = self._percentile_baseline(baseline_values, ratio=0.05)
        if self.debug:
            print("Baseline mode:", candidate_mode)
            print("Baseline:", baseline)

        if baseline is None:
            return {}, [], []

        spike_windows = []
        spike_window_details = []

        for w in sorted(self.windows.keys()):
            samples = self.windows[w]

            if candidate_mode == "syn_b2b":
                critical_samples = [
                    s for s in samples
                    if s.get("type") in ("syn", "b2b")
                    and isinstance(s.get("mlt"), (int, float))
                ]
            else:
                critical_samples = [
                    s for s in samples
                    if isinstance(s.get("mlt"), (int, float))
                ]

            abnormal_candidates = [
                s for s in critical_samples
                if s["mlt"] - baseline >= absolute_threshold
            ]

            if not abnormal_candidates:
                continue

            worst = max(abnormal_candidates, key=lambda x: x["mlt"] - baseline)

            spike_windows.append(w)
            spike_window_details.append({
                "window": w,
                "time": epoch_to_utc8(w * self.window_size),
                "mlt": round(worst["mlt"], 6),
                "increase": round(worst["mlt"] - baseline, 6),
                "type": worst.get("type"),
            })

        strict_ranges = self.merge_consecutive_windows(spike_windows)
        merged_ranges = self.merge_ranges_smart(
            strict_ranges,
            max_gap_windows=5,
            min_side_windows=3,
            tiny_island_windows=2,
        )
        merged_spike_periods = []
        for start, end in merged_ranges:
            range_details = [
                x for x in spike_window_details
                if start <= x["window"] <= end
            ]

            merged_spike_periods.append({
                "start_window": start,
                "end_window": end,
                "start_time": epoch_to_utc8(start * self.window_size),
                "end_time": epoch_to_utc8((end + 1) * self.window_size),
                "duration_windows": end - start + 1,
                "duration_seconds": round((end - start + 1) * self.window_size, 6),
                "max_mlt": round(max(x["mlt"] for x in range_details), 6),
                "max_increase": round(max(x["increase"] for x in range_details), 6),
                "types": sorted(set(x["type"] for x in range_details if x.get("type"))),
            })

        return {
            "baseline": round(baseline, 6),
            "absolute_threshold": absolute_threshold,
            "baseline_mode": candidate_mode,
        }, spike_window_details, merged_spike_periods
    # --------------------------------------------------
    # Sample gap detection
    # --------------------------------------------------

    def detect_sample_gap(self, min_gap_windows=3):
        """
        仅检测已有观测范围内部的 gap。
        也就是只检查 [min_window, max_window] 之间的空洞。
        """
        if not self.windows:
            return []

        sorted_windows = sorted(self.windows.keys())
        scan_start = min(sorted_windows)
        scan_end = max(sorted_windows)

        gap_periods = []
        gap_start = None
        gap_count = 0

        for w in range(scan_start, scan_end + 1):
            if w not in self.windows or len(self.windows[w]) == 0:
                if gap_start is None:
                    gap_start = w
                gap_count += 1
            else:
                if gap_count >= min_gap_windows:
                    gap_periods.append((gap_start, w - 1))
                gap_start = None
                gap_count = 0

        if gap_count >= min_gap_windows:
            gap_periods.append((gap_start, scan_end))

        merged_gaps = []
        for start, end in gap_periods:
            merged_gaps.append({
                "start_window": start,
                "end_window": end,
                "start_time": epoch_to_utc8(start * self.window_size),
                "end_time": epoch_to_utc8((end + 1) * self.window_size),
                "duration_windows": end - start + 1,
                "duration_seconds": round((end - start + 1) * self.window_size, 6),
            })

        return merged_gaps
    def merge_anomaly_periods(self, periods, max_gap_windows=5):
        """
        把不同来源的异常区间（如 gap / elevated）统一合并成最终异常区间。
        规则：
        - 重叠则合并
        - 相邻则合并
        - 中间 gap <= max_gap_windows 也合并
        """
        if not periods:
            return []

        periods = sorted(periods, key=lambda x: x["start_window"])
        merged = [periods[0].copy()]

        for cur in periods[1:]:
            prev = merged[-1]

            gap = cur["start_window"] - prev["end_window"] - 1

            if gap <= max_gap_windows:
                prev["end_window"] = max(prev["end_window"], cur["end_window"])
                prev["end_time"] = epoch_to_utc8((prev["end_window"] + 1) * self.window_size)
                prev["duration_windows"] = prev["end_window"] - prev["start_window"] + 1
                prev["duration_seconds"] = round(prev["duration_windows"] * self.window_size, 6)

                prev_sources = set(prev.get("sources", []))
                cur_sources = set(cur.get("sources", []))
                prev["sources"] = sorted(prev_sources | cur_sources)
            else:
                merged.append(cur.copy())

        return merged
    # --------------------------------------------------
    # Main Diagnosis Logic
    # --------------------------------------------------

    def diagnose(
        self,
        lost_count=0,
        total_packets=0,
        absolute_threshold=0.15,
        min_link_samples=3,
        min_gap_windows=3,
    ):
        samples = self.samples

        # -----------------------------
        # Optional subnet filtering
        # -----------------------------
        if self.focus_subnet:
            try:
                network = ipaddress.ip_network(self.focus_subnet, strict=False)
                filtered = []

                for s in samples:
                    ack_sender = s.get("ack_sender")
                    if ack_sender is None:
                        continue
                    if self._safe_ip_in_subnet(ack_sender, network):
                        filtered.append(s)

                samples = filtered
            except Exception:
                pass

        if not samples:
            return {
                "total_mlt_samples": 0,
                "loss_ratio": 0,
                "health_score": 0,
                "window_size_seconds": self.window_size,
                "mlt_anomaly_analysis": {
                    "baseline": None,
                    "absolute_threshold": absolute_threshold,
                    "spike_windows": [],
                    "merged_spike_periods": [],
                },
                "sample_gap_analysis": [],
                "diagnosis": {
                    "network_status": "CRITICAL",
                    "issues": ["No mlt samples (possible disconnect)"],
                    "gap_issues": [],
                    "elevated_issues": [],
                    "loss_issues": [],
                    "anomaly_periods": [],
                },
            }
        # 不污染 self.samples
        self.build_windows(samples)
        if self.debug:
        
            print('start diagnose')
            print("After subnet filtering, sample count:", len(samples))
            print("Window count:", len(self.windows))

        type_count = {}
        for ws in self.windows.values():
            for s in ws:
                t = s.get("type", "missing")
                type_count[t] = type_count.get(t, 0) + 1
        if self.debug:
            print("Type distribution:", type_count)
            print('link delay')
        # -----------------------------
        # Detect anomalies
        # -----------------------------
        link_info, spike_windows, merged_spike_periods = self.detect_link_delay_spike(
            absolute_threshold=absolute_threshold,
            min_samples=min_link_samples,
        )

        gap_periods = self.detect_sample_gap(min_gap_windows=min_gap_windows)

        # -----------------------------
        # Packet loss
        # -----------------------------
        loss_ratio = 0.0
        if total_packets > 0:
            loss_ratio = lost_count / total_packets

        # -----------------------------
        # Health score (0-100)
        # -----------------------------
        health_score = 100

        if merged_spike_periods:
            health_score -= 20

        if gap_periods:
            health_score -= 40

        if loss_ratio > 0.03:
            health_score -= 25

        health_score = max(0, health_score)

        # -----------------------------
        # Diagnosis result
        # -----------------------------
        diagnosis = {
            "network_status": "NORMAL",
            "issues": [],
            "gap_issues": [],
            "elevated_issues": [],
            "loss_issues": [],
            "anomaly_periods": [],
        }

        # gap 优先级最高
        if gap_periods:
            diagnosis["network_status"] = self._upgrade_status(
                diagnosis["network_status"], "CRITICAL"
            )

            for gap in gap_periods:
                diagnosis["issues"].append(
                    f"No mlt samples from {gap['start_time']} to {gap['end_time']} "
                    f"({gap['duration_seconds']}s, {gap['duration_windows']} windows)"
                )

                diagnosis["gap_issues"].append({
                    "start_time": gap["start_time"],
                    "end_time": gap["end_time"],
                    "duration_seconds": gap["duration_seconds"],
                    "duration_windows": gap["duration_windows"],
                })

        # RTT / MLT 连续异常区间
        if merged_spike_periods:
            diagnosis["network_status"] = self._upgrade_status(
                diagnosis["network_status"], "WARNING"
            )

            for period in merged_spike_periods:
                diagnosis["issues"].append(
                    f"mlt elevated from {period['start_time']} to {period['end_time']} "
                    f"({period['duration_seconds']}s, {period['duration_windows']} windows, "
                    f"max_mlt={period['max_mlt']}s, "
                    f"max_increase=+{period['max_increase']}s, "
                    f"types={period['types']})"
                )

                diagnosis["elevated_issues"].append({
                    "start_time": period["start_time"],
                    "end_time": period["end_time"],
                    "duration_seconds": period["duration_seconds"],
                    "duration_windows": period["duration_windows"],
                    "max_mlt": period["max_mlt"],
                    "max_increase": period["max_increase"],
                    "types": period["types"],
                })

        # 丢包
        if loss_ratio > 0.03:
            diagnosis["network_status"] = self._upgrade_status(
                diagnosis["network_status"], "WARNING"
            )

            loss_msg = f"High packet loss ratio ({round(loss_ratio * 100, 2)}%)"
            diagnosis["issues"].append(loss_msg)
            diagnosis["loss_issues"].append({
                "loss_ratio": round(loss_ratio, 6),
                "loss_percent": round(loss_ratio * 100, 2),
                "message": loss_msg,
            })

        if health_score <= 30:
            diagnosis["network_status"] = self._upgrade_status(
                diagnosis["network_status"], "CRITICAL"
            )
        all_anomaly_periods = []

        for gap in gap_periods:
            all_anomaly_periods.append({
                "start_window": gap["start_window"],
                "end_window": gap["end_window"],
                "start_time": gap["start_time"],
                "end_time": gap["end_time"],
                "duration_windows": gap["duration_windows"],
                "duration_seconds": gap["duration_seconds"],
                "sources": ["gap"],
            })

        for period in merged_spike_periods:
            all_anomaly_periods.append({
                "start_window": period["start_window"],
                "end_window": period["end_window"],
                "start_time": period["start_time"],
                "end_time": period["end_time"],
                "duration_windows": period["duration_windows"],
                "duration_seconds": period["duration_seconds"],
                "sources": ["elevated"],
            })

        final_anomaly_periods = self.merge_anomaly_periods(
            all_anomaly_periods,
            max_gap_windows=5,
        )
        diagnosis["anomaly_periods"] = final_anomaly_periods





        # -----------------------------
        # Final Report
        # -----------------------------
        report = {
            "total_mlt_samples": len(samples),
            "loss_ratio": round(loss_ratio, 6),
            "health_score": health_score,
            "window_size_seconds": self.window_size,
            "mlt_anomaly_analysis": {
                "baseline": link_info.get("baseline"),
                "absolute_threshold": link_info.get("absolute_threshold"),
                "spike_windows": spike_windows,
                "merged_spike_periods": merged_spike_periods,
            },
            "sample_gap_analysis": gap_periods,
            "diagnosis": diagnosis,
        }

        return report

    # --------------------------------------------------
    # Save JSON report
    # --------------------------------------------------

    def save_report(
        self,
        lost_count=0,
        total_packets=0,
        path="diagnosis_report.json",
        absolute_threshold=0.15,
        min_link_samples=3,
        min_gap_windows=3,
    ):
        report = self.diagnose(
            lost_count=lost_count,
            total_packets=total_packets,
            absolute_threshold=absolute_threshold,
            min_link_samples=min_link_samples,
            min_gap_windows=min_gap_windows,
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)

        print(f"\nJSON report saved to: {path}")