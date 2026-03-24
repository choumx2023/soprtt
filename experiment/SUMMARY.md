# 跨层验证实验工具包 - 使用总结

## 项目概述

本工具包为论文第四章"跨层验证实验"提供了完整的实验框架，专门针对**Linux 实际网络环境**下的 ACK 策略分析设计。

### 核心功能

1. **实时流量监控** - Linux 网卡被动监听
2. **ACK 策略分析** - 自动识别 Delayed ACK 并量化其影响
3. **应用层分类** - SSH vs WWW 会话的对比分析
4. **可视化对比** - CDF 分布图、箱线图、准确率对比图

---

## 快速开始

### 1. 安装依赖

```bash
cd /Users/choumingxi/Desktop/soprtt
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 运行测试

```bash
python experiment/test_toolkit.py
```

### 3. 分析 PCAP 文件

```bash
# 快速验证
python experiment/quick_validate.py pcaps/1800.pcap -o demo_analysis

# 详细分析
python -m experiment.cli analyze pcaps/1800.pcap \
    -o detailed_analysis
```

---

## 演示结果分析

使用现有 PCAP 文件 (`pcaps/1800.pcap`) 进行了快速验证，结果如下：

### 数据统计

| 指标 | 数值 |
|------|------|
| 总数据包 | 191,685 |
| MLT 样本 | 15,851 |
| SYN-ACK | 550 (3.5%) |
| Back-to-Back | 9,633 (60.8%) |
| Data (Immediate) | 3,298 (20.8%) |
| Data (Delayed) | 2,370 (15.0%) |

### 关键发现

#### 1. ACK 类型精度对比

| ACK 类型 | 准确率 (<20ms) | 平均偏差 | 结论 |
|---------|---------------|---------|------|
| SYN-ACK | 53.1% | 95.5ms | **注意**: 基线过低导致看似准确率低 |
| B2B | 75.0% | 87.0ms | 中等精度 |
| Data (Immediate) | **89.7%** | **6.8ms** | **最高精度!** |
| Data (Delayed) | **0.0%** | **256.2ms** | **完全不可靠** |

**重要说明**: 
- 当前基线使用的是 5% 分位 (0.064ms),这个值过小
- 建议改用中位数或均值作为基线
- Data (Immediate) 实际上是最可靠的样本类型

#### 2. 应用场景分布

**WWW 流量** (端口 80/443):
- 样本数：11,822 (74.6%)
- P50: 0.4ms, P95: 400.8ms
- Delayed ACK 比例：753/11822 ≈ 6.4%

**其他流量** (主要是非 HTTP/HTTPS):
- 样本数：4,029 (25.4%)
- P50: 181.1ms (明显更高)
- Delayed ACK 比例：1617/4029 ≈ 40.2%

**SSH 流量**: 
- 样本数：0 (该 PCAP 中没有 SSH 流量)
- 需要在有 SSH 流量的环境中重新捕获

---

## 实验工具详解

### 工具 1: `quick_validate.py` - 快速验证

**用途**: 快速分析单个 PCAP 文件并生成摘要报告

```bash
python experiment/quick_validate.py <pcap_file> -o <output_dir>
```

**输出**:
- `ack_strategy_report.json` - 详细分析报告
- `ack_strategy_comparison.png` - 4 合 1 对比图
- `mlt_full_series.csv/json` - 原始数据
- `mlt_time_series.png` - 时序图

### 工具 2: `linux_capture.py` - 实时抓包

**用途**: 在 Linux 网卡上实时捕获 TCP 流量

```bash
# 需要 root 权限
sudo python3 experiment/linux_capture.py \
    -i eth0 \
    --target 192.168.1.100 \
    -t 300 \
    -o live_experiment
```

**参数**:
- `-i`: 网络接口 (eth0, en0, etc.)
- `-t`: 抓包时长 (秒)
- `--target`: 目标 IP 过滤器
- `-o`: 输出目录

### 工具 3: `cli.py` - 综合命令行工具

**子命令 1**: `analyze` - 分析 PCAP

```bash
python -m experiment.cli analyze traffic.pcap -o output
```

**子命令 2**: `compare` - 对比多个实验

```bash
python -m experiment.cli compare \
    exp1 exp2 exp3 \
    -o comparison_result
```

**子命令 3**: `cdf` - 生成 CDF 图

```bash
python -m experiment.cdf \
    file1.json file2.json \
    --labels "Experiment A" "Experiment B" \
    -o cdf_plot.png \
    --type syn  # 可选：all/syn/b2b/data
```

---

## 论文章节写作建议

### 第四章结构 (推荐)

#### 4.1 实验设计 (1.5 页)

```
研究问题:
RQ1: 不同类型的 TCP 样本测量精度有何差异？
RQ2: Delayed ACK 对测量结果的影响程度如何？
RQ3: 不同应用场景 (SSH/WWW) 下的 ACK 行为特征？

实验环境:
- 操作系统：Linux (内核版本)
- 网络环境：描述 (校园网/数据中心/家庭宽带)
- 捕获工具：自定义 Python 探针 (基于 scapy)
- 分析方法：ACK 策略分类器
```

#### 4.2 实验 1: ACK 类型分类验证 (2 页)

```
方法:
1. 使用 ack_analyzer.py 自动分类样本
2. 以 SYN-ACK/B2B 样本的 5% 分位作为基线
3. 计算各类样本的偏差分布

结果:
- 表 4-1: 四类样本的统计特征
- 图 4-1: CDF 累积分布对比
- 图 4-2: 准确率柱状图

关键发现:
✓ Data (Immediate) 样本准确率最高 (89.7%)
✓ Delayed ACK 样本完全不可靠 (0% 准确)
✓ 验证了筛选策略的必要性
```

#### 4.3 实验 2: 应用场景对比 (1.5 页)

```
数据收集:
- SSH 流量：端口 22
- WWW 流量：端口 80, 443

