# core/packet_parser.py

from scapy.layers.inet import IP, TCP


class PacketParser:
    """
    Extract structured TCP information from scapy packets.
    This module does NOT handle MLT logic.
    """

    def parse(self, packet):
        """
        Parse a scapy packet and return structured TCP info.

        Returns:
            dict or None
        """

        # Only process IPv4 TCP packets
        if IP not in packet or TCP not in packet:
            return None

        ip = packet[IP]
        tcp = packet[TCP]

        payload_len = len(tcp.payload)

        # Build structured result
        result = {
            "src_ip": ip.src,
            "dst_ip": ip.dst,
            "src_port": tcp.sport,
            "dst_port": tcp.dport,
            "seq": tcp.seq,
            "ack": tcp.ack,
            "payload_len": payload_len,
            "timestamp": float(packet.time),
            "flags": {
                "SYN": bool(tcp.flags.S),
                "ACK": bool(tcp.flags.A),
                "FIN": bool(tcp.flags.F),
                "RST": bool(tcp.flags.R),
            }
        }

        return result