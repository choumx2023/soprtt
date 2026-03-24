#!/usr/bin/env python3
"""
简单的 TCP 流量捕获脚本
用于在 Linux 环境下捕获 SSH 和 WWW 流量

使用方法:
    sudo python3 capture_traffic.py -i eth0 -t 300 -o captured_traffic
    
参数:
    -i: 网络接口 (如 eth0, enp3s0)
    -t: 捕获时长 (秒)
    -o: 输出文件名 (不含 .pcap 后缀)
"""

import argparse
import os
import sys
from datetime import datetime
from scapy.all import sniff, wrpcap, TCP


class TrafficCaptureStats:
    """捕获统计信息"""
    
    def __init__(self):
        self.packet_count = 0
        self.ssh_count = 0
        self.www_count = 0
        self.other_count = 0
        self.start_time = None
        
    def process_packet(self, packet):
        """处理单个数据包"""
        if not packet.haslayer(TCP):
            return
        
        self.packet_count += 1
        
        # 按端口分类
        sport = packet[TCP].sport
        dport = packet[TCP].dport
        
        if sport == 22 or dport == 22:
            self.ssh_count += 1
        elif sport in (80, 443) or dport in (80, 443):
            self.www_count += 1
        else:
            self.other_count += 1
        
        # 每 1000 个包打印一次进度
        if self.packet_count % 1000 == 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Packets: {self.packet_count} | "
                  f"Rate: {self.packet_count / max(elapsed, 1):.1f} pkt/s | "
                  f"SSH: {self.ssh_count} | WWW: {self.www_count}")
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "=" * 60)
        print("流量捕获摘要")
        print("=" * 60)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"捕获时长：{elapsed:.1f} 秒")
        print(f"总包数：{self.packet_count}")
        print(f"平均速率：{self.packet_count / max(elapsed, 1):.1f} 包/秒")
        print(f"\n流量分类:")
        print(f"  SSH (端口 22):     {self.ssh_count:>8} 包 ({self.ssh_count/self.packet_count*100:.1f}%)")
        print(f"  WWW (端口 80/443): {self.www_count:>8} 包 ({self.www_count/self.packet_count*100:.1f}%)")
        print(f"  其他流量：         {self.other_count:>8} 包 ({self.other_count/self.packet_count*100:.1f}%)")
        print("=" * 60)


def capture_traffic(interface="eth0", duration=300, output_file="captured_traffic"):
    """
    捕获指定时长的 TCP 流量
    
    Args:
        interface: 网络接口
        duration: 捕获时长 (秒)
        output_file: 输出文件名
    """
    print("=" * 60)
    print("TCP 流量捕获工具")
    print("=" * 60)
    print(f"网络接口：{interface}")
    print(f"捕获时长：{duration} 秒")
    print(f"输出文件：{output_file}.pcap")
    print("=" * 60)
    print("\n开始捕获... (按 Ctrl+C 可提前停止)\n")
    
    stats = TrafficCaptureStats()
    captured_packets = []
    
    def packet_handler(pkt):
        stats.process_packet(pkt)
        captured_packets.append(pkt)
    
    stats.start_time = datetime.now()
    
    try:
        # 开始抓包
        packets = sniff(
            iface=interface,
            filter="tcp",  # 只捕获 TCP
            prn=packet_handler,
            timeout=duration,
            store=True
        )
        
        # 保存到 PCAP 文件
        pcap_path = f"{output_file}.pcap"
        wrpcap(pcap_path, packets)
        
        print(f"\n✓ 已保存 {len(packets)} 个数据包到：{pcap_path}")
        
        # 打印统计
        stats.print_summary()
        
        # 生成使用说明
        print(f"\n下一步操作:")
        print(f"  python experiment/quick_validate.py {pcap_path} -o analysis_output")
        
        return pcap_path
        
    except KeyboardInterrupt:
        print("\n\n用户中断捕获")
        
        if captured_packets:
            pcap_path = f"{output_file}_interrupted.pcap"
            wrpcap(pcap_path, captured_packets)
            print(f"✓ 已保存 {len(captured_packets)} 个数据包到：{pcap_path}")
        
        stats.print_summary()
        return None
        
    except Exception as e:
        print(f"\n✗ 捕获失败：{e}")
        print("\n提示:")
        print("  1. 确保使用 sudo 运行：sudo python3 capture_traffic.py ...")
        print("  2. 检查网络接口名称是否正确")
        print("  3. 确认 scapy 已安装：pip install scapy")
        return None


def list_interfaces():
    """列出可用的网络接口"""
    from scapy.arch import get_if_list
    
    interfaces = get_if_list()
    
    print("\n可用的网络接口:")
    for iface in interfaces:
        print(f"  - {iface}")
    
    return interfaces


def main():
    parser = argparse.ArgumentParser(
        description="简单的 TCP 流量捕获工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 在 eth0 接口捕获 300 秒
  sudo python3 capture_traffic.py -i eth0 -t 300
  
  # 在其他接口捕获
  sudo python3 capture_traffic.py -i enp3s0 -t 600 -o my_capture
  
  # 查看可用接口
  python3 capture_traffic.py --list-interfaces
        """
    )
    
    parser.add_argument(
        "-i", "--interface",
        default="eth0",
        help="网络接口名称 (默认：eth0)"
    )
    
    parser.add_argument(
        "-t", "--time",
        type=int,
        default=300,
        help="捕获时长 (秒，默认：300)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="captured_traffic",
        help="输出文件名 (不含 .pcap 后缀)"
    )
    
    parser.add_argument(
        "--list-interfaces",
        action="store_true",
        help="列出可用的网络接口并退出"
    )
    
    args = parser.parse_args()
    
    if args.list_interfaces:
        list_interfaces()
        return
    
    # 检查是否 root 权限
    if os.geteuid() != 0:
        print("⚠️  警告：需要 root 权限才能捕获网络流量")
        print("请使用 sudo 运行:")
        print(f"  sudo python3 {sys.argv[0]} {' '.join(sys.argv[1:])}")
        print("\n继续运行吗？(y/n): ", end="")
        
        try:
            response = input().lower()
            if response != 'y':
                print("已取消")
                return
        except:
            print("\n已取消")
            return
    
    # 开始捕获
    capture_traffic(
        interface=args.interface,
        duration=args.time,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
