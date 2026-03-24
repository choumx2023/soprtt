#!/usr/bin/env python3
"""
Linux 环境下的实时 TCP 监控探针
用于捕获 SSH 和 WWW 会话数据，支持被动监听和实时分析
"""

import argparse
import json
import os
import sys
import signal
from datetime import datetime
from typing import Optional, List, Dict
from scapy.all import sniff, TCP, IP
from core.engine import MLTEngine
from core.collector import MLTCollector


class LiveTCPMonitor:
    """
    实时 TCP 流量监控器
    部署在 Linux 网卡接口上，被动监听 TCP 报文
    """
    
    def __init__(
        self,
        interface: str = "eth0",
        monitor_ips: Optional[List[str]] = None,
        target_ips: Optional[List[str]] = None,
        output_dir: str = "live_outputs"
    ):
        self.interface = interface
        self.monitor_ips = monitor_ips
        self.target_ips = target_ips
        self.output_dir = output_dir
        
        self.engine = MLTEngine(
            monitor_ips=monitor_ips,
            target_ips=target_ips
        )
        
        self.running = False
        self.packet_count = 0
        self.start_time = None
        
        os.makedirs(output_dir, exist_ok=True)
    
    def _packet_callback(self, packet):
        """处理每个捕获的数据包"""
        if not (IP in packet and TCP in packet):
            return
        
        self.packet_count += 1
        
        # 交给 engine 处理
        self.engine.process_packet(packet)
        
        # 定期输出进度
        if self.packet_count % 1000 == 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Packets: {self.packet_count} | "
                  f"Rate: {self.packet_count / max(elapsed, 1):.1f} pkt/s | "
                  f"MLT samples: {len(self.engine.collector.samples)}")
    
    def start(self, duration: Optional[int] = None, count: Optional[int] = None):
        """
        开始抓包
        
        Args:
            duration: 抓包时长（秒），None 表示无限
            count: 抓包数量，None 表示无限
        """
        print(f"[*] Starting live TCP monitor on interface: {self.interface}")
        print(f"[*] Monitor IPs: {self.monitor_ips or 'ALL'}")
        print(f"[*] Target IPs: {self.target_ips or 'ALL'}")
        print(f"[*] Output directory: {self.output_dir}")
        print("[*] Press Ctrl+C to stop...")
        
        self.running = True
        self.start_time = datetime.now()
        
        # 设置信号处理
        def signal_handler(sig, frame):
            print("\n[*] Stopping capture...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # 开始抓包
        try:
            sniff(
                iface=self.interface,
                filter="tcp",
                prn=self._packet_callback,
                store=False,
                timeout=duration,
                count=count if count else 0
            )
        except Exception as e:
            print(f"[ERROR] Capture failed: {e}")
            print("[HINT] You may need root privileges: sudo python3 linux_capture.py ...")
            return
        
        # 保存结果
        self._save_results()
    
    def _save_results(self):
        """保存实验结果"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print(f"\n===== Capture Summary =====")
        print(f"Duration: {elapsed:.1f}s")
        print(f"Total packets: {self.packet_count}")
        print(f"MLT samples: {len(self.engine.collector.samples)}")
        
        # 导出 CSV
        csv_path = os.path.join(self.output_dir, "mlt_live.csv")
        self.engine.collector.export_full_series(csv_path)
        
        # 导出 JSON
        json_path = os.path.join(self.output_dir, "mlt_live.json")
        self.engine.collector.export_json(json_path)
        
        # 绘制时序图
        plot_path = os.path.join(self.output_dir, "mlt_live.png")
        self.engine.collector.plot_mlt_time_series(plot_path)
        
        # 生成统计报告
        stats = self._generate_statistics()
        stats_path = os.path.join(self.output_dir, "statistics.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
        
        print(f"\nResults saved to: {self.output_dir}/")
        print(f"  - CSV: {csv_path}")
        print(f"  - JSON: {json_path}")
        print(f"  - Plot: {plot_path}")
        print(f"  - Statistics: {stats_path}")
    
    def _generate_statistics(self) -> Dict:
        """生成统计数据"""
        samples = self.engine.collector.samples
        
        # 按类型分类
        type_stats = {}
        for s in samples:
            t = s.get("type", "unknown")
            if t not in type_stats:
                type_stats[t] = {"count": 0, "mlts": []}
            type_stats[t]["count"] += 1
            if s.get("mlt") is not None:
                type_stats[t]["mlts"].append(s["mlt"])
        
        # 计算统计量
        for t in type_stats:
            mlts = sorted(type_stats[t]["mlts"])
            if mlts:
                type_stats[t]["min"] = round(min(mlts), 6)
                type_stats[t]["max"] = round(max(mlts), 6)
                type_stats[t]["avg"] = round(sum(mlts) / len(mlts), 6)
                type_stats[t]["median"] = round(mlts[len(mlts) // 2], 6)
                type_stats[t]["p95"] = round(mlts[int(len(mlts) * 0.95)], 6)
                type_stats[t]["p99"] = round(mlts[int(len(mlts) * 0.99)], 6)
        
        # 按应用分类（SSH vs WWW）
        app_stats = {"ssh": {"count": 0}, "www": {"count": 0}, "other": {"count": 0}}
        
        for s in samples:
            ack_sender = s.get("ack_sender", "")
            flow = s.get("flow", ())
            
            # 根据端口判断应用类型
            if flow:
                src_port, dst_port = flow[1], flow[3]
                if src_port == 22 or dst_port == 22:
                    app_stats["ssh"]["count"] += 1
                elif src_port in (80, 443) or dst_port in (80, 443):
                    app_stats["www"]["count"] += 1
                else:
                    app_stats["other"]["count"] += 1
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "capture_duration_seconds": round(elapsed, 1),
            "total_packets": self.packet_count,
            "total_mlt_samples": len(samples),
            "type_statistics": type_stats,
            "application_statistics": app_stats,
            "timestamp": datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(
        description="Live TCP monitor for Linux environment"
    )
    parser.add_argument(
        "-i", "--interface",
        default="eth0",
        help="Network interface to monitor (default: eth0)"
    )
    parser.add_argument(
        "--monitor",
        nargs="*",
        help="Monitor IP addresses"
    )
    parser.add_argument(
        "--target",
        nargs="*",
        help="Target IP addresses"
    )
    parser.add_argument(
        "-o", "--output",
        default="live_outputs",
        help="Output directory (default: live_outputs)"
    )
    parser.add_argument(
        "-t", "--time",
        type=int,
        default=None,
        help="Capture duration in seconds"
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=None,
        help="Number of packets to capture"
    )
    
    args = parser.parse_args()
    
    monitor = LiveTCPMonitor(
        interface=args.interface,
        monitor_ips=args.monitor,
        target_ips=args.target,
        output_dir=args.output
    )
    
    monitor.start(duration=args.time, count=args.count)


if __name__ == "__main__":
    main()
