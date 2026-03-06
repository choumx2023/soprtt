# core/collector.py

from collections import defaultdict
from typing import List, Dict
import json
import matplotlib.pyplot as plt
from utils.time_utils import epoch_to_utc8
import ipaddress

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

            # 1️⃣ Per-flow MLT storage
            self.mlt_data[flow].append(mlt)

            # 2️⃣ Raw sample storage (full time series)
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
                # 保留 ACK 发送端，用于子网过滤 / 可视化
                "ack_sender": s.get("ack_sender"),
                "acked_segments": s.get("acked_segments"),
                "acked_bytes": s.get("acked_bytes"),
                "target_seq": s.get("target_seq"),
            }

            self.samples.append(sample)

            self.total_samples += 1

    # --------------------------------------------------
    # Get FULL MLT time series
    # --------------------------------------------------

    def get_all_mlt(self) -> List[Dict]:
        """
        Return full raw MLT samples (no aggregation).
        """
        return self.samples

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

    def get_sorted_mlt(self) -> List[Dict]:
        return sorted(
            self.samples,
            key=lambda x: x["timestamp"]
        )

    # --------------------------------------------------
    # Print all MLT samples
    # --------------------------------------------------

    def print_samples(self):
        print("\n===== MLT Raw Samples (Grouped by Flow Direction) =====")

        # Group samples by flow (direction matters)
        grouped = {}

        for s in self.get_sorted_mlt():
            flow = s["flow"]
            direction = f"{flow[0]}:{flow[1]} -> {flow[2]}:{flow[3]}"
            grouped.setdefault(direction, []).append(
                (s["timestamp"], s["mlt"], s.get("type"))
            )

        for direction, records in grouped.items():
            print(f"\nFlow Direction: {direction}")
            for ts, mlt, ty in records:
                print(
                    f"  {ts} | MLT={round(mlt,6)} | type={ty}"
                )

        print("\nTotal MLT samples:", self.total_samples)

    # --------------------------------------------------
    # Per-flow statistical summary
    # --------------------------------------------------
    def summary(self, subnet: str = None):

        print("\n===== MLT Summary =====")

        filtered_samples = self.samples

        if subnet:
            network = ipaddress.ip_network(subnet, strict=False)

            filtered_samples = [
                s for s in self.samples
                if ipaddress.ip_address(s["flow"][0]) in network
                or ipaddress.ip_address(s["flow"][2]) in network
            ]

        print("Total MLT samples:", len(filtered_samples))

        for s in filtered_samples:
            print(
                f"{s['timestamp']} | "
                f"{s['flow']} | "
                f"type={s.get('type')} | "
                f"MLT={round(s['mlt'],6)}"
            )


    # --------------------------------------------------
    # Export FULL MLT series to CSV
    # --------------------------------------------------

    def export_full_series(self, path="mlt_full_series.csv"):

        with open(path, "w") as f:

            f.write(
                "timestamp,time_utc8,flow,seq,length,"
                "mlt,type,back_to_back,retransmissions,"
                "ack_sender,acked_segments,acked_bytes,target_seq\n"
            )

            for s in self.get_sorted_mlt():

                f.write(
                    f"{s['timestamp']},"
                    f"{s['time_utc8']},"
                    f"{s['flow']},"
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

    def export_json(self, path="mlt_full_series.json"):

        with open(path, "w") as f:
            json.dump(self.get_sorted_mlt(), f, indent=4)

        print(f"\nFull MLT time series exported to: {path}")


    # --------------------------------------------------
    # Plot MLT time series
    # --------------------------------------------------

    
    def plot_mlt_time_series(self, path="mlt_time_series.png", subnet=None):
        """
        Plot MLT over time.
        If subnet is provided (e.g., "183.172.73.0/24"),
        only flows matching this subnet will be plotted.
        """

        if not self.samples:
            print("No MLT samples to plot.")
            return

        import matplotlib.pyplot as plt
        import ipaddress

        # -----------------------------
        # Optional subnet filtering
        # -----------------------------
        filtered = self.samples

        if subnet:
            try:
                network = ipaddress.ip_network(subnet, strict=False)

                filtered = [
                    s for s in self.samples
                    if "ack_sender" in s and
                       ipaddress.ip_address(s["ack_sender"]) in network
                ]
            except Exception:
                print(f"Invalid subnet format: {subnet}")
                return

        if not filtered:
            print("No MLT samples after subnet filtering.")
            return

        # -----------------------------
        # Sort by timestamp
        # -----------------------------
        filtered = sorted(filtered, key=lambda x: x["timestamp"])

        times = [s["timestamp"] for s in filtered]
        mlts = [s["mlt"] for s in filtered]
        types = [s.get("type", "data") for s in filtered]

        # -----------------------------
        # Separate by type
        # -----------------------------
        data_x, data_y = [], []
        b2b_x, b2b_y = [], []
        syn_x, syn_y = [], []

        for t, r, ty in zip(times, mlts, types):
            if ty == "b2b":
                b2b_x.append(t)
                b2b_y.append(r)
            elif ty == "syn":
                syn_x.append(t)
                syn_y.append(r)
            else:
                data_x.append(t)
                data_y.append(r)

        # -----------------------------
        # Plot
        # -----------------------------
        plt.figure()

        if data_x:
            plt.scatter(data_x, data_y, s=5, label="data")
        if b2b_x:
            plt.scatter(b2b_x, b2b_y, s=10, label="b2b")
        if syn_x:
            plt.scatter(syn_x, syn_y, s=15, label="syn")

        plt.xlabel("Timestamp")
        plt.ylabel("MLT (seconds)")
        plt.title("MLT Time Series")
        plt.legend()
        plt.tight_layout()
        plt.ylim(0,1)
        plt.savefig(path)
        plt.close()

        print(f"MLT time series plot saved to: {path}")
