from typing import List, Optional, Tuple
import ipaddress
FlowKey = Tuple[str, int, str, int]


class FlowFilter:

    def __init__(
        self,
        monitor_ips: Optional[List[str]] = None,
        target_ips: Optional[List[str]] = None
    ):
        self.monitor_ips = monitor_ips or []
        self.target_ips = target_ips or []

    def _ip_in_list(self, ip: str, patterns: List[str]) -> bool:
        """
        支持：
        - 精确IP (192.168.1.10)
        - 子网 (192.168.1.0/24)
        """
        for p in patterns:
            try:
                if "/" in p:
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(p, strict=False):
                        return True
                else:
                    if ip == p:
                        return True
            except Exception:
                continue
        return False


    def match(self, flow: FlowKey) -> bool:

        if not self.monitor_ips and not self.target_ips:
            return True

        src_ip, _, dst_ip, _ = flow

        monitor_match = (
            not self.monitor_ips
            or self._ip_in_list(src_ip, self.monitor_ips)
            or self._ip_in_list(dst_ip, self.monitor_ips)
        )

        target_match = (
            not self.target_ips
            or self._ip_in_list(src_ip, self.target_ips)
            or self._ip_in_list(dst_ip, self.target_ips)
        )

        return monitor_match and target_match  
    
    