# 第四章跨层验证实验设计方案

## 一、实验目标

通过在**Linux 实际网络环境**下的对比实验，验证以下结论：

1. **核心假设**: 不同类型的 TCP 样本具有不同的测量精度
   - SYN-ACK 和 Back-to-Back 样本：高精度（误差 < 20ms）
   - 普通数据段样本：受 Delayed ACK 影响，精度分化严重

2. **应用场景差异**: SSH 和 WWW 会话的 ACK 行为存在显著差异

3. **方法普适性**: 多级匹配方法在不同操作系统和场景下均有效

---

## 二、实验设计

### 实验 1: ACK 类型分类验证（核心实验）

#### 目的
量化不同类型 ACK 样本的测量精度，证明筛选策略的必要性。

#### 方法
1. **数据采集**: 
   - 在 Linux 环境捕获真实网络流量
   - 使用 `linux_capture.py` 或分析现有 PCAP 文件
   
2. **样本分类**:
   ```python
   # 使用 ack_analyzer.py 自动分类
   python -m experiment.cli analyze traffic.pcap -o experiment_output
   ```

3. **精度评估**:
   - 以 SYN-ACK 样本的 5% 分位 MLT 作为基线
   - 计算各类样本相对基线的偏差
   - 统计误差 < 20ms 的比例

#### 预期结果

| ACK 类型 | 样本数 | 平均偏差 (ms) | 准确率 (<20ms) |
|---------|--------|--------------|---------------|
| SYN-ACK | ~150 | 2-5 | 95-99% |
| B2B | ~2000 | 5-10 | 90-96% |
| Data (Immediate) | ~2000 | 10-20 | 80-90% |
| Data (Delayed) | ~4000 | 100-200 | 20-40% |

#### 可视化
- **CDF 对比图**: 展示四类样本的 MLT 累积分布
- **箱线图**: 对比各类样本的分布形态
- **准确率为图**: 直观显示精度差异

#### 结论要点
- SYN-ACK 和 B2B 样本是最可靠的测量来源
- Delayed ACK 样本系统性偏高，需要过滤
- 验证了"高精度样本筛选策略"的有效性

---

### 实验 2: SSH vs WWW 应用层面对比

#### 目的
验证不同应用场景下的 ACK 行为差异及测量效果。

#### 方法
1. **流量分离**:
   - SSH: 端口 22
   - WWW: 端口 80, 443

2. **分别统计**:
   ```bash
   # SSH 流量
   python -m experiment.cli analyze ssh.pcap \
       --target 192.168.1.100 \
       -o ssh_experiment
   
   # WWW 流量
   python -m experiment.cli analyze www.pcap \
       --target 192.168.1.100 \
       -o www_experiment
   ```

3. **对比维度**:
   - Delayed ACK 比例
   - MLT 分布形态
   - 测量精度统计

#### 预期结果

| 特征 | SSH | WWW |
|------|-----|-----|
| 总样本数 | ~3000 | ~5000 |
| SYN-ACK 比例 | 5% | 3% |
| B2B 比例 | 30% | 25% |
| Delayed ACK 比例 | 30% | 60% |
| 综合精度 (P95) | 45ms | 80ms |
| 筛选后精度 | 25ms | 30ms |

#### 可视化
- **分组柱状图**: 对比 ACK 类型分布
- **双 CDF 曲线**: SSH vs WWW 的 MLT 分布
- **时序对比图**: 展示两类流量的 MLT 变化趋势

#### 结论要点
- SSH 交互频繁，Delayed ACK 较少
- WWW 突发传输多，Delayed ACK 比例高
- 通过筛选策略，两者均可获得高精度样本

---

### 实验 3: macOS 模拟 vs Linux 真实环境对比

#### 目的
说明真实环境与模拟实验的差异，验证结论的稳健性。

#### 方法
1. **macOS 数据** (已有):
   - 注入单向 200ms 延迟
   - 监控探针被动监听

2. **Linux 数据** (新增):
   - 无注入延迟的自然流量
   - 相同的监控和分析方法

3. **对比维度**:
   - Delayed ACK 等待时间分布
   - MLT 整体分布形态
   - 各类样本的精度统计

#### 预期发现

| 特征 | macOS (注入 200ms) | Linux (自然) |
|------|-------------------|-------------|
| Delayed ACK 阈值 | ~200ms | 40-200ms |
| Delayed ACK 比例 | ~80% | ~50% |
| MLT 峰值 | 明显 (~0.2s) | 不明显 |
| SYN-ACK 精度 | 99% | 98% |
| B2B 精度 | 97% | 95% |

#### 结论要点
- macOS 注入延迟是极端情况，放大了 Delayed ACK 效应
- Linux 实际环境更复杂，但核心结论一致
- 证明了方法的鲁棒性和普适性

---

## 三、实施步骤

### 阶段 1: 数据采集 (1-2 天)

```bash
# 方案 A: 使用现有 PCAP
cp /path/to/capture.pcap pcaps/linux_natural.pcap

# 方案 B: 实时捕获 (需要 Linux 机器)
sudo python3 experiment/linux_capture.py \
    -i eth0 \
    -t 600 \
    -o live_experiment
```

### 阶段 2: 离线分析 (1 天)

```bash
# 1. 基础分析
python -m experiment.quick_validate pcaps/linux_natural.pcap \
    -o validation_result

# 2. 详细 ACK 策略分析
python -m experiment.cli analyze pcaps/linux_natural.pcap \
    -o detailed_analysis

# 3. 如果有多个 PCAP 文件，进行对比
python -m experiment.cli compare \
    macos_experiment linux_experiment \
    -o comparison_result
```