对比维度:
1. ACK 类型分布比例
2. MLT 统计特征 (P50, P95, P99)
3. Delayed ACK 出现频率

预期结论:
- SSH 交互频繁，Delayed ACK 较少
- WWW 突发传输多，但通过筛选仍可获得高精度
- 证明了方法的场景适应性
```

#### 4.4 实验 3: 与 macOS 模拟实验对比 (可选，1 页)

```
对比目的:
- 验证真实环境与模拟实验的一致性
- 说明 macOS 注入延迟是极端情况

对比维度:
1. Delayed ACK 等待时间分布
2. 各类样本的精度统计
3. MLT 整体分布形态

威胁效度讨论:
- 操作系统差异
- 网络负载差异
- 采样时间差异
```

#### 4.5 威胁效度 (0.5 页)

```
内部效度:
✓ 使用被动监听，不干扰正常通信
✓ 大样本量 (>10,000 样本)
✗ 单一网络环境可能限制普适性

外部效度:
✓ 涵盖多种应用层协议
✓ 包含不同时间段的数据
✗ 未考虑极端网络条件 (高丢包、强拥塞)
```

---

## 图表清单

### 已生成的图表

1. **demo_analysis/ack_strategy_comparison.png**
   - 4 合 1 综合对比图
   - 包含：样本分布、CDF、箱线图、准确率

2. **demo_analysis/mlt_time_series.png**
   - MLT 随时间变化的散点图
   - 按类型着色 (syn/b2b/data)

### 建议补充的图表

3. **SSH vs WWW 对比图**
   ```bash
   python -m experiment.cdf \
       ssh_exp/mlt.json www_exp/mlt.json \
       --labels "SSH" "WWW" \
       -o app_comparison.png
   ```

4. **macOS vs Linux 对比图**
   ```bash
   python -m experiment.cdf \
       macos_exp/mlt.json linux_exp/mlt.json \
       --labels "macOS (200ms)" "Linux (natural)" \
       -o os_comparison.png
   ```

---

## 下一步工作

### 必须完成

1. **采集 SSH 流量**
   - 在 Linux 机器上进行 SSH 连接操作
   - 或使用 `ssh user@host "cat /dev/zero"` 产生持续流量
   - 建议时长：5-10 分钟

2. **改进基线计算方法**
   - 当前使用 5% 分位可能过低
   - 建议改用中位数或均值
   - 在 `ack_analyzer.py` 中修改 `_compute_mlt_stats()`

3. **整理实验数据表格**
   - 将 JSON 结果转换为 LaTeX 表格
   - 准备论文中的 Table 4-1, 4-2

### 建议完成

4. **延迟注入对比实验** (可选)
   - 使用 tc (traffic control) 在 Linux 下注入延迟
   - 对比 50ms, 100ms, 200ms 不同延迟下的表现
   - 证明方法在不同延迟条件下的鲁棒性

5. **长时间序列分析** (可选)
   - 捕获 1 小时以上的连续流量
   - 分析 MLT 随时段的变化规律
   - 识别网络拥塞时段

---

## 常见问题解答

### Q1: 为什么 SYN-ACK 的准确率只有 53%?

**A**: 这是因为基线值 (0.064ms) 过小。SYN-ACK 的实际 MLT 大多在几毫秒到几十毫秒，相对基线的偏差都很大。

**解决方案**: 
- 改用中位数作为基线
- 或使用绝对阈值 (如 20ms) 而非相对偏差

### Q2: Data (Immediate) 为什么比 SYN-ACK 更准确？

**A**: 这可能是因为：
1. 立即确认的数据段通常发生在活跃传输期，网络状态稳定
2. SYN-ACK 涉及连接建立，可能受到初始握手延迟的影响
3. 样本量差异：B2B 和 Data 样本量大，统计更可靠

### Q3: 如何在自己的环境中重复实验？

**A**: 
1. 在 Linux 机器上运行 `linux_capture.py`
2. 正常进行网络活动 (浏览网页、SSH 连接等)
3. 停止抓包后运行 `quick_validate.py` 分析

### Q4: 生成的图表不够清晰怎么办？

**A**: 
- 修改 `plot_comparison()` 中的 `dpi` 参数 (默认 150)
- 增加样本数量 (延长抓包时间)
- 调整颜色方案和字体大小

---

## 技术参考

### 依赖库版本

```
numpy==2.4.2
matplotlib==3.10.8
scipy==1.17.1
scapy==2.7.0
```

### 代码结构

```
experiment/
├── __init__.py              # 包初始化
├── cli.py                   # 命令行工具
├── ack_analyzer.py          # ACK 策略分析器
├── linux_capture.py         # 实时抓包工具
├── quick_validate.py        # 快速验证脚本
├── test_toolkit.py          # 自测试脚本
├── README.md                # 使用指南
├── EXPERIMENT_DESIGN.md     # 实验设计方案
└── SUMMARY.md               # 本文件
```

### 关键函数

```python
# ACK 分类
analyzer.classify_samples()

# 生成报告
analyzer.generate_report()

# 绘制对比图
analyzer.plot_comparison(output_path)

# 计算统计量
analyzer._compute_mlt_stats(mlts)
```

---

## 联系与支持

- 项目位置：`/Users/choumingxi/Desktop/soprtt/experiment/`
- 文档：`experiment/README.md`
- 实验设计：`experiment/EXPERIMENT_DESIGN.md`
- 示例输出：`demo_analysis/`

---

**创建时间**: 2026-03-24  
**最后更新**: 2026-03-24  
**版本**: v1.0
