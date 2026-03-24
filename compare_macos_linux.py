#!/usr/bin/env python3
"""
对比 macOS 和 Linux 环境下的 MLT 测量结果

使用方法:
    python3 compare_macos_linux.py analysis_1800/ linux_experiment_analysis/
"""

import json
import sys
from pathlib import Path


def load_analysis(json_path):
    """加载分析结果"""
    with open(json_path, 'r') as f:
        return json.load(f)


def extract_stats(data):
    """从分析数据中提取统计信息"""
    stats = {
        'total_samples': 0,
        'ssh': {'count': 0, 'p50': None, 'p95': None, 'p99': None},
        'www': {'count': 0, 'p50': None, 'p95': None, 'p99': None},
        'other': {'count': 0, 'p50': None, 'p95': None, 'p99': None},
        'ack_types': {}
    }
    
    # 尝试从不同格式的数据中提取
    if isinstance(data, dict):
        if 'application_analysis' in data:
            app_data = data['application_analysis']
            
            if 'ssh' in app_data and app_data['ssh'].get('mlt_samples', 0) > 0:
                ssh = app_data['ssh']
                stats['ssh'] = {
                    'count': ssh.get('mlt_samples', 0),
                    'p50': ssh.get('percentiles', {}).get('p50'),
                    'p95': ssh.get('percentiles', {}).get('p95'),
                    'p99': ssh.get('percentiles', {}).get('p99')
                }
            
            if 'www' in app_data and app_data['www'].get('mlt_samples', 0) > 0:
                www = app_data['www']
                stats['www'] = {
                    'count': www.get('mlt_samples', 0),
                    'p50': www.get('percentiles', {}).get('p50'),
                    'p95': www.get('percentiles', {}).get('p95'),
                    'p99': www.get('percentiles', {}).get('p99')
                }
            
            if 'other' in app_data and app_data['other'].get('mlt_samples', 0) > 0:
                other = app_data['other']
                stats['other'] = {
                    'count': other.get('mlt_samples', 0),
                    'p50': other.get('percentiles', {}).get('p50'),
                    'p95': other.get('percentiles', {}).get('p95'),
                    'p99': other.get('percentiles', {}).get('p99')
                }
        
        # 计算总样本数
        stats['total_samples'] = (
            stats['ssh']['count'] + 
            stats['www']['count'] + 
            stats['other']['count']
        )
        
        # ACK 类型分布
        if 'delayed_ack_impact' in data:
            ack_cats = data['delayed_ack_impact'].get('categories', {})
            for ack_type, ack_data in ack_cats.items():
                stats['ack_types'][ack_type] = {
                    'count': ack_data.get('count', 0),
                    'accuracy': ack_data.get('accuracy_within_20ms', 0)
                }
    
    return stats


def format_ms(value):
    """格式化毫秒值"""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def print_comparison_table(macos_stats, linux_stats):
    """打印对比表格"""
    print("=" * 80)
    print("macOS vs Linux 实验结果对比")
    print("=" * 80)
    print()
    
    # 总体统计
    print("【总体统计】")
    print(f"{'指标':<20} | {'macOS':>15} | {'Linux':>15} | {'差异':>15}")
    print("-" * 80)
    print(f"{'总样本数':<20} | {macos_stats['total_samples']:>15} | {linux_stats['total_samples']:>15} | {linux_stats['total_samples'] - macos_stats['total_samples']:>+15}")
    print()
    
    # SSH 流量对比
    print("【SSH 流量对比】")
    print(f"{'指标':<20} | {'macOS':>15} | {'Linux':>15} | {'差异':>15}")
    print("-" * 80)
    print(f"{'样本数':<20} | {macos_stats['ssh']['count']:>15} | {linux_stats['ssh']['count']:>15} | {linux_stats['ssh']['count'] - macos_stats['ssh']['count']:>+15}")
    print(f"{'P50 (ms)':<20} | {format_ms(macos_stats['ssh']['p50']):>15} | {format_ms(linux_stats['ssh']['p50']):>15} | {'-':>15}")
    print(f"{'P95 (ms)':<20} | {format_ms(macos_stats['ssh']['p95']):>15} | {format_ms(linux_stats['ssh']['p95']):>15} | {'-':>15}")
    print(f"{'P99 (ms)':<20} | {format_ms(macos_stats['ssh']['p99']):>15} | {format_ms(linux_stats['ssh']['p99']):>15} | {'-':>15}")
    print()
    
    # WWW 流量对比
    print("【WWW 流量对比】")
    print(f"{'指标':<20} | {'macOS':>15} | {'Linux':>15} | {'差异':>15}")
    print("-" * 80)
    print(f"{'样本数':<20} | {macos_stats['www']['count']:>15} | {linux_stats['www']['count']:>15} | {linux_stats['www']['count'] - macos_stats['www']['count']:>+15}")
    print(f"{'P50 (ms)':<20} | {format_ms(macos_stats['www']['p50']):>15} | {format_ms(linux_stats['www']['p50']):>15} | {'-':>15}")
    print(f"{'P95 (ms)':<20} | {format_ms(macos_stats['www']['p95']):>15} | {format_ms(linux_stats['www']['p95']):>15} | {'-':>15}")
    print(f"{'P99 (ms)':<20} | {format_ms(macos_stats['www']['p99']):>15} | {format_ms(linux_stats['www']['p99']):>15} | {'-':>15}")
    print()
    
    # ACK 类型对比
    print("【ACK 类型分布对比】")
    print(f"{'ACK 类型':<20} | {'macOS Count':>12} | {'macOS Acc%':>12} | {'Linux Count':>12} | {'Linux Acc%':>12}")
    print("-" * 80)
    
    all_ack_types = set(macos_stats['ack_types'].keys()) | set(linux_stats['ack_types'].keys())
    for ack_type in sorted(all_ack_types):
        macos_ack = macos_stats['ack_types'].get(ack_type, {'count': 0, 'accuracy': 0})
        linux_ack = linux_stats['ack_types'].get(ack_type, {'count': 0, 'accuracy': 0})
        print(f"{ack_type:<20} | {macos_ack['count']:>12} | {macos_ack['accuracy']:>11.1f}% | {linux_ack['count']:>12} | {linux_ack['accuracy']:>11.1f}%")
    print()


