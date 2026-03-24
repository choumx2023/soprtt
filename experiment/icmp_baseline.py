#!/usr/bin/env python3
"""
ICMP Baseline 测量工具

用途：
- 使用 ICMP (ping) 测量网络延迟作为"地面真值"
- 与 TCP ACK 方法的测量结果对比
- 评估 TCP ACK 测量方法的准确性

使用方法:
    sudo python3 icmp_baseline.py --target 192.168.1.100 --count 100
"""

import argparse
import subprocess
import re
import time
import json
from datetime import datetime
from typing import List, Dict


class ICMPPinger:
    """ICMP Ping 封装"""
    
    def __init__(self, target: str, count: int = 10):
        self.target = target
        self.count = count
        self.results = []
        
    def ping(self) -> Dict:
        """执行一次 ping 并返回结果"""
        try:
            # 执行 ping 命令
            cmd = ['ping', '-c', '1', '-W', '2', self.target]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3
            )
            
            # 解析输出
            output = result.stdout + result.stderr
            
            # 提取延迟时间
            match = re.search(r'time[=<](\d+\.?\d*)\s*ms', output)
            if match:
                rtt = float(match.group(1))
                return {
                    'success': True,
                    'rtt_ms': rtt,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'rtt_ms': None,
                    'error': 'No RTT found',
                    'timestamp': datetime.now().isoformat()
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'rtt_ms': None,
                'error': 'Timeout',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'rtt_ms': None,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def multi_ping(self) -> List[Dict]:
        """执行多次 ping"""
        print(f"Pinging {self.target} ({self.count} times)...")
        
        results = []
        success_count = 0
        
        for i in range(self.count):
            result = self.ping()
            results.append(result)
            
            if result['success']:
                success_count += 1
                print(f"  [{i+1}/{self.count}] RTT: {result['rtt_ms']:.2f} ms")
            else:
                print(f"  [{i+1}/{self.count}] Failed: {result.get('error', 'Unknown')}")
            
            # 间隔 0.5 秒
            time.sleep(0.5)
        
        # 统计
        successful_rtts = [r['rtt_ms'] for r in results if r['success']]
        
        stats = {
            'target': self.target,
            'total_pings': self.count,
            'successful_pings': success_count,
            'loss_rate': (self.count - success_count) / self.count * 100,
            'rtt_stats': None
        }
        
        if successful_rtts:
            import statistics
            stats['rtt_stats'] = {
                'min': min(successful_rtts),
                'max': max(successful_rtts),
                'mean': statistics.mean(successful_rtts),
                'median': statistics.median(successful_rtts),
                'stdev': statistics.stdev(successful_rtts) if len(successful_rtts) > 1 else 0,
                'p95': sorted(successful_rtts)[int(len(successful_rtts) * 0.95)] if len(successful_rtts) >= 20 else max(successful_rtts),
                'p99': sorted(successful_rtts)[int(len(successful_rtts) * 0.99)] if len(successful_rtts) >= 100 else max(successful_rtts)
            }
        
        return results, stats


def main():
    parser = argparse.ArgumentParser(
        description='ICMP Baseline 测量工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Ping 目标服务器 100 次
  sudo python3 icmp_baseline.py --target 192.168.1.100 --count 100
  
  # 持续 Ping（用于对照实验期间）
  python3 icmp_baseline.py --target 192.168.1.100 --continuous --duration 300
  
  # 保存结果到 JSON
  python3 icmp_baseline.py --target 192.168.1.100 --count 100 --output icmp_baseline.json
        """
    )
    
    parser.add_argument(
        '--target',
        type=str,
        required=True,
        help='目标 IP 地址或主机名'
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Ping 的次数 (默认：10)'
    )
    
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='持续 Ping 模式'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='持续时间（秒），仅 continuous 模式 (默认：300)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='保存结果到 JSON 文件'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("ICMP Baseline 测量")
    print("=" * 70)
    print(f"目标：{args.target}")
    print(f"次数：{args.count}")
    print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    pinger = ICMPPinger(args.target, args.count)
    
    if args.continuous:
        # 持续 Ping 模式
        print(f"持续 Ping {args.duration} 秒...\n")
        
        all_results = []
        start_time = time.time()
        
        while time.time() - start_time < args.duration:
            results, stats = pinger.multi_ping()
            all_results.extend(results)
            
            print(f"\n[{len(all_results)} samples]")
            print(f"平均 RTT: {stats['rtt_stats']['mean']:.2f} ms ± {stats['rtt_stats']['stdev']:.2f} ms")
            print(f"丢包率：{stats['loss_rate']:.1f}%\n")
            
            time.sleep(5)  # 每轮间隔 5 秒
        
        # 最终统计
        final_rtts = [r['rtt_ms'] for r in all_results if r['success']]
        import statistics
        
        print("\n" + "=" * 70)
        print("最终统计")
        print("=" * 70)
        print(f"总样本数：{len(final_rtts)}")
        print(f"平均 RTT: {statistics.mean(final_rtts):.2f} ms")
        print(f"中位数：{statistics.median(final_rtts):.2f} ms")
        print(f"标准差：{statistics.stdev(final_rtts):.2f} ms")
        print(f"P95: {sorted(final_rtts)[int(len(final_rtts)*0.95)]:.2f} ms")
        print(f"P99: {sorted(final_rtts)[int(len(final_rtts)*0.99)]:.2f} ms")
        
    else:
        # 单次测量模式
        results, stats = pinger.multi_ping()
        
        print("\n" + "=" * 70)
        print("统计结果")
        print("=" * 70)
        
        if stats['rtt_stats']:
            s = stats['rtt_stats']
            print(f"成功次数：{stats['successful_pings']}/{stats['total_pings']}")
            print(f"丢包率：{stats['loss_rate']:.1f}%")
            print(f"最小 RTT: {s['min']:.2f} ms")
            print(f"最大 RTT: {s['max']:.2f} ms")
            print(f"平均 RTT: {s['mean']:.2f} ms")
            print(f"中位数：{s['median']:.2f} ms")
            print(f"标准差：{s['stdev']:.2f} ms")
            print(f"P95: {s['p95']:.2f} ms")
            print(f"P99: {s['p99']:.2f} ms")
        else:
            print("❌ 没有成功的 Ping")
    
    # 保存结果
    if args.output:
        output_data = {
            'experiment_info': {
                'target': args.target,
                'count': args.count,
                'start_time': datetime.now().isoformat(),
                'tool': 'ICMP Baseline Measurer'
            },
            'results': results,
            'statistics': stats
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✓ 结果已保存到：{args.output}")


if __name__ == "__main__":
    main()
