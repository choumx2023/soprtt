# Linux 环境下的跨层验证实验指南

## 概述

本实验工具包用于在**Linux 实际网络环境**下验证不同 ACK 策略对 MLT 测量精度的影响，特别针对 SSH 和 WWW 会话数据进行深入分析。

## 核心功能

### 1. 实时流量监控 (`linux_capture.py`)
- 在 Linux 网卡接口上被动监听 TCP 流量
- 自动分类 SSH (端口 22) 和 WWW (端口 80/443) 会话
- 实时计算 MLT 样本并保存

### 2. ACK 策略分析器 (`ack_analyzer.py`)
- 识别不同类型的 ACK 行为：
  - **SYN-ACK**: 最可靠（误差 < 20ms）
  - **Back-to-Back**: 较可靠
  - **Immediate ACK**: 普通数据段的立即确认
  - **Delayed ACK**: 延迟确认（可能引入 40-500ms 偏差）
- 量化 Delayed ACK 对测量精度的影响
- 生成可视化对比图表

### 3. 实验对比工具 (`cli.py`)
- 对比多个实验的结果
- 生成 CDF 累积分布图
- 按应用场景（SSH vs WWW）分别统计

---

## 安装依赖

```bash
pip install numpy matplotlib scipy scapy
```

---

## 使用方法

### 方案 1: 分析现有 PCAP 文件

如果你有已经捕获的 PCAP 文件：

```bash
# 分析 SSH 会话数据
python -m experiment.cli analyze ssh_traffic.pcap \
    -o ssh_experiment \
    --target 192.168.1.100

# 分析 WWW 会话数据
python -m experiment.cli analyze www_traffic.pcap \
    -o www_experiment \
    --target 192.168.1.100
```

### 方案 2: 实时捕获网络流量

在 Linux 机器上实时监听：

```bash
# 需要 root 权限
sudo python3 experiment/linux_capture.py \
    -i eth0 \
    --target 192.168.1.100 \
    -o live_ssh_experiment \
    -t 300  # 捕获 300 秒
```

### 方案 3: 对比多个实验

```bash
# 对比 SSH 和 WWW 实验的结果
python -m experiment.cli compare \
    ssh_experiment www_experiment \
    -o comparison_result
```

### 方案 4: 生成 CDF 对比图

```bash
# 对比所有样本类型
python -m experiment.cdf \
    ssh_experiment/mlt_live.json \
    www_experiment/mlt_live.json \
    --labels "SSH Traffic" "WWW Traffic" \
    -o cdf_all_types.png

# 仅对比 SYN-ACK 样本（最可靠）
python -m experiment.cdf \
    ssh_experiment/mlt_live.json \
    www_experiment/mlt_live.json \
    --labels "SSH" "WWW" \
    -o cdf_syn_only.png \
    --type syn

# 仅对比 B2B 样本
python -m experiment.cdf \
    ssh_experiment/mlt_live.json \
    www_experiment/mlt_live.json \
    --labels "SSH" "WWW" \
    -o cdf_b2b_only.png \
    --type b2b
```

---

## 输出说明

每个实验会生成以下文件：

```
experiment_output/
├── mlt_live.csv              # CSV 格式的 MLT 时间序列
├── mlt_live.json             # JSON 格式的完整样本
├── mlt_live.png              # MLT 时序图
├── statistics.json           # 统计数据摘要
└── ack_strategy_report.json  # ACK 策略分析报告（如果有）
```

### statistics.json 示例

```json
{
  "capture_duration_seconds": 300.5,
  "total_packets": 125000,
  "total_mlt_samples": 8500,
  "type_statistics": {
    "syn": {"count": 150, "avg": 0.025, "p95": 0.045},
    "b2b": {"count": 2300, "avg": 0.028, "p95": 0.052},
    "data": {"count": 6050, "avg": 0.156, "p95": 0.421}
  },
  "application_statistics": {
    "ssh": {"count": 3200},
    "www": {"count": 4800},
    "other": {"count": 500}
  }
}
```

### ack_strategy_report.json 关键指标