def generate_paper_ready_data(macos_stats, linux_stats):
    """生成论文可用数据"""
    print("=" * 80)
    print("论文章节可用数据")
    print("=" * 80)
    print()
    
    print("**Table X: macOS vs Linux 平台对比**")
    print()
    print("| 平台 | SSH 样本数 | SSH P95 (ms) | WWW 样本数 | WWW P95 (ms) | 总样本数 |")
    print("|------|-----------|-------------|-----------|-------------|----------|")
    print(f"| macOS | {macos_stats['ssh']['count']} | {format_ms(macos_stats['ssh']['p95'])} | {macos_stats['www']['count']} | {format_ms(macos_stats['www']['p95'])} | {macos_stats['total_samples']} |")
    print(f"| Linux | {linux_stats['ssh']['count']} | {format_ms(linux_stats['ssh']['p95'])} | {linux_stats['www']['count']} | {format_ms(linux_stats['www']['p95'])} | {linux_stats['total_samples']} |")
    print()
    
    print("**关键发现**:")
    print(f"- Linux 环境下 SSH 流量占比：{linux_stats['ssh']['count']/max(linux_stats['total_samples'],1)*100:.1f}%")
    print(f"- macOS 环境下 SSH 流量占比：{macos_stats['ssh']['count']/max(macos_stats['total_samples'],1)*100:.1f}%")
    print(f"- Linux 环境下 WWW 流量占比：{linux_stats['www']['count']/max(linux_stats['total_samples'],1)*100:.1f}%")
    print(f"- macOS 环境下 WWW 流量占比：{macos_stats['www']['count']/max(macos_stats['total_samples'],1)*100:.1f}%")
    print()


def main():
    if len(sys.argv) < 3:
        print("使用方法:")
        print(f"  {sys.argv[0]} <macos_analysis_dir> <linux_analysis_dir>")
        print()
        print("示例:")
        print(f"  {sys.argv[0]} analysis_1800/ linux_hybrid_analysis/")
        sys.exit(1)
    
    macos_dir = Path(sys.argv[1])
    linux_dir = Path(sys.argv[2])
    
    # 查找 JSON 文件
    macos_json = None
    linux_json = None
    
    # 尝试不同的文件名
    for filename in ['mlt_full_series_by_app.json', 'mlt_full_series.json', 'ack_strategy_report.json']:
        if (macos_dir / filename).exists():
            macos_json = macos_dir / filename
            break
    
    for filename in ['mlt_full_series_by_app.json', 'mlt_full_series.json', 'ack_strategy_report.json']:
        if (linux_dir / filename).exists():
            linux_json = linux_dir / filename
            break
    
    if not macos_json:
        print(f"[ERROR] 未在 {macos_dir} 中找到分析文件")
        sys.exit(1)
    
    if not linux_json:
        print(f"[ERROR] 未在 {linux_dir} 中找到分析文件")
        sys.exit(1)
    
    print(f"加载 macOS 数据：{macos_json}")
    print(f"加载 Linux 数据：{linux_json}")
    print()
    
    # 加载数据
    macos_data = load_analysis(macos_json)
    linux_data = load_analysis(linux_json)
    
    # 提取统计信息
    macos_stats = extract_stats(macos_data)
    linux_stats = extract_stats(linux_data)
    
    # 打印对比
    print_comparison_table(macos_stats, linux_stats)
    generate_paper_ready_data(macos_stats, linux_stats)
    
    print("=" * 80)
    print("✓ 对比完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
