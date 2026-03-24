#!/usr/bin/env python3
"""
分析捕获的流量，按应用场景 (SSH/WWW) 分类统计

使用方法:
    python analyze_by_app.py analysis_output/mlt_full_series.json
"""

import json
import sys
import os
from collections import defaultdict


def classify_flow_by_port(src_port, dst_port):
    """根据端口分类流量"""
    if src_port == 22 or dst_port == 22:
        return "SSH"
    elif src_port in (80, 443) or dst_port in (80, 443):
        return "WWW"
    else:
        return "OTHER"


def analyze_mlt_samples(json_file):
    """分析 MLT 样本"""
    
    print("=" * 70)
    print("MLT 样本分析 - 按应用场景分类")
    print("=" * 70)
    
    # 读取 JSON 文件
    if not os.path.exists(json_file):
        print(f"✗ 文件不存在：{json_file}")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        samples = json.load(f)
    
    print(f"\n总样本数：{len(samples)}")
    
    # 按应用分类
    app_stats = {
        "SSH": {"count": 0, "mlts": [], "types": defaultdict(int)},
        "WWW": {"count": 0, "mlts": [], "types": defaultdict(int)},
        "OTHER": {"count": 0, "mlts": [], "types": defaultdict(int)}
    }
    
    # 统计每个样本
    for s in samples:
        flow = s.get("flow", ())
        if len(flow) >= 4:
            src_port, dst_port = flow[1], flow[3]
            app_type = classify_flow_by_port(src_port, dst_port)
            
            app_stats[app_type]["count"] += 1
            
            if s.get("mlt") is not None:
                app_stats[app_type]["mlts"].append(s["mlt"])
            
            sample_type = s.get("type", "unknown")
            app_stats[app_type]["types"][sample_type] += 1
    
    # 打印统计结果
    print("\n" + "=" * 70)
    print("应用场景分布")
    print("=" * 70)
    
    for app_type in ["SSH", "WWW", "OTHER"]:
        stats = app_stats[app_type]
        count = stats["count"]
        pct = count / len(samples) * 100 if len(samples) > 0 else 0
        
        print(f"\n{app_type}:")
        print(f"  样本数：{count} ({pct:.1f}%)")
        
        if stats["mlts"]:
            mlts = sorted(stats["mlts"])
            n = len(mlts)
            
            print(f"  MLT 统计:")
            print(f"    最小值：{min(mlts)*1000:.3f} ms")
            print(f"    最大值：{max(mlts)*1000:.3f} ms")
            print(f"    平均值：{sum(mlts)/n*1000:.3f} ms")
            print(f"    中位数：{mlts[n//2]*1000:.3f} ms")
            print(f"    P95:    {mlts[int(n*0.95)]*1000:.3f} ms")
            print(f"    P99:    {mlts[min(int(n*0.99), n-1)]*1000:.3f} ms")
        
        if stats["types"]:
            print(f"  ACK 类型分布:")
            for ack_type, type_count in sorted(stats["types"].items()):
                type_pct = type_count / count * 100 if count > 0 else 0
                print(f"    {ack_type}: {type_count} ({type_pct:.1f}%)")
    
    # 生成对比表格
    print("\n" + "=" * 70)
    print("对比摘要表")
    print("=" * 70)
    
    print(f"\n{'指标':<20} {'SSH':>15} {'WWW':>15} {'OTHER':>15}")
    print("-" * 70)
    
    # 样本数
    row = f"{'样本数':<20}"
    for app in ["SSH", "WWW", "OTHER"]:
        row += f" {app_stats[app]['count']:>14}"
    print(row)
    
    # 计算并显示 P95
    row = f"{'P95 (ms)':<20}"
    for app in ["SSH", "WWW", "OTHER"]:
        mlts = sorted(app_stats[app]["mlts"])
        if mlts:
            p95 = mlts[int(len(mlts)*0.95)] * 1000
            row += f" {p95:>13.2f}"
        else:
            row += f" {'N/A':>14}"
    print(row)
    
    # Delayed ACK 比例
    row = f"{'Delayed ACK %':<20}"
    for app in ["SSH", "WWW", "OTHER"]:
        types = app_stats[app]["types"]
        total = app_stats[app]["count"]
        delayed = types.get("data", 0)  # data 类型可能包含 Delayed ACK
        if total > 0:
            # 简单估算：假设 data 类型中有一部分是 Delayed ACK
            delayed_pct = delayed / total * 100
            row += f" {delayed_pct:>13.1f}%"
        else:
            row += f" {'N/A':>14}"
    print(row)
    
    print("\n" + "=" * 70)
    
    # 生成简化版报告（用于论文）
    print("\n论文章节可用数据:")
    print("-" * 70)
    
    for app in ["SSH", "WWW"]:
        stats = app_stats[app]
        if stats["count"] > 0:
            print(f"\n**{app} 流量**:")
            print(f"  - 总样本数：{stats['count']}")
            
            mlts = sorted(stats["mlts"])
            if mlts:
                print(f"  - P50: {mlts[len(mlts)//2]*1000:.2f} ms")
                print(f"  - P95: {mlts[int(len(mlts)*0.95)]*1000:.2f} ms")
                print(f"  - P99: {mlts[min(int(len(mlts)*0.99), len(mlts)-1)]*1000:.2f} ms")
            
            # ACK 类型分布
            print(f"  - ACK 类型:")
            for ack_type, count in sorted(stats["types"].items()):
                pct = count / stats["count"] * 100
                print(f"    · {ack_type}: {count} ({pct:.1f}%)")
    
    # 保存分析结果
    output_json = json_file.replace('.json', '_by_app.json')
    result = {
        "source_file": json_file,
        "total_samples": len(samples),
        "application_breakdown": {}
    }
    
    for app, stats in app_stats.items():
        mlts = sorted(stats["mlts"])
        n = len(mlts)
        
        result["application_breakdown"][app] = {
            "count": stats["count"],
            "percentage": stats["count"] / len(samples) * 100 if len(samples) > 0 else 0,
            "type_distribution": dict(stats["types"]),
            "mlt_statistics": {
                "min": min(mlts) * 1000 if mlts else None,
                "max": max(mlts) * 1000 if mlts else None,
                "mean": sum(mlts) / n * 1000 if mlts else None,
                "median": mlts[n // 2] * 1000 if mlts else None,
                "p95": mlts[int(n * 0.95)] * 1000 if mlts else None,
                "p99": mlts[min(int(n * 0.99), n - 1)] * 1000 if mlts else None,
            } if mlts else None
        }
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"\n✓ 分析结果已保存到：{output_json}")
    
    return result


def main():
    if len(sys.argv) < 2:
        print("用法：python analyze_by_app.py <mlt_full_series.json>")
        print("\n示例:")
        print("  python analyze_by_app.py captured_traffic_analysis/mlt_full_series.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    analyze_mlt_samples(json_file)


if __name__ == "__main__":
    main()