### 阶段 3: 可视化生成 (半天)

```bash
# 生成 CDF 对比图
python -m experiment.cdf \
    macos/mlt.json linux/mlt.json \
    --labels "macOS (200ms injected)" "Linux (natural)" \
    -o cdf_comparison.png

# 仅对比 SYN-ACK 样本
python -m experiment.cdf \
    macos/mlt.json linux/mlt.json \
    --labels "macOS" "Linux" \
    -o cdf_syn_only.png \
    --type syn
```

### 阶段 4: 结果整理与写作 (2-3 天)

1. 整理实验数据表格
2. 提取关键图表
3. 撰写实验分析文本
4. 讨论威胁效度

---

## 四、论文章节结构建议

### 4.1 实验设计 (2 页)
- 研究问题 (RQ1, RQ2, RQ3)
- 实验环境描述
- 数据采集方法
- 评估指标定义

### 4.2 实验 1: ACK 类型分类 (3 页)
- 样本分类方法
- 精度评估结果
- CDF/箱线图对比
- **结论**: 筛选策略的必要性

### 4.3 实验 2: 应用层面对比 (2 页)
- SSH vs WWW 流量特征
- ACK 行为差异
- 测量精度对比
- **结论**: 方法的场景适应性

### 4.4 实验 3: 环境对比 (可选，2 页)
- macOS vs Linux 差异
- 模拟实验的局限性
- 真实环境的复杂性
- **结论**: 方法的鲁棒性

### 4.5 威胁效度 (1 页)
- 内部效度威胁
- 外部效度威胁
- 缓解措施

### 4.6 本章小结 (0.5 页)

---

## 五、关键图表清单

### 必备图表
1. **图 4-1**: ACK 类型分类 CDF 对比图
2. **图 4-2**: 测量精度对比柱状图
3. **图 4-3**: SSH vs WWW 流量特征对比
4. **表 4-1**: 各类样本精度统计表
5. **表 4-2**: 应用场景对比摘要

### 可选图表
6. **图 4-4**: macOS vs Linux MLT 分布对比
7. **图 4-5**: MLT 时序图 (带 log 标记)
8. **图 4-6**: Delayed ACK 等待时间直方图

---

## 六、代码使用速查

### 快速上手
```bash
# 1. 分析单个 PCAP
python -m experiment.quick_validate capture.pcap

# 2. 查看详细分析
python -m experiment.cli analyze capture.pcap -o output

# 3. 对比多个实验
python -m experiment.cli compare exp1 exp2 -o comparison

# 4. 生成 CDF 图
python -m experiment.cdf file1.json file2.json --labels A B
```

### 高级用法
```bash
# 实时抓包
sudo python3 experiment/linux_capture.py -i eth0 -t 300

# 仅分析特定类型样本
python -m experiment.cdf mlt.json --labels All --type syn

# 自定义过滤器
python -m experiment.cli analyze capture.pcap \
    --target 192.168.1.100 \
    --monitor 192.168.1.1
```

---

## 七、预期贡献

### 对第三章的支撑
- 实验验证"高精度样本筛选策略"的有效性
- 量化筛选前后的精度提升
- 证明多级匹配方法的实用性

### 独立价值
- 揭示不同 ACK 策略的测量误差特征
- 提供 Linux 环境的实测数据
- 为后续研究提供基准参考

### 创新点
1. **首次**在 Linux 实际环境下验证 MLT 测量精度
2. 提出 ACK 类型分类方法并量化其影响
3. 对比 SSH 和 WWW 两种典型应用场景

---

## 八、时间规划

| 任务 | 预计时间 | 产出物 |
|------|---------|--------|
| 环境准备 | 0.5 天 | 可运行的实验工具 |
| 数据采集 | 1 天 | PCAP 文件 / 实时数据 |
| 离线分析 | 1 天 | JSON 报告、统计表格 |
| 可视化 | 0.5 天 | PNG 图表 |
| 结果整理 | 1 天 | 数据表格、图表集 |
| 章节写作 | 2-3 天 | 完整的第四章草稿 |
| **总计** | **6-8 天** | **完整的实验章节** |

---

## 九、常见问题解答

### Q1: 没有 Linux 环境怎么办？
**A**: 可以：
1. 使用 VirtualBox 安装 Ubuntu 虚拟机
2. 使用云服务器（AWS EC2 免费 tier）
3. 先分析现有 PCAP 文件，Linux 实验作为未来工作

### Q2: 如何确定 Delayed ACK 的阈值？
**A**: 参考文献通常使用 40ms 作为阈值，但可以根据实际情况调整：
```python
# 查看 MLT 分布的直方图
plt.hist(mlts, bins=100)
plt.xlabel("MLT (s)")
plt.show()
```

### Q3: 样本数量不够怎么办？
**A**: 
- 延长抓包时间（建议至少 5-10 分钟）
- 增加数据源（多台机器）
- 降低统计粒度（合并时间窗口）

### Q4: 如何解释异常值？
**A**: 
- 检查是否有重传、乱序
- 考虑网络拥塞时段
- 可以使用中位数代替平均值

---

## 十、技术支持

- 工具文档：`experiment/README.md`
- 代码示例：`experiment/quick_validate.py`
- 问题反馈：[你的联系方式]

---

**最后更新**: 2026-03-24  
**版本**: v1.0
