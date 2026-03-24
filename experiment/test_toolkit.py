#!/usr/bin/env python3
"""
测试脚本 - 验证实验工具的基本功能
"""

import os
import sys
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """测试必要的模块是否可以导入"""
    print("Testing imports...")
    
    try:
        from experiment.ack_analyzer import ACKStrategyAnalyzer
        print("  ✓ ack_analyzer imported")
    except ImportError as e:
        print(f"  ✗ Failed to import ack_analyzer: {e}")
        return False
    
    try:
        from experiment.cli import compare_experiments
        print("  ✓ cli imported")
    except ImportError as e:
        print(f"  ✗ Failed to import cli: {e}")
        return False
    
    try:
        import numpy as np
        print("  ✓ numpy imported")
    except ImportError:
        print("  ✗ numpy not installed. Run: pip install numpy")
        return False
    
    try:
        import matplotlib.pyplot as plt
        print("  ✓ matplotlib imported")
    except ImportError:
        print("  ✗ matplotlib not installed. Run: pip install matplotlib")
        return False
    
    try:
        from scapy.all import TCP, IP
        print("  ✓ scapy imported")
    except ImportError:
        print("  ✗ scapy not installed. Run: pip install scapy")
        return False
    
    print("\nAll imports successful!\n")
    return True


def test_analyzer():
    """测试 ACK 分析器的基本功能"""
    print("Testing ACKStrategyAnalyzer...")
    
    # 创建模拟样本
    mock_samples = [
        {
            "flow": ("192.168.1.1", 80, "192.168.1.2", 12345),
            "mlt": 0.025,
            "type": "syn",
            "ack_sender": "192.168.1.1",
            "ack_time": 1000.0
        },
        {
            "flow": ("192.168.1.1", 80, "192.168.1.2", 12345),
            "mlt": 0.030,
            "type": "b2b",
            "ack_sender": "192.168.1.1",
            "ack_time": 1001.0
        },
        {
            "flow": ("192.168.1.1", 80, "192.168.1.2", 12345),
            "mlt": 0.035,
            "type": "data",
            "ack_sender": "192.168.1.1",
            "ack_time": 1002.0
        },
        {
            "flow": ("192.168.1.1", 22, "192.168.1.2", 54321),
            "mlt": 0.150,
            "type": "data",
            "ack_sender": "192.168.1.1",
            "ack_time": 1003.0
        }
    ]
    
    try:
        from experiment.ack_analyzer import ACKStrategyAnalyzer
        
        analyzer = ACKStrategyAnalyzer(mock_samples)
        
        # 测试分类
        classified = analyzer.classify_samples()
        print(f"  Classified samples: {sum(len(v) for v in classified.values())}")
        
        # 测试报告生成
        report = analyzer.generate_report()
        print(f"  Report generated: {report['summary']['total_samples']} samples")
        
        print("  ✓ Analyzer tests passed\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Analyzer test failed: {e}\n")
        return False


def test_existing_pcap():
    """测试现有的 PCAP 文件（如果有的话）"""
    pcap_dir = "pcaps"
    
    if not os.path.exists(pcap_dir):
        print(f"PCAP directory '{pcap_dir}' not found. Skipping PCAP test.\n")
        return True
    
    pcap_files = [f for f in os.listdir(pcap_dir) if f.endswith('.pcap')]
    
    if not pcap_files:
        print("No PCAP files found. Skipping PCAP test.\n")
        return True
    
    print(f"Found PCAP files: {pcap_files}")
    print("You can analyze them with:")
    print(f"  python -m experiment.quick_validate pcaps/{pcap_files[0]}\n")
    
    return True


def main():
    print("=" * 60)
    print("Experiment Toolkit - Self Test")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Test 1: Imports
    if not test_imports():
        all_passed = False
        print("Please install missing dependencies:")
        print("  pip install numpy matplotlib scipy scapy\n")
    
    # Test 2: Analyzer
    if not test_analyzer():
        all_passed = False
    
    # Test 3: PCAP files
    if not test_existing_pcap():
        all_passed = False
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("\nNext steps:")
        print("  1. Analyze a PCAP file:")
        print("     python -m experiment.quick_validate your_capture.pcap")
        print()
        print("  2. Read the documentation:")
        print("     cat experiment/README.md")
        print()
        print("  3. Design your experiment:")
        print("     cat experiment/EXPERIMENT_DESIGN.md")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
