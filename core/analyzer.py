# core/analyzer.py

from collections import defaultdict
import json
from utils.time_utils import epoch_to_utc8
import ipaddress

class MLTAnalyzer:

    def __init__(self, samples, window_size=1.0, focus_subnet=None):

        self.samples = samples
        self.window_size = window_size
        self.windows = defaultdict(list)

        # 只分析某个子网（例如 183.x.x.x）
        self.focus_subnet = focus_subnet
    # --------------------------------------------------
    # Build time windows
    # --------------------------------------------------

    def build_windows(self):

        self.windows.clear()

        for s in self.samples:
            if s.get("ack_time") is None:
                continue

            window = int(s["ack_time"] // self.window_size)
            self.windows[window].append(s)

    # --------------------------------------------------
    # Link delay detection (SYN + B2B)
    # --------------------------------------------------

    def detect_link_delay_spike(self, absolute_threshold=0.15, min_samples=3):

        # 使用全局最小 syn/b2b 作为基线，避免窗口稀疏导致偏高
        all_link_mlts = [
            s["mlt"]
            for samples in self.windows.values()
            for s in samples
            if s.get("type") in ("syn", "b2b")
        ]

        if len(all_link_mlts) < min_samples:
            return {}, []

        baseline = min(all_link_mlts)

        spikes = []

        # 2️⃣ 不再看平均值
        #    只要某个 syn/b2b 样本超过 baseline + threshold 就触发
        for w, samples in self.windows.items():

            critical_samples = [
                s for s in samples
                if s.get("type") in ("syn", "b2b")
            ]

            for s in critical_samples:
                if s["mlt"] - baseline >= absolute_threshold:

                    spikes.append({
                        "window": w,
                        "time": epoch_to_utc8(w * self.window_size),
                        "mlt": round(s["mlt"], 6),
                        "increase": round(s["mlt"] - baseline, 6),
                        "type": s.get("type")
                    })

                    break  # 一个窗口只记一次异常

        return {
            "baseline": round(baseline, 6),
            "absolute_threshold": absolute_threshold
        }, spikes

    def detect_sample_gap(self, min_gap_windows=3):

        if not self.windows:
            return []

        sorted_windows = sorted(self.windows.keys())

        gap_periods = []
        gap_start = None
        gap_count = 0

        for w in range(min(sorted_windows), max(sorted_windows) + 1):

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
            gap_periods.append((gap_start, sorted_windows[-1]))

        return gap_periods
    # --------------------------------------------------
    # Main Diagnosis Logic
    # --------------------------------------------------

    def diagnose(self, lost_count=0, total_packets=0):
        # --------------------------------------------------
        # Optional subnet filtering (only analyze 183 subnet)
        # --------------------------------------------------
        samples = self.samples

        if self.focus_subnet:
            try:
                network = ipaddress.ip_network(self.focus_subnet, strict=False)
                samples = [
                    s for s in samples
                    if "ack_sender" in s and
                       ipaddress.ip_address(s["ack_sender"]) in network
                ]
            except Exception:
                pass

        if not samples:
            return {
                "total_mlt_samples": 0,
                "loss_ratio": 0,
                "health_score": 0,
                "diagnosis": {
                    "network_status": "CRITICAL",
                    "issues": ["No mlt samples (possible disconnect)"]
                }
            }

        self.samples = samples
        self.build_windows()

        link_info, link_spikes = self.detect_link_delay_spike()

        # -----------------------------
        # Packet loss
        # -----------------------------
        loss_ratio = 0
        if total_packets > 0:
            loss_ratio = lost_count / total_packets

        # -----------------------------
        # Health score (0-100)
        # -----------------------------
        health_score = 100

        if link_spikes:
            health_score -= 20

        if loss_ratio > 0.03:
            health_score -= 25

        if len(samples) == 0:
            health_score = 0

        health_score = max(0, health_score)

        # -----------------------------
        # Diagnosis result
        # -----------------------------
        diagnosis = {
            "network_status": "NORMAL",
            "issues": []
        }
        gaps = self.detect_sample_gap()

        if gaps:
            diagnosis["network_status"] = "CRITICAL"
            for start, end in gaps:
                diagnosis["issues"].append(
                    f"No mlt samples from {epoch_to_utc8(start*self.window_size)} "
                    f"to {epoch_to_utc8(end*self.window_size)} "
                    "(possible disconnect or host failure)"
                )
        # -----------------------------
        # Link latency spike (with time)
        # -----------------------------
        if link_spikes:
            diagnosis["network_status"] = "WARNING"

            for spike in link_spikes:
                diagnosis["issues"].append(
                    f"mlt increased at {spike['time']} "
                    f"(mlt={spike['mlt']}s, "
                    f"+{spike['increase']}s over baseline, "
                    f"type={spike.get('type')})"
                )

        # -----------------------------
        # Packet loss warning
        # -----------------------------
        if loss_ratio > 0.03:
            diagnosis["network_status"] = "WARNING"
            diagnosis["issues"].append(
                f"High packet loss ratio ({round(loss_ratio*100,2)}%)"
            )

        if health_score <= 30:
            diagnosis["network_status"] = "CRITICAL"

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
                "spikes": link_spikes
            },
            "diagnosis": diagnosis
        }

        return report

    # --------------------------------------------------
    # Save JSON report
    # --------------------------------------------------

    def save_report(self, lost_count=0, total_packets=0,
                    path="diagnosis_report.json"):

        report = self.diagnose(
            lost_count=lost_count,
            total_packets=total_packets
        )

        with open(path, "w") as f:
            json.dump(report, f, indent=4)

        print(f"\nJSON report saved to: {path}")
