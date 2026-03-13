from typing import List, Optional
import os
import ipaddress
import json
import sys
from datetime import datetime

from scapy.all import PcapReader
from core.packet_parser import PacketParser
from core.flow import FlowManager
from core.matcher import MLTMatcher
from core.collector import MLTCollector
from core.analyzer import MLTAnalyzer
from core.filter import FlowFilter


class MLTEngine:

    def __init__(self,
                 timeout: float = 3.0,
                 monitor_ips: Optional[List[str]] = None,
                 target_ips: Optional[List[str]] = None):

        self.timeout = timeout

        self.packet_count = 0
        self.lost_count = 0

        self.parser = PacketParser()
        self.flow_manager = FlowManager()

        self.flow_filter = FlowFilter(
            monitor_ips=monitor_ips,
            target_ips=target_ips
        )

        self.matcher = MLTMatcher(
            self.flow_manager,
            flow_filter=self.flow_filter
        )

        self.collector = MLTCollector()

    def _count_total_packets(self, pcap_file):
        total = 0
        with PcapReader(pcap_file) as packets:
            for _ in packets:
                total += 1
        return total

    def _print_progress(self, current, total, bar_width=30):
        if total <= 0:
            return

        ratio = min(max(current / total, 0.0), 1.0)
        filled = int(bar_width * ratio)
        bar = "#" * filled + "-" * (bar_width - filled)
        percent = ratio * 100

        sys.stdout.write(f"\rProcessing packets: [{bar}] {percent:6.2f}% ({current}/{total})")
        sys.stdout.flush()

    def _write_progress_file(self, output_dir, current, total, status="running"):
        if total <= 0:
            percent = 0.0
        else:
            percent = round(min(max(current / total, 0.0), 1.0) * 100, 2)

        progress_path = os.path.join(output_dir, "progress.json")
        payload = {
            "status": status,
            "current_packets": current,
            "total_packets": total,
            "percent": percent,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

    def process_packet(self, packet):
        data = self.parser.parse(packet)

        if not data:
            return

        key = self.flow_manager.make_key(
            data["src_ip"],
            data["src_port"],
            data["dst_ip"],
            data["dst_port"]
        )

        timestamp = data["timestamp"]

        if (
            data["payload_len"] > 0
            or data["flags"]["SYN"]
            or data["flags"]["FIN"]
        ):
            length = data["payload_len"]

            if data["flags"]["SYN"] or data["flags"]["FIN"]:
                length += 1

            self.flow_manager.add_segment(
                key,
                data["seq"],
                length,
                timestamp,
                is_syn=data["flags"]["SYN"]
            )

        if data["flags"]["ACK"]:
            samples = self.matcher.handle_ack(
                key,
                data["ack"],
                timestamp
            )

            if samples:
                self.collector.add_samples(samples)

    def run(self, pcap_file, output_dir="outputs", log_events=None):
        os.makedirs(output_dir, exist_ok=True)
        self.packet_count = 0
        self.lost_count = 0
        self.flow_manager = FlowManager()
        self.matcher = MLTMatcher(
            self.flow_manager,
            flow_filter=self.flow_filter
        )
        self.collector = MLTCollector()

        total_packets = self._count_total_packets(pcap_file)
        print(f"Total packets to process: {total_packets}")
        self._write_progress_file(output_dir, 0, total_packets, status="running")

        last_timestamp = 0.0

        with PcapReader(pcap_file) as packets:
            for pkt in packets:
                self.packet_count += 1
                last_timestamp = float(pkt.time)

                self.process_packet(pkt)

                if self.packet_count % 10000 == 0:
                    self._print_progress(self.packet_count, total_packets)
                    self._write_progress_file(output_dir, self.packet_count, total_packets, status="running")

                    lost = self.flow_manager.cleanup(
                        last_timestamp,
                        self.timeout
                    )

                    if lost:
                        self.lost_count += len(lost)
                        self.collector.add_samples(lost)

            lost = self.flow_manager.cleanup(
                last_timestamp,
                self.timeout
            )

            if lost:
                self.lost_count += len(lost)
                self.collector.add_samples(lost)

        self._print_progress(self.packet_count, total_packets)
        self._write_progress_file(output_dir, self.packet_count, total_packets, status="running")
        print()

        print("\nFinished processing.")
        print("\n===== Flow Statistics =====")
        print("Total packets:", self.packet_count)
        print("Lost segments:", self.lost_count)

        ANALYSIS_SUBNET = "183.172.73.0/24"

        analyzer = MLTAnalyzer(
            self.collector.samples,
            window_size=1.0,
            focus_subnet=ANALYSIS_SUBNET
        )

        network = ipaddress.ip_network(ANALYSIS_SUBNET, strict=False)

        filtered_samples = []
        for s in self.collector.samples:
            ack_sender = s.get("ack_sender")
            if ack_sender is None:
                continue
            try:
                if ipaddress.ip_address(ack_sender) in network:
                    filtered_samples.append(s)
            except ValueError:
                continue

        filtered_total_samples = len(filtered_samples)
        filtered_lost = len([
            s for s in filtered_samples
            if s.get("type") == "lost"
        ])

        report = analyzer.diagnose(
            lost_count=filtered_lost,
            total_packets=filtered_total_samples,
            absolute_threshold=0.15,
            min_link_samples=3,
            min_gap_windows=3,
        )

        report_path = os.path.join(output_dir, "diagnosis_report.json")
        csv_path = os.path.join(output_dir, "mlt_full_series.csv")
        json_path = os.path.join(output_dir, "mlt_full_series.json")
        plot_path = os.path.join(output_dir, "mlt_time_series.png")
        overlay_plot_path = os.path.join(output_dir, "mlt_with_logs.png")
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)

        self.collector.export_full_series(csv_path, subnet=ANALYSIS_SUBNET)
        self.collector.export_json(json_path, subnet=ANALYSIS_SUBNET)
        self.collector.plot_mlt_time_series(plot_path, subnet=ANALYSIS_SUBNET)   
        if log_events:
            self.collector.plot_mlt_with_log_markers(
                log_events=log_events,
                path=overlay_plot_path,
                subnet=ANALYSIS_SUBNET
            )
        
        self._write_progress_file(output_dir, self.packet_count, total_packets, status="completed")
        return {
            "status": "success",
            "pcap_file": pcap_file,
            "output_dir": output_dir,
            "packet_count": self.packet_count,
            "lost_count": self.lost_count,
            "analysis_subnet": ANALYSIS_SUBNET,
            "filtered_total_samples": filtered_total_samples,
            "filtered_lost": filtered_lost,
            "report_path": report_path,
            "csv_path": csv_path,
            "json_path": json_path,
            "plot_path": plot_path,
            "overlay_plot_path": overlay_plot_path if log_events else None,
            "report": report,
        }