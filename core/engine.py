from typing import List, Optional

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

        # 统计信息
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

    # --------------------------------------------------
    # Process one packet
    # --------------------------------------------------

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

        # SEND
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

        # ACK
        if data["flags"]["ACK"]:

            samples = self.matcher.handle_ack(
                key,
                data["ack"],
                timestamp
            )

            if samples:
                self.collector.add_samples(samples)

    # --------------------------------------------------
    # Run over PCAP
    # --------------------------------------------------

    def run(self, pcap_file):

        last_timestamp = 0.0

        with PcapReader(pcap_file) as packets:

            for pkt in packets:

                self.packet_count += 1
                last_timestamp = float(pkt.time)

                self.process_packet(pkt)

                if self.packet_count % 10000 == 0:
                    print("Processed", self.packet_count)

                    lost = self.flow_manager.cleanup(
                        last_timestamp,
                        self.timeout
                    )

                    if lost:
                        self.lost_count += len(lost)
                        self.collector.add_samples(lost)

            # Final cleanup
            lost = self.flow_manager.cleanup(
                last_timestamp,
                self.timeout
            )

            if lost:
                self.lost_count += len(lost)
                self.collector.add_samples(lost)

        print("\nFinished processing.")

        print("\n===== Flow Statistics =====")
        print("Total packets:", self.packet_count)
        print("Lost segments:", self.lost_count)

        self.collector.summary()

        # -----------------------------
        # Analyze only specific subnet (e.g. 183.x)
        # -----------------------------
        ANALYSIS_SUBNET = "183.172.73.0/24"

        analyzer = MLTAnalyzer(
            self.collector.samples,
            focus_subnet=ANALYSIS_SUBNET
        )

        # Compute loss stats ONLY for that subnet (based on ack_sender)
        import ipaddress
        network = ipaddress.ip_network(ANALYSIS_SUBNET, strict=False)

        filtered_samples = [
            s for s in self.collector.samples
            if "ack_sender" in s and
               ipaddress.ip_address(s["ack_sender"]) in network
        ]

        filtered_total_packets = len(filtered_samples)
        print("halo ",len(self.collector.samples), filtered_total_packets)
        filtered_lost = len([
            s for s in filtered_samples
            if s.get("type") == "lost"
        ])

        analyzer.save_report(
            lost_count=filtered_lost,
            total_packets=filtered_total_packets,
            path="diagnosis_report.json"
        )

        # Export / visualize only this subnet
        self.collector.print_samples()
        self.collector.export_full_series("mlt_full_series.csv")
        self.collector.export_json("mlt_full_series.json", )

        self.collector.plot_mlt_time_series(
            "mlt_time_series.png",
            subnet=ANALYSIS_SUBNET
        )

        self.collector.summary(subnet=ANALYSIS_SUBNET)