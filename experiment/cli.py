#!/usr/bin/env python3
"""
跨层验证实验工具 - Linux 实际场景版
用于验证不同 ACK 策略下的 MLT 测量精度

支持:
1. 分析现有 PCAP 文件（SSH、WWW 会话）
2. 实时捕获网络流量
3. 生成对比实验报告
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Optional
import matplotlib.pyplot as plt
import numpy as np


def compare_experiments(
    experiment_dirs: List[str],
    output_dir: str = "comparison_output"
):
    """
    对比多个实验的结果
    
    Args:
        experiment_dirs: 实验输出目录列表
        output_dir: 对比结果输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    
    experiments = []
    
    # 加载所有实验的统计数据
    for exp_dir in experiment_dirs:
        stats_path = os.path.join(exp_dir, "statistics.json")
        report_path = os.path.join(exp_dir, "ack_strategy_report.json")
        
        if not os.path.exists(stats_path):
            print(f"[WARN] Skipping {exp_dir}: no statistics.json")
            continue
        
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
        
        report = None
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        
        experiments.append({
            "dir": exp_dir,
            "stats": stats,
            "report": report
        })
    
    if len(experiments) < 2:
        print("[ERROR] Need at least 2 experiments to compare")
        return
    
    print(f"\n===== Experiment Comparison =====")
    print(f"Comparing {len(experiments)} experiments\n")
    
    # 1. 基本统计对比
    print("Basic Statistics:")
    print("-" * 60)
    print(f"{'Metric':<30} ", end="")
    for exp in experiments:
        label = os.path.basename(exp["dir"])
        print(f"{label:<25} ", end="")
    print()
    print("-" * 60)
    
    metrics = [
        ("Total packets", lambda e: e["stats"].get("total_packets", 0)),
        ("MLT samples", lambda e: e["stats"].get("total_mlt_samples", 0)),
        ("Duration (s)", lambda e: e["stats"].get("capture_duration_seconds", 0)),
    ]
    
    for name, getter in metrics:
        print(f"{name:<30} ", end="")
        for exp in experiments:
            val = getter(exp)
            if isinstance(val, float):
                print(f"{val:>20.1f} ", end="")
            else:
                print(f"{val:>20} ", end="")
        print()
    
    # 2. ACK 类型分布对比
    print("\n\nACK Type Distribution:")
    print("-" * 60)
    
    if experiments[0]["report"]:
        type_categories = ["syn_ack", "b2b", "data_immediate", "data_delayed"]
        
        print(f"{'Type':<20} ", end="")
        for exp in experiments:
            label = os.path.basename(exp["dir"])
            print(f"{label:<25} ", end="")
        print()
        print("-" * 60)
        
        for cat in type_categories:
            print(f"{cat:<20} ", end="")
            for exp in experiments:
                if exp["report"] and "classified_counts" in exp["report"]["summary"]:
                    count = exp["report"]["summary"]["classified_counts"].get(cat, 0)
                    total = exp["report"]["summary"]["total_samples"]
                    pct = count / total * 100 if total > 0 else 0
                    print(f"{count:>5} ({pct:>5.1f}%) ", end="")
                else:
                    print(f"{'N/A':>14} ", end="")
            print()
    
    # 3. 准确率对比
    print("\n\nAccuracy Comparison (within 20ms):")
    print("-" * 60)
    
    if experiments[0]["report"] and "delayed_ack_impact" in experiments[0]["report"]:
        type_categories = ["syn_ack", "b2b", "data_immediate", "data_delayed"]
        
        print(f"{'Type':<20} ", end="")
        for exp in experiments:
            label = os.path.basename(exp["dir"])
            print(f"{label:<15} ", end="")
        print()
        print("-" * 60)
        
        for cat in type_categories:
            print(f"{cat:<20} ", end="")
            for exp in experiments:
                if (exp["report"] and 
                    "delayed_ack_impact" in exp["report"] and
                    "categories" in exp["report"]["delayed_ack_impact"]):
                    
                    cat_data = exp["report"]["delayed_ack_impact"]["categories"].get(cat, {})
                    if cat_data.get("count", 0) > 0:
                        acc = cat_data.get("accuracy_within_20ms", 0)
                        print(f"{acc:>13.1f}% ", end="")
                    else:
                        print(f"{'N/A':>15} ", end="")
                else:
                    print(f"{'N/A':>15} ", end="")
            print()
    
    # 4. 应用层面对比（SSH vs WWW）
    print("\n\nApplication-Level Analysis:")
    print("-" * 60)
    
    if experiments[0]["report"] and "application_analysis" in experiments[0]["report"]:
        apps = ["ssh", "www", "other"]
        
        print(f"{'Application':<15} {'Metric':<20} ", end="")
        for exp in experiments:
            label = os.path.basename(exp["dir"])
            print(f"{label:<20} ", end="")
        print()
        print("-" * 60)
        
        for app in apps:
            print(f"{app.upper():<15} {'Sample Count':<20} ", end="")
            for exp in experiments:
                if (exp["report"] and 
                    "application_analysis" in exp["report"] and
                    app in exp["report"]["application_analysis"]):
                    
                    count = exp["report"]["application_analysis"][app].get("total_samples", 0)
                    print(f"{count:>18} ", end="")
                else:
                    print(f"{'N/A':>18} ", end="")
            print()
    
    # 保存对比报告
    comparison_result = {
        "timestamp": datetime.now().isoformat(),
        "experiments": [
            {
                "dir": exp["dir"],
                "stats": exp["stats"],
                "has_report": exp["report"] is not None
            }
            for exp in experiments
        ],
        "comparison_summary": {
            "experiment_count": len(experiments),
            "metrics_compared": ["packets", "samples", "duration", "ack_types", "accuracy"]
        }
    }
    
    result_path = os.path.join(output_dir, "comparison_report.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(comparison_result, f, indent=4, ensure_ascii=False)
    
    print(f"\nComparison report saved to: {result_path}")
    
    return comparison_result


def generate_cdf_plot(
    json_files: List[str],
    labels: List[str],
    output_path: str = "mlt_cdf_comparison.png",
    focus_type: str = "all"
):
    """
    生成 MLT 的 CDF 对比图
    
    Args:
        json_files: MLT JSON 文件列表
        labels: 对应的标签列表
        output_path: 输出路径
        focus_type: 样本类型过滤 (all/syn/b2b/data)
    """
    plt.figure(figsize=(12, 8))
    
    colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6']
    
    for json_file, label, color in zip(json_files, labels, colors):
        if not os.path.exists(json_file):
            print(f"[WARN] File not found: {json_file}")
            continue
        
        with open(json_file, "r", encoding="utf-8") as f:
            samples = json.load(f)
        
        # 过滤样本类型
        if focus_type != "all":
            samples = [s for s in samples if s.get("type") == focus_type]
        
        if not samples:
            print(f"[WARN] No samples in {json_file}" + 
                  (f" (type={focus_type})" if focus_type != "all" else ""))
            continue
        
        mlts = sorted([s["mlt"] * 1000 for s in samples if s.get("mlt")])
        
        if not mlts:
            continue
        
        x = mlts
        y = np.arange(1, len(x) + 1) / len(x)
        
        plt.plot(x, y, label=label, color=color, linewidth=2.5)
        
        # 标注关键分位点
        p50 = np.percentile(mlts, 50)
        p95 = np.percentile(mlts, 95)
        p99 = np.percentile(mlts, 99)
        
        plt.axvline(p95, color=color, linestyle='--', alpha=0.3)
        plt.text(p95, 0.95, f'  P95={p95:.1f}ms', color=color, fontsize=9)
    
    plt.xlabel("MLT (ms)")
    plt.ylabel("CDF")
    plt.title(f"MLT Cumulative Distribution Function" + 
              (f" - {focus_type.upper()} Samples" if focus_type != "all" else ""))
    plt.legend(loc='lower right')
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 1.05)
    plt.xlim(0, None)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"CDF plot saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-layer validation experiment toolkit for Linux environment"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # 1. Analyze PCAP command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze existing PCAP file"
    )
    analyze_parser.add_argument("pcap_file", help="Path to PCAP file")
    analyze_parser.add_argument("-o", "--output", default="experiment_output",
                               help="Output directory")
    analyze_parser.add_argument("--monitor", nargs="*", help="Monitor IPs")
    analyze_parser.add_argument("--target", nargs="*", help="Target IPs")
    analyze_parser.add_argument("--app", choices=["ssh", "www", "all"], default="all",
                               help="Focus application type")
    
    # 2. Compare experiments command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare multiple experiments"
    )
    compare_parser.add_argument("experiment_dirs", nargs="+",
                               help="Experiment output directories")
    compare_parser.add_argument("-o", "--output", default="comparison_output",
                               help="Comparison output directory")
    
    # 3. CDF plot command
    cdf_parser = subparsers.add_parser(
        "cdf",
        help="Generate CDF comparison plot"
    )
    cdf_parser.add_argument("json_files", nargs="+",
                           help="MLT JSON files")
    cdf_parser.add_argument("--labels", nargs="+", required=True,
                           help="Labels for each JSON file")
    cdf_parser.add_argument("-o", "--output", default="mlt_cdf_comparison.png",
                           help="Output plot path")
    cdf_parser.add_argument("--type", dest="sample_type",
                           choices=["all", "syn", "b2b", "data"], default="all",
                           help="Filter by sample type")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        from experiment.ack_analyzer import analyze_pcap_file
        
        analyze_pcap_file(
            args.pcap_file,
            output_dir=args.output,
            monitor_ips=args.monitor,
            target_ips=args.target
        )
        
    elif args.command == "compare":
        compare_experiments(
            args.experiment_dirs,
            output_dir=args.output
        )
        
    elif args.command == "cdf":
        generate_cdf_plot(
            args.json_files,
            args.labels,
            output_path=args.output,
            focus_type=args.sample_type
        )
        
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Analyze a PCAP file")
        print("  python -m experiment.cli analyze capture.pcap -o ssh_experiment")
        print()
        print("  # Compare multiple experiments")
        print("  python -m experiment.compare ssh_experiment www_experiment")
        print()
        print("  # Generate CDF plot")
        print("  python -m experiment.cdf exp1/mlt.json exp2/mlt.json --labels SSH WWW")


if __name__ == "__main__":
    main()
