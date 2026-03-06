# core/matcher.py

from typing import List, Dict


class MLTMatcher:
    """
    Responsible for matching ACKs with outstanding segments
    and generating MLT samples.
    """
    def __init__(self, flow_manager, flow_filter=None):
        self.flow_manager = flow_manager
        self.flow_filter = flow_filter
    # --------------------------------------------------
    # Handle ACK
    # --------------------------------------------------

    def handle_ack(self, flow_key, ack_num, timestamp) -> List[Dict]:
        samples = []

        reverse_key = self.flow_manager.reverse_key(flow_key)

        # 如果配置了过滤器，只统计匹配的流
        if self.flow_filter and not self.flow_filter.match(reverse_key):
            return samples

        bucket = self.flow_manager.get_bucket(reverse_key)
        if not bucket:
            return samples

        confirmed = []
        total_acked_bytes = 0

        for seq, rec in bucket.items():
            if rec.seq + rec.length <= ack_num:
                confirmed.append(seq)
                total_acked_bytes += rec.length

        if not confirmed:
            return samples

        confirmed = sorted(confirmed)
        back_to_back = (len(confirmed) >= 2)

        # 改成最后一个被确认的 seq
        latest_seq = confirmed[-1]
        target_rec = None

        for seq in confirmed:
            rec = self.flow_manager.remove_segment(reverse_key, seq)
            if rec is None:
                continue

            if seq == latest_seq:
                target_rec = rec

        if target_rec is None:
            return samples

        mlt_base = timestamp - target_rec.first_send
        mlt_last = timestamp - target_rec.last_send

        if getattr(target_rec, "is_syn", False):
            sample_type = "syn"
        elif back_to_back:
            sample_type = "b2b"
        else:
            sample_type = "data"

        sample = {
            "flow": reverse_key,
            "ack_time": timestamp,
            "mlt": mlt_base,
            "mlt_last": mlt_last,
            "retransmissions": target_rec.retransmissions,
            "back_to_back": back_to_back,
            "type": sample_type,
            "ack_sender": flow_key[0],
            "acked_segments": len(confirmed),
            "acked_bytes": total_acked_bytes,
            "target_seq": latest_seq,
        }

        samples.append(sample)
        return samples   
        
        
        
    
    
    
    
    