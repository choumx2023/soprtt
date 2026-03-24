#!/usr/bin/env python3
"""
ACK 策略分析器
用于分析不同类型的 ACK 行为及其对 MLT 测量精度的影响

识别以下 ACK 类型：
1. Immediate ACK - 立即确认（SYN-ACK, Back-to-Back）
2. Delayed ACK - 延迟确认（普通数据段，等待最多 500ms）
3. Piggyback ACK - 捎带确认（双向数据传输时）
"""

import json
import os
from collections import defaultdict
from typing import List, Dict, Tuple
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats


class ACKStrategyAnalyzer:
    """
    ACK 策略分析器
    分析不同场景下的 ACK 行为特征
    """
    
    def __init__(self, samples: List[Dict]):
        self.samples = samples
        self.analysis_results = {}
        
    def classify_samples(self) -> Dict[str, List[Dict]]:
        """
        将样本按类型分类
        """
        classified = {
            "syn_ack": [],      # SYN-ACK（最可靠）
            "b2b": [],          # Back-to-Back（可靠）
            "data_immediate": [],  # 普通数据段的立即 ACK
            "data_delayed": [],    # 普通数据段的 Delayed ACK
        }
        
        for s in self.samples:
            sample_type = s.get("type", "")
            
            if sample_type == "syn":
                classified["syn_ack"].append(s)
            elif sample_type == "b2b":
                classified["b2b"].append(s)
            elif sample_type == "data":
                # 进一步判断是否为 Delayed ACK
                mlt = s.get("mlt", 0)
                
                # Delayed ACK 通常等待 40-500ms
                # 如果 MLT 显著大于基线，可能是 Delayed ACK
                if mlt > 0.04:  # 40ms 阈值
                    classified["data_delayed"].append(s)
                else:
                    classified["data_immediate"].append(s)
        
        return classified
    
    def analyze_by_application(
        self, 
        classified_samples: Dict[str, List[Dict]]
    ) -> Dict[str, Dict]:
        """
        按应用场景（SSH vs WWW）分析 ACK 行为
        """
        app_analysis = {
            "ssh": {"total": 0, "types": defaultdict(int), "mlts": []},
            "www": {"total": 0, "types": defaultdict(int), "mlts": []},
            "other": {"total": 0, "types": defaultdict(int), "mlts": []}
        }
        
        for category, samples in classified_samples.items():
            for s in samples:
                flow = s.get("flow", ())
                if not flow:
                    continue
                
                src_port, dst_port = flow[1], flow[3]
                
                # 判断应用类型
                if src_port == 22 or dst_port == 22:
                    app = "ssh"
                elif src_port in (80, 443) or dst_port in (80, 443):
                    app = "www"
                else:
                    app = "other"
                
                app_analysis[app]["total"] += 1
                app_analysis[app]["types"][category] += 1
                
                if s.get("mlt") is not None:
                    app_analysis[app]["mlts"].append(s["mlt"])
        
        # 转换为普通字典并计算统计量
        result = {}
        for app, data in app_analysis.items():
            mlts = sorted(data["mlts"])
            result[app] = {
                "total_samples": data["total"],
                "type_distribution": dict(data["types"]),
                "mlt_statistics": self._compute_mlt_stats(mlts) if mlts else None
            }
        
        return result
    
    def _compute_mlt_stats(self, mlts: List[float]) -> Dict:
        """计算 MLT 的统计量"""
        if not mlts:
            return {}
        
        mlts = sorted(mlts)
        n = len(mlts)
        
        return {
            "count": n,
            "min": round(min(mlts), 6),
            "max": round(max(mlts), 6),
            "mean": round(sum(mlts) / n, 6),
            "median": round(mlts[n // 2], 6),
            "p90": round(mlts[int(n * 0.90)], 6),
            "p95": round(mlts[int(n * 0.95)], 6),
            "p99": round(mlts[min(int(n * 0.99), n - 1)], 6),
            "std": round(np.std(mlts), 6) if len(mlts) > 1 else 0
        }
    
    def detect_delayed_ack_impact(self) -> Dict:
        """
        检测 Delayed ACK 对测量精度的影响
        """
        classified = self.classify_samples()
        
        # 提取各类样本的 MLT 值
        syn_mlts = [s["mlt"] for s in classified["syn_ack"] if s.get("mlt")]
        b2b_mlts = [s["mlt"] for s in classified["b2b"] if s.get("mlt")]
        data_imm_mlts = [s["mlt"] for s in classified["data_immediate"] if s.get("mlt")]
        data_del_mlts = [s["mlt"] for s in classified["data_delayed"] if s.get("mlt")]
        
        # 使用 SYN-ACK 和 B2B 作为基准（最可靠）
        baseline_mlts = syn_mlts + b2b_mlts
        if not baseline_mlts:
            return {"error": "No reliable baseline samples"}
        
        baseline = np.percentile(baseline_mlts, 5)  # 用 5% 分位作为基线
        
        analysis = {
            "baseline_mlt": round(baseline, 6),
            "baseline_source": f"{len(baseline_mlts)} syn/b2b samples",
            "categories": {}
        }
        
        # 分析每类样本相对基线的偏差
        for cat_name, cat_mlts in [
            ("syn_ack", syn_mlts),
            ("b2b", b2b_mlts),
            ("data_immediate", data_imm_mlts),
            ("data_delayed", data_del_mlts)
        ]:
            if not cat_mlts:
                analysis["categories"][cat_name] = {
                    "count": 0,
                    "note": "No samples"
                }
                continue
            
            deviations = [m - baseline for m in cat_mlts]
            avg_deviation = np.mean(deviations)
            std_deviation = np.std(deviations)
            
            # 计算准确率（误差 < 20ms 视为准确）
            accurate_count = sum(1 for d in deviations if abs(d) < 0.02)
            accuracy = accurate_count / len(cat_mlts) * 100
            
            analysis["categories"][cat_name] = {
                "count": len(cat_mlts),
                "avg_deviation_ms": round(avg_deviation * 1000, 2),
                "std_deviation_ms": round(std_deviation * 1000, 2),
                "accuracy_within_20ms": round(accuracy, 2),
                "p50_deviation_ms": round(np.percentile(deviations, 50) * 1000, 2),
                "p95_deviation_ms": round(np.percentile(deviations, 95) * 1000, 2),
            }
        
        return analysis
    
    def generate_report(self) -> Dict:
        """生成完整分析报告"""
        classified = self.classify_samples()
        
        report = {
            "summary": {
                "total_samples": len(self.samples),
                "classified_counts": {
                    k: len(v) for k, v in classified.items()
                }
            },
            "delayed_ack_impact": self.detect_delayed_ack_impact(),
            "application_analysis": self.analyze_by_application(classified),
            "recommendations": []
        }
        
        # 生成建议
        impact = report["delayed_ack_impact"]
        if "categories" in impact:
            data_delayed = impact["categories"].get("data_delayed", {})
            if data_delayed.get("count", 0) > 0:
                accuracy = data_delayed.get("accuracy_within_20ms", 0)
                if accuracy < 50:
                    report["recommendations"].append(
                        "Delayed ACK samples show low accuracy (< 50%). "
                        "Consider filtering them out for precise measurements."
                    )
        
        syn_ack_acc = impact.get("categories", {}).get("syn_ack", {}).get("accuracy_within_20ms", 0)
        if syn_ack_acc >= 95:
            report["recommendations"].append(
                "SYN-ACK samples are highly reliable. "
                "Recommended as primary measurement source."
            )
        
        return report
    
    def plot_comparison(self, output_path: str = "ack_strategy_comparison.png"):
        """绘制对比图"""
        classified = self.classify_samples()
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        categories = ["syn_ack", "b2b", "data_immediate", "data_delayed"]
        colors = ["#2ecc71", "#3498db", "#f39c12", "#e74c3c"]
        labels = ["SYN-ACK", "Back-to-Back", "Data (Immediate)", "Data (Delayed)"]
        
        # 1. 样本数量分布
        ax1 = axes[0, 0]
        counts = [len(classified[cat]) for cat in categories]
        bars = ax1.bar(labels, counts, color=colors)
        ax1.set_ylabel("Sample Count")
        ax1.set_title("Distribution of ACK Types")
        ax1.tick_params(axis='x', rotation=15)
        
        for bar, count in zip(bars, counts):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    str(count), ha='center', va='bottom', fontsize=9)
        
        # 2. MLT 累积分布函数 (CDF)
        ax2 = axes[0, 1]
        for cat, color, label in zip(categories, colors, labels):
            mlts = sorted([s["mlt"] for s in classified[cat] if s.get("mlt")])
            if mlts:
                x = np.sort(mlts)
                y = np.arange(1, len(x) + 1) / len(x)
                ax2.plot(x * 1000, y, label=label, color=color, linewidth=2)
        
        ax2.set_xlabel("MLT (ms)")
        ax2.set_ylabel("CDF")
        ax2.set_title("MLT Cumulative Distribution by ACK Type")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 箱线图对比
        ax3 = axes[1, 0]
        data_to_plot = []
        plot_labels = []
        for cat, color, label in zip(categories, colors, labels):
            mlts = [s["mlt"] * 1000 for s in classified[cat] if s.get("mlt")]
            if mlts:
                data_to_plot.append(mlts)
                plot_labels.append(label)
        
        if data_to_plot:
            bp = ax3.boxplot(data_to_plot, labels=plot_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors[:len(data_to_plot)]):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            ax3.set_ylabel("MLT (ms)")
            ax3.set_title("MLT Distribution Comparison")
            ax3.tick_params(axis='x', rotation=15)
        
        # 4. 准确率对比
        ax4 = axes[1, 1]
        impact = self.detect_delayed_ack_impact()
        
        accuracies = []
        acc_labels = []
        if "categories" in impact:
            for cat, color, label in zip(categories, colors, labels):
                cat_data = impact["categories"].get(cat, {})
                if cat_data.get("count", 0) > 0:
                    acc = cat_data.get("accuracy_within_20ms", 0)
                    accuracies.append(acc)
                    acc_labels.append(label)
        
        if accuracies:
            bars = ax4.bar(acc_labels, accuracies, color=colors[:len(accuracies)])
            ax4.set_ylabel("Accuracy within 20ms (%)")
            ax4.set_title("Measurement Accuracy by ACK Type")
            ax4.set_ylim(0, 105)
            ax4.tick_params(axis='x', rotation=15)
            ax4.axhline(y=95, color='r', linestyle='--', label="95% threshold")
            ax4.legend()
            
            for bar, acc in zip(bars, accuracies):
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                        f"{acc:.1f}%", ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        print(f"Comparison plot saved to: {output_path}")


def analyze_pcap_file(
    pcap_path: str,
    output_dir: str = "ack_analysis_output",
    monitor_ips: List[str] = None,
    target_ips: List[str] = None
):
    """
    分析 PCAP 文件中的 ACK 策略
    
    Args:
        pcap_path: PCAP 文件路径
        output_dir: 输出目录
        monitor_ips: 监控 IP 列表
        target_ips: 目标 IP 列表
    """
    from core.engine import MLTEngine
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[*] Analyzing PCAP: {pcap_path}")
    
    # 使用 engine 处理
    engine = MLTEngine(
        monitor_ips=monitor_ips,
        target_ips=target_ips
    )
    
    result = engine.run(pcap_path, output_dir=output_dir)
    
    # 创建分析器
    analyzer = ACKStrategyAnalyzer(engine.collector.samples)
    
    # 生成报告
    report = analyzer.generate_report()
    
    # 保存报告
    report_path = os.path.join(output_dir, "ack_strategy_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    print(f"\n[*] ACK strategy report saved to: {report_path}")
    
    # 绘制对比图
    plot_path = os.path.join(output_dir, "ack_strategy_comparison.png")
    analyzer.plot_comparison(plot_path)
    
    # 打印摘要
    print("\n===== ACK Strategy Analysis Summary =====")
    print(f"Total MLT samples: {report['summary']['total_samples']}")
    print("\nClassified counts:")
    for cat, count in report['summary']['classified_counts'].items():
        print(f"  {cat}: {count}")
    
    impact = report['delayed_ack_impact']
    if "categories" in impact:
        print("\nAccuracy (within 20ms):")
        for cat, data in impact["categories"].items():
            if data.get("count", 0) > 0:
                acc = data.get("accuracy_within_20ms", 0)
                print(f"  {cat}: {acc}%")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
    
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ACK Strategy Analyzer")
    parser.add_argument("pcap_file", help="Path to PCAP file")
    parser.add_argument("-o", "--output", default="ack_analysis_output",
                       help="Output directory")
    parser.add_argument("--monitor", nargs="*", help="Monitor IPs")
    parser.add_argument("--target", nargs="*", help="Target IPs")
    
    args = parser.parse_args()
    
    analyze_pcap_file(
        args.pcap_file,
        output_dir=args.output,
        monitor_ips=args.monitor,
        target_ips=args.target
    )
