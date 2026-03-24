#!/usr/bin/env python3
"""
快速验证脚本 - 使用现有 PCAP 文件演示 ACK 策略分析
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment.ack_analyzer import ACKStrategyAnalyzer, analyze_pcap_file
from core.engine import MLTEngine


def quick_validate(pcap_path: str, output_dir: str = "quick_validation"):
    """
    快速验证现有 PCAP 文件
    
    Args:
        pcap_path: PCAP 文件路径
        output_dir: 输出目录
    """
    if not os.path.exists(pcap_path):
        print(f"[ERROR] PCAP file not found: {pcap_path}")
        return
    
    print("=" * 70)
    print("跨层验证实验 - ACK 策略分析")
    print("=" * 70)
    print(f"\n[*] Input PCAP: {pcap_path}")
    print(f"[*] Output directory: {output_dir}\n")
    
    # 使用 engine 处理 PCAP
    engine = MLTEngine()
    
    print("[*] Processing PCAP file...")
    result = engine.run(pcap_path, output_dir=output_dir)
    
    print(f"\n[*] Total packets processed: {result['packet_count']}")
    print(f"[*] MLT samples collected: {result['filtered_total_samples']}")
    
    # 创建 ACK 分析器
    analyzer = ACKStrategyAnalyzer(engine.collector.samples)
    
    # 生成分析报告
    print("\n[*] Analyzing ACK strategies...")
    report = analyzer.generate_report()
    
    # 保存报告
    report_path = os.path.join(output_dir, "ack_strategy_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    print(f"[*] Report saved to: {report_path}")
    
    # 绘制对比图
    plot_path = os.path.join(output_dir, "ack_strategy_comparison.png")
    analyzer.plot_comparison(plot_path)
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("验证结果摘要")
    print("=" * 70)
    
    summary = report["summary"]
    print(f"\n总 MLT 样本数：{summary['total_samples']}")
    print("\nACK 类型分布:")
    for ack_type, count in summary["classified_counts"].items():
        pct = count / summary["total_samples"] * 100 if summary["total_samples"] > 0 else 0
        print(f"  {ack_type:<20} {count:>6} ({pct:>5.1f}%)")
    
    # 准确率统计
    impact = report["delayed_ack_impact"]
    if "categories" in impact:
        print("\n测量精度 (误差 < 20ms):")
        for ack_type, data in impact["categories"].items():
            if data.get("count", 0) > 0:
                acc = data.get("accuracy_within_20ms", 0)
                avg_dev = data.get("avg_deviation_ms", 0)
                print(f"  {ack_type:<20} {acc:>6.1f}%  (平均偏差：{avg_dev:>6.1f}ms)")
    
    # 应用层面分析
    app_analysis = report["application_analysis"]
    print("\n应用场景分布:")
    for app, data in app_analysis.items():
        if data["total_samples"] > 0:
            print(f"  {app.upper():<20} {data['total_samples']:>6} 样本")
            if data["mlt_statistics"]:
                stats = data["mlt_statistics"]
                print(f"                     P50={stats['median']*1000:>7.1f}ms, "
                      f"P95={stats['p95']*1000:>7.1f}ms, "
                      f"P99={stats['p99']*1000:>7.1f}ms")
    
    # 建议
    if report["recommendations"]:
        print("\n实验建议:")
        for rec in report["recommendations"]:
            print(f"  • {rec}")
    
    print("\n" + "=" * 70)
    print(f"详细报告已保存至：{output_dir}/")
    print(f"  - JSON 报告：ack_strategy_report.json")
    print(f"  - 对比图表：ack_strategy_comparison.png")
    print(f"  - 原始数据：mlt_full_series.csv / mlt_full_series.json")
    print("=" * 70)
    
    return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Quick validation tool for ACK strategy analysis"
    )
    parser.add_argument(
        "pcap_file",
        help="Path to PCAP file"
    )
    parser.add_argument(
        "-o", "--output",
        default="quick_validation",
        help="Output directory (default: quick_validation)"
    )
    
    args = parser.parse_args()
    
    quick_validate(args.pcap_file, output_dir=args.output)


if __name__ == "__main__":
    main()
