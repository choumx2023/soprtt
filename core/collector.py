from collections import defaultdict
from typing import List, Dict, Optional
import json
import ipaddress
import matplotlib.pyplot as plt
from datetime import datetime

from utils.time_utils import epoch_to_utc8


class MLTCollector:
    """
    Collect MLT samples.
    Stores BOTH:
        - per-flow aggregated MLT list
        - full raw MLT time series
    """

    def __init__(self):
        # flow_key -> list of mlt values
        self.mlt_data = defaultdict(list)

        # full raw samples (time series)
        self.samples: List[Dict] = []

        self.total_samples = 0
    def _parse_log_time(self, value: str):
        text = str(value).strip()
        if not text:
            return None

        text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None

        return dt.timestamp()
    def plot_mlt_with_log_markers(
        self,
        log_events: List[Dict],
        path: str = "mlt_with_logs.png",
        subnet: Optional[str] = None
    ):
        """
        Plot MLT time series and overlay log anomaly timestamps.

        log_events example:
            [
                {"time": "2026-03-01 18:02:04+08:00", "event_id": 2, "raw_message": "..."},
                {"time": "2026-03-01 18:07:12+08:00", "event_id": 3, "raw_message": "..."},
            ]
        """

        filtered = self.get_sorted_mlt(subnet=subnet)

        if not filtered:
            print("No MLT samples to plot.")
            return

        times = [s["timestamp"] for s in filtered]
        mlts = [s["mlt"] for s in filtered]
        types = [s.get("type", "data") for s in filtered]

        data_x, data_y = [], []
        b2b_x, b2b_y = [], []
        syn_x, syn_y = [], []
        lost_x, lost_y = [], []

        for t, r, ty in zip(times, mlts, types):
            if ty == "b2b":
                b2b_x.append(t)
                b2b_y.append(r)
            elif ty == "syn":
                syn_x.append(t)
                syn_y.append(r)
            elif ty == "lost":
                lost_x.append(t)
                lost_y.append(r)
            else:
                data_x.append(t)
                data_y.append(r)

        plt.figure(figsize=(12, 5))

        if data_x:
            plt.scatter(data_x, data_y, s=5, label="mlt:data")
        if b2b_x:
            plt.scatter(b2b_x, b2b_y, s=10, label="mlt:b2b")
        if syn_x:
            plt.scatter(syn_x, syn_y, s=15, label="mlt:syn")
        if lost_x:
            plt.scatter(lost_x, lost_y, s=20, label="mlt:lost")

        if log_events:
            event2_x, event2_y = [], []
            event3_x, event3_y = [], []
            other_x, other_y = [], []
            marker_y = 0.82

            for event in log_events:
                log_ts = self._parse_log_time(event.get("time", ""))
                if log_ts is None:
                    continue

                event_id = event.get("event_id")
                if event_id == 2:
                    event2_x.append(log_ts)
                    event2_y.append(marker_y)
                elif event_id == 3:
                    event3_x.append(log_ts)
                    event3_y.append(marker_y)
                else:
                    other_x.append(log_ts)
                    other_y.append(marker_y)

                plt.axvline(log_ts, linestyle="--", alpha=0.35)

            if event2_x:
                plt.scatter(event2_x, event2_y, s=45, marker="o", label="log:event_id=2")
            if event3_x:
                plt.scatter(event3_x, event3_y, s=55, marker="^", label="log:event_id=3")
            if other_x:
                plt.scatter(other_x, other_y, s=45, marker="x", label="log:other")

        tick_positions = []
        tick_labels = []
        seen = set()
        for ts in times:
            label = epoch_to_utc8(ts)[11:16].replace(":", ".")
            if label not in seen:
                tick_positions.append(ts)
                tick_labels.append(label)
                seen.add(label)

        if tick_positions:
            max_ticks = 10
            step = max(1, len(tick_positions) // max_ticks)
            plt.xticks(tick_positions[::step], tick_labels[::step], rotation=30)

        plt.xlabel("Time (UTC+8)")
        plt.ylabel("MLT (seconds)")
        plt.title("MLT Time Series with Log Event Markers")
        plt.legend()
        plt.tight_layout()
        plt.ylim(0, 1)
        plt.savefig(path)
        plt.close()

        print(f"MLT + log overlay plot saved to: {path}")
    # --------------------------------------------------
    # Add samples
    # --------------------------------------------------

    def add_samples(self, samples: List[Dict]):
        for s in samples:
            # skip lost / invalid
            if s.get("ack_time") is None:
                continue

            mlt = s.get("mlt")
            if mlt is None:
                continue

            flow = s.get("flow")
            if flow is None:
                continue

            # 1) Per-flow MLT storage
            self.mlt_data[flow].append(mlt)

            # 2) Raw sample storage (full time series)
            sample = {
                "flow": flow,
                "seq": s.get("seq"),
                "length": s.get("length"),
                "timestamp": s.get("ack_time"),
                "time_utc8": epoch_to_utc8(s.get("ack_time")),
                "mlt": mlt,
                "type": s.get("type", "data"),
                "back_to_back": s.get("back_to_back", False),
                "retransmissions": s.get("retransmissions", 0),
                "ack_sender": s.get("ack_sender"),
                "acked_segments": s.get("acked_segments"),
                "acked_bytes": s.get("acked_bytes"),
                "target_seq": s.get("target_seq"),
            }

            self.samples.append(sample)
            self.total_samples += 1

    # --------------------------------------------------
    # Internal helper: unified subnet filter
    # --------------------------------------------------

    def _filter_samples(self, subnet: Optional[str] = None) -> List[Dict]:
        if not subnet:
            return list(self.samples)

        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except Exception:
            print(f"Invalid subnet format: {subnet}")
            return []

        filtered = []
        for s in self.samples:
            ack_sender = s.get("ack_sender")
            if ack_sender is None:
                continue

            try:
                if ipaddress.ip_address(ack_sender) in network:
                    filtered.append(s)
            except Exception:
                continue

        return filtered

    # --------------------------------------------------
    # Get FULL MLT time series
    # --------------------------------------------------

    def get_all_mlt(self, subnet: Optional[str] = None) -> List[Dict]:
        """
        Return full raw MLT samples (no aggregation).
        """
        return self._filter_samples(subnet=subnet)

    # --------------------------------------------------
    # Get MLT by specific flow
    # --------------------------------------------------

    def get_mlt_by_flow(self, flow_key) -> List[Dict]:
        return [
            s for s in self.samples
            if s["flow"] == flow_key
        ]

    # --------------------------------------------------
    # Get sorted MLT by timestamp
    # --------------------------------------------------

    def get_sorted_mlt(self, subnet: Optional[str] = None) -> List[Dict]:
        return sorted(
            self._filter_samples(subnet=subnet),
            key=lambda x: x["timestamp"]
        )

    # --------------------------------------------------
    # Print all MLT samples
    # --------------------------------------------------

    def print_samples(self, subnet: Optional[str] = None):
        print("\n===== MLT Raw Samples (Grouped by Flow Direction) =====")

        filtered = self.get_sorted_mlt(subnet=subnet)

        if not filtered:
            print("No MLT samples.")
            return

        grouped = {}

        for s in filtered:
            flow = s["flow"]
            direction = f"{flow[0]}:{flow[1]} -> {flow[2]}:{flow[3]}"
            grouped.setdefault(direction, []).append(
                (s["timestamp"], s["mlt"], s.get("type"))
            )

        for direction, records in grouped.items():
            print(f"\nFlow Direction: {direction}")
            for ts, mlt, ty in records:
                print(f"  {ts} | MLT={round(mlt, 6)} | type={ty}")

        print("\nTotal MLT samples:", len(filtered))

    # --------------------------------------------------
    # Per-flow statistical summary
    # --------------------------------------------------

    def summary(self, subnet: Optional[str] = None):
        print("\n===== MLT Summary =====")

        filtered_samples = self.get_sorted_mlt(subnet=subnet)

        print("Total MLT samples:", len(filtered_samples))

        for s in filtered_samples:
            print(
                f"{s['timestamp']} | "
                f"{s['flow']} | "
                f"type={s.get('type')} | "
                f"MLT={round(s['mlt'], 6)}"
            )

    # --------------------------------------------------
    # Export FULL MLT series to CSV
    # --------------------------------------------------

    def export_full_series(
        self,
        path: str = "mlt_full_series.csv",
        subnet: Optional[str] = None
    ):
        filtered = self.get_sorted_mlt(subnet=subnet)

        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "timestamp,time_utc8,flow,seq,length,"
                "mlt,type,back_to_back,retransmissions,"
                "ack_sender,acked_segments,acked_bytes,target_seq\n"
            )

            for s in filtered:
                f.write(
                    f"{s['timestamp']},"
                    f"{s['time_utc8']},"
                    f"\"{s['flow']}\","
                    f"{s['seq']},"
                    f"{s['length']},"
                    f"{s['mlt']},"
                    f"{s['type']},"
                    f"{s['back_to_back']},"
                    f"{s['retransmissions']},"
                    f"{s.get('ack_sender')},"
                    f"{s.get('acked_segments')},"
                    f"{s.get('acked_bytes')},"
                    f"{s.get('target_seq')}\n"
                )

        print(f"\nFull MLT time series exported to: {path}")

    # --------------------------------------------------
    # Export to JSON
    # --------------------------------------------------

    def export_json(
        self,
        path: str = "mlt_full_series.json",
        subnet: Optional[str] = None
    ):
        filtered = self.get_sorted_mlt(subnet=subnet)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=4, ensure_ascii=False)

        print(f"\nFull MLT time series exported to: {path}")

    # --------------------------------------------------
    # Plot MLT time series
    # --------------------------------------------------

    def plot_mlt_time_series(
        self,
        path: str = "mlt_time_series.png",
        subnet: Optional[str] = None
    ):
        """
        Plot MLT over time.
        If subnet is provided (e.g., "183.172.73.0/24"),
        only samples whose ack_sender is in this subnet are plotted.
        """

        filtered = self.get_sorted_mlt(subnet=subnet)

        if not filtered:
            print("No MLT samples to plot.")
            return

        times = [s["timestamp"] for s in filtered]
        mlts = [s["mlt"] for s in filtered]
        types = [s.get("type", "data") for s in filtered]

        data_x, data_y = [], []
        b2b_x, b2b_y = [], []
        syn_x, syn_y = [], []
        lost_x, lost_y = [], []

        for t, r, ty in zip(times, mlts, types):
            if ty == "b2b":
                b2b_x.append(t)
                b2b_y.append(r)
            elif ty == "syn":
                syn_x.append(t)
                syn_y.append(r)
            elif ty == "lost":
                lost_x.append(t)
                lost_y.append(r)
            else:
                data_x.append(t)
                data_y.append(r)

        plt.figure()

        if data_x:
            plt.scatter(data_x, data_y, s=5, label="data")
        if b2b_x:
            plt.scatter(b2b_x, b2b_y, s=10, label="b2b")
        if syn_x:
            plt.scatter(syn_x, syn_y, s=15, label="syn")
        if lost_x:
            plt.scatter(lost_x, lost_y, s=20, label="lost")

        tick_positions = []
        tick_labels = []
        seen = set()
        for ts in times:
            label = epoch_to_utc8(ts)[11:16].replace(":", ".")
            if label not in seen:
                tick_positions.append(ts)
                tick_labels.append(label)
                seen.add(label)

        if tick_positions:
            max_ticks = 10
            step = max(1, len(tick_positions) // max_ticks)
            plt.xticks(tick_positions[::step], tick_labels[::step], rotation=30)

        plt.xlabel("Time (UTC+8)")
        plt.ylabel("MLT (seconds)")
        plt.title("MLT Time Series")
        plt.legend()
        plt.tight_layout()
        plt.ylim(0, 0.8)
        plt.savefig(path)
        plt.close()

        print(f"MLT time series plot saved to: {path}")