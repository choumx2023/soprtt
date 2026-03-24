# 流量捕获与分析 - 完整使用指南

## 📋 老师的建议解读

老师希望你：
1. **在 Linux 环境下捕获真实的 SSH 和 WWW 流量**
2. **使用现有的分析方法**（MLTEngine）处理数据
3. **对比不同场景下的 ACK 策略效果**

---

## 🚀 完整流程（3 步走）

### 步骤 1: 捕获流量 → 生成 PCAP 文件

#### 方案 A: 在 Linux 环境实时抓包 ✅ (推荐)

```bash
# 1. 查看可用的网络接口
python3 capture_traffic.py --list-interfaces

# 2. 开始抓包 (需要 sudo)
sudo python3 capture_traffic.py -i eth0 -t 600 -o ssh_www_capture

# 参数说明:
#   -i eth0      : 网络接口名称
#   -t 600       : 抓包 600 秒 (10 分钟)
#   -o 文件名     : 输出文件名 (会自动加 .pcap 后缀)
```

**抓包时产生流量**:
```bash
# 在另一个终端执行，产生 SSH 流量
ssh user@server "cat /dev/zero > /dev/null"

# 浏览网页产生 WWW 流量
firefox https://github.com
curl https://www.example.com/large-file.zip
```

#### 方案 B: 使用现有 PCAP 文件

如果你已经有 PCAP 文件，可以跳过抓包步骤，直接用方案 A 中生成的 PCAP 或你自己的文件。

---

### 步骤 2: 分析 PCAP 文件 → 生成 MLT 数据

```bash
# 使用快速验证工具分析
python experiment/quick_validate.py ssh_www_capture.pcap -o analysis_output
```

**输出文件**:
- `analysis_output/mlt_full_series.json` ← 主要分析对象
- `analysis_output/mlt_full_series.csv`
- `analysis_output/ack_strategy_report.json`
- `analysis_output/ack_strategy_comparison.png`

---

### 步骤 3: 按应用场景分类统计

```bash
# 分析 SSH vs WWW 流量
python analyze_by_app.py analysis_output/mlt_full_series.json
```

**输出示例**:
```
======================================================================
MLT 样本分析 - 按应用场景分类
======================================================================

总样本数：15851

SSH:
  样本数：3200 (20.2%)
  MLT 统计:
    最小值：0.015 ms
    最大值：450.2 ms
    平均值：45.3 ms
    中位数：12.5 ms
    P95:    85.6 ms
    P99:    125.3 ms
  ACK 类型分布:
    syn: 150 (4.7%)
    b2b: 1800 (56.3%)
    data: 1250 (39.1%)

WWW:
  样本数：9800 (61.8%)
  MLT 统计:
    最小值：0.012 ms
    最大值：520.8 ms
    平均值：52.1 ms
    中位数：8.3 ms
    P95:    95.2 ms
    P99:    145.6 ms
  ACK 类型分布:
    syn: 280 (2.9%)
    b2b: 6200 (63.3%)
    data: 3320 (33.9%)

======================================================================
论文章章可用数据:
======================================================================

**SSH 流量**:
  - 总样本数：3200
  - P50: 12.50 ms
  - P95: 85.60 ms
  - P99: 125.30 ms
  - ACK 类型:
    · syn: 150 (4.7%)
    · b2b: 1800 (56.3%)
    · data: 1250 (39.1%)

**WWW 流量**:
  - 总样本数：9800
  - P50: 8.30 ms
  - P95: 95.20 ms
  - P99: 145.60 ms
  - ACK 类型:
    · syn: 280 (2.9%)
    · b2b: 6200 (63.3%)
    · data: 3320 (33.9%)
```

---

## 📊 论文写作数据模板

### 表 4-X: SSH 与 WWW 流量对比

