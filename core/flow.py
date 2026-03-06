# core/flow.py

from dataclasses import dataclass
from typing import Dict, Tuple


FlowKey = Tuple[str, int, str, int]


@dataclass
class SegmentRecord:
    seq: int
    length: int
    first_send: float
    last_send: float
    retransmissions: int = 0
    is_syn: bool = False   # 新增字段


class FlowManager:
    """
    Responsible only for maintaining outstanding TCP segments.
    Does NOT compute mlt.
    """

    def __init__(self):
        # flow_key -> { seq -> SegmentRecord }
        self.flows: Dict[FlowKey, Dict[int, SegmentRecord]] = {}

    # --------------------------------------------------
    # Create flow key
    # --------------------------------------------------

    def make_key(self, src_ip, src_port, dst_ip, dst_port):
        return (src_ip, src_port, dst_ip, dst_port)

    # --------------------------------------------------
    # Add / update segment
    # --------------------------------------------------

    def add_segment(self, key, seq, length, timestamp, is_syn=False):

        if key not in self.flows:
            self.flows[key] = {}

        bucket = self.flows[key]

        if seq in bucket:
            # retransmission
            rec = bucket[seq]
            rec.last_send = timestamp
            rec.retransmissions += 1
        else:
            bucket[seq] = SegmentRecord(
                seq=seq,
                length=length,
                first_send=timestamp,
                last_send=timestamp,
                is_syn=is_syn  # 🔥 正确传入
            )

    # --------------------------------------------------
    # Get outstanding segments for a flow
    # --------------------------------------------------

    def get_bucket(self, key: FlowKey):
        return self.flows.get(key, {})

    # --------------------------------------------------
    # Remove confirmed segment
    # --------------------------------------------------

    def remove_segment(self, key: FlowKey, seq: int):
        if key in self.flows:
            return self.flows[key].pop(seq, None)
        return None

    # --------------------------------------------------
    # Reverse flow key
    # --------------------------------------------------

    def reverse_key(self, key: FlowKey):
        src, sport, dst, dport = key
        return (dst, dport, src, sport)

    # --------------------------------------------------
    # Cleanup timeout segments
    # --------------------------------------------------

    def cleanup(self, current_time, timeout):

        lost_samples = []

        for key in list(self.flows.keys()):
            bucket = self.flows[key]

            to_remove = []

            for seq, rec in bucket.items():
                if current_time - rec.last_send > timeout:
                    to_remove.append(seq)

            for seq in to_remove:
                rec = bucket.pop(seq)

                lost_samples.append({
                    "flow": key,
                    "seq": rec.seq,
                    "length": rec.length,
                    "first_send": rec.first_send,
                    "last_send": rec.last_send,
                    "ack_time": None,
                    "mlt_base": None,
                    "mlt_last": None,
                    "retransmissions": rec.retransmissions,
                    "type": "lost"
                })

        return lost_samples