```json
{
  "delayed_ack_impact": {
    "baseline_mlt": 0.023,
    "categories": {
      "syn_ack": {
        "count": 150,
        "accuracy_within_20ms": 98.7,
        "avg_deviation_ms": 2.3
      },
      "b2b": {
        "count": 2300,
        "accuracy_within_20ms": 96.2,
        "avg_deviation_ms": 5.1
      },
      "data_immediate": {
        "count": 2100,
        "accuracy_within_20ms": 87.3,
        "avg_deviation_ms": 12.5
      },
      "data_delayed": {
        "count": 3950,
        "accuracy_within_20ms": 23.4,
        "avg_deviation_ms": 185.6
      }
    }
  }
}
```

---

## 预期结果与解释

### 1. SYN-ACK 样本
- **准确率**: > 95%（误差 < 20ms）
- **特点**: 不受 Delayed ACK 影响
- **建议**: 作为最高精度的测量来源

### 2. Back-to-Back 样本
- **准确率**: 90-96%
- **特点**: 连续数据传输，ACK 及时
- **建议**: 可靠的次要测量来源

### 3. 普通数据段样本
- **准确率**: 分化严重
  - Immediate ACK: 80-90%
  - Delayed ACK: 20-40%（系统性偏高）
- **特点**: 受操作系统 ACK 策略影响大
- **建议**: 需要过滤或单独处理

### SSH vs WWW 对比

| 特征 | SSH | WWW |
|------|-----|-----|
| 交互模式 | 小包、频繁 | 大包、突发 |
| Delayed ACK 比例 | 较低 (~30%) | 较高 (~60%) |
| 测量精度 | 较高 | 较低（需筛选） |

---

## 论文写作建议

### 第四章实验设计

#### 实验 1: ACK 类型分类验证
**目的**: 证明不同类型样本的精度差异

**方法**:
1. 在 Linux 环境捕获真实流量（SSH + WWW）
2. 使用 ACK 分析器分类统计
3. 对比各类样本的 MLT 分布

**预期结论**:
- SYN-ACK 和 B2B 样本准确率 > 95%
- Delayed ACK 样本准确率显著降低（~20-40%）
- 验证了"高精度样本筛选策略"的必要性

#### 实验 2: 应用场景对比
**目的**: 验证不同应用层协议下的测量效果

**方法**:
1. 分别统计 SSH 和 WWW 会话的 MLT 样本
2. 对比两类场景的 ACK 行为差异
3. 分析 Delayed ACK 的影响程度

**预期结论**:
- SSH 场景 Delayed ACK 较少，整体精度更高
- WWW 场景 Delayed ACK 较多，但通过筛选仍可获得高精度样本
- 证明了方法在不同场景下的适用性

#### 实验 3: 与 macOS 注入延迟实验对比
**目的**: 说明真实环境与模拟实验的差异

**对比维度**:
- Delayed ACK 比例（真实 vs 模拟）
- MLT 分布形态
- 测量精度统计

**关键发现**:
- macOS 注入 200ms 延迟是极端情况
- Linux 实际环境中 Delayed ACK 等待时间通常在 40-200ms
- 真实场景更复杂，但核心结论一致

---

## 常见问题

### Q1: 为什么需要 Linux 环境？
A: Linux 的 TCP/IP 协议栈实现与 macOS 不同，ACK 策略也有差异。在 Linux 下验证可以证明方法的普适性。

### Q2: 如何区分 Delayed ACK？
A: 通过分析 MLT 分布：
- MLT < 40ms: 通常是 Immediate ACK
- MLT > 40ms: 可能是 Delayed ACK（需结合基线判断）

### Q3: 抓包需要 root 权限吗？
A: 是的，需要使用 `sudo` 运行实时抓包脚本。

### Q4: 如果只有 macOS 环境怎么办？
A: 可以先用现有 PCAP 文件做离线分析，或者考虑：
1. 使用 VirtualBox 运行 Linux 虚拟机
2. 在云服务器（如 AWS EC2）上进行实验

### Q5: 需要捕获多少数据？
A: 建议至少 5-10 分钟的活跃流量，以获得足够的 SYN-ACK 和 B2B 样本（各 > 100 个）。

---

## 参考文献

1. Stevens, W. R. (1994). TCP/IP Illustrated, Volume 1. （Delayed ACK 机制）
2. Allman, M., & Paxson, V. (1999). On Estimating End-to-End Network Path Properties. （RTT 测量）
3. 你的论文第三章（多级匹配方法）

---

## 技术支持

遇到问题可以：
1. 查看 `--help` 获取命令帮助
2. 检查输出目录的日志文件
3. 联系作者讨论

---

**最后更新**: 2026-03-24