| 特征 | SSH | WWW |
|------|-----|-----|
| 总样本数 | 3,200 | 9,800 |
| 占比 | 20.2% | 61.8% |
| P50 (ms) | 12.5 | 8.3 |
| P95 (ms) | 85.6 | 95.2 |
| P99 (ms) | 125.3 | 145.6 |
| SYN 比例 | 4.7% | 2.9% |
| B2B 比例 | 56.3% | 63.3% |
| Data 比例 | 39.1% | 33.9% |

### 图 4-X: CDF 对比图

```bash
# 生成 SSH vs WWW 的 CDF 对比图
python experiment/cdf_plot.py \
    ssh_data.json www_data.json \
    --labels "SSH Traffic" "WWW Traffic" \
    -o ssh_www_cdf_comparison.png
```

---

## 🔧 常见问题

### Q1: 没有 Linux 环境怎么办？

**方案 1**: VirtualBox 虚拟机 (免费)
```
1. 下载 VirtualBox
2. 安装 Ubuntu 20.04 LTS
3. 网络设置为"桥接模式"
4. 在虚拟机中运行抓包脚本
```

**方案 2**: 云服务器
```
1. AWS EC2 免费 tier (12 个月)
2. 选择 t2.micro 实例
3. SSH 连接后运行抓包
```

**方案 3**: 使用现有 PCAP
```
先用现有的 pcaps/1800.pcap 做演示分析
Linux 实验作为"未来工作"或"补充实验"
```

### Q2: 抓不到 SSH 流量怎么办？

**方法 1**: 主动产生 SSH 流量
```bash
# 持续产生 SSH 流量
ssh user@server "while true; do echo test; sleep 0.1; done"

# 或使用 scp 传输文件
scp large_file user@server:/tmp/
```

**方法 2**: 延长抓包时间
```bash
sudo python3 capture_traffic.py -i eth0 -t 1800  # 30 分钟
```

### Q3: 如何确认抓包成功？

```bash
# 检查生成的 PCAP 文件大小
ls -lh captured_traffic.pcap

# 用 tcpdump 查看内容
tcpdump -r captured_traffic.pcap | head -20

# 或用 Wireshark 打开
wireshark captured_traffic.pcap
```

---

## 📝 一键运行脚本

创建一个自动化脚本 `run_experiment.sh`:

```bash
#!/bin/bash

echo "======================================"
echo "跨层验证实验 - 一键运行"
echo "======================================"

# 1. 抓包
echo "[1/3] 捕获网络流量..."
sudo python3 capture_traffic.py -i eth0 -t 600 -o experiment_capture

# 2. 分析
echo "[2/3] 分析 MLT 样本..."
python experiment/quick_validate.py experiment_capture.pcap -o experiment_analysis

# 3. 分类统计
echo "[3/3] 按应用场景分类..."
python analyze_by_app.py experiment_analysis/mlt_full_series.json

echo ""
echo "======================================"
echo "✓ 实验完成！"
echo "======================================"
echo "结果位置：experiment_analysis/"
echo "  - mlt_full_series.json"
echo "  - ack_strategy_report.json"
echo "  - ack_strategy_comparison.png"
```

使用方法:
```bash
chmod +x run_experiment.sh
./run_experiment.sh
```

---

## 🎯 实验检查清单

- [ ] 已成功安装所有依赖 (`pip install -r requirements.txt`)
- [ ] 已测试工具包 (`python experiment/test_toolkit.py`)
- [ ] 已捕获网络流量 (PCAP 文件)
- [ ] 已分析 PCAP 文件 (生成 JSON 报告)
- [ ] 已分类 SSH vs WWW 流量
- [ ] 已生成对比图表
- [ ] 已整理论文所需数据表格

---

## 📚 相关文件

| 文件 | 用途 |
|------|------|
| `capture_traffic.py` | 流量捕获工具 |
| `analyze_by_app.py` | 应用分类分析 |
| `experiment/quick_validate.py` | 快速验证 |
| `experiment/ack_analyzer.py` | ACK 策略分析 |
| `EXPERIMENT_PROPOSAL.md` | 实验方案汇报 |

---

**最后更新**: 2026-03-24  
**版本**: v1.0
