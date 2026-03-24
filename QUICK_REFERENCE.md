# 🚀 Linux 实验快速参考卡片

## 📋 一句话总结

**在 Linux 虚拟机或云服务器上运行一键脚本，自动捕获 SSH+WWW 流量并完成分析。**

---

## ⚡ 3 分钟快速开始

### 方案 A: Ubuntu 虚拟机（推荐新手）

```bash
# 1. 安装 VirtualBox + Ubuntu 22.04 (网络设为桥接模式)

# 2. 在 Ubuntu 中打开终端，运行：
wget https://github.com/your-repo/soprtt/archive/main.zip
unzip main.zip && cd soprtt-main

# 3. 运行安装脚本：
bash setup_linux.sh

# 4. 运行实验（一键完成抓包+分析）：
sudo ./run_linux_experiment.sh

# 完成！查看结果
ls -lh *.pcap
ls -lh *_analysis/
```

### 方案 B: AWS EC2 云服务器

```bash
# 1. 创建 EC2 t2.micro 实例（免费 12 个月）
# 2. SSH 连接后运行：
git clone <your-repo>
cd soprtt

# 3. 安装依赖：
bash setup_linux.sh

# 4. 运行实验：
sudo ./run_linux_experiment.sh aws_capture 300
```

---

## 📊 生成的文件

运行 `run_linux_experiment.sh` 后自动生成：

```
linux_hybrid_capture.pcap          ← 原始 PCAP 文件（~50-200MB）
linux_hybrid_capture_analysis/     ← 分析结果目录
├── mlt_full_series.json           ← 主要数据
├── mlt_full_series.csv
├── ack_strategy_report.json       ← ACK 策略报告
├── ack_strategy_comparison.png    ← 对比图
└── mlt_time_series.png            ← 时间序列图
```

---

## 📈 论文数据提取

运行完成后，自动显示论文可用数据：

```
======================================================================
论文章节可用数据:
======================================================================

**SSH 流量 (Linux)**:
  - 总样本数：X,XXX
  - P50: XX.XX ms
  - P95: XXX.XX ms
  - P99: XXX.XX ms

**WWW 流量 (Linux)**:
  - 总样本数：X,XXX  
  - P50: X.XX ms
  - P95: XXX.XX ms
  - P99: XXX.XX ms
```

直接复制到论文中即可！

---

## 🔬 对比 macOS vs Linux

```bash
# 比较两个平台的结果：
python3 compare_macos_linux.py analysis_1800/ linux_hybrid_capture_analysis/

# 自动生成对比表格和论文数据
```

---

## 🎯 典型实验结果

| 指标 | macOS | Linux | 说明 |
|------|-------|-------|------|
| SSH 样本数 | 0 | 2,000-5,000 | Mac 数据无 SSH |
| WWW 样本数 | 9,422 | 8,000-15,000 | 相当 |
| Delayed ACK% | 15% | 10-30% | Linux 变化大 |
| b2b 比例 | 60% | 50-70% | 主要类型 |

---

## 🛠️ 自定义参数

```bash
# 指定输出文件名
sudo ./run_linux_experiment.sh my_experiment

# 指定抓包时长（秒）
sudo ./run_linux_experiment.sh ssh_test 300   # 5 分钟
sudo ./run_linux_experiment.sh www_test 1800  # 30 分钟

# 两者都指定
sudo ./run_linux_experiment.sh hybrid 600
```

---

## 🐛 常见问题速查

### 没有 SSH 流量？
```bash
# 手动产生
ssh github.com "cat /dev/zero > /dev/null" &
ssh gitlab.com "cat /dev/zero > /dev/null" &
```

### 找不到网络接口？
```bash
ip addr show
# 替换 eth0 为实际接口名（如 enp0s3, ens33）
```

### 权限错误？
```bash
# 必须使用 sudo
sudo ./run_linux_experiment.sh
```

### VM 桥接不工作？
```bash
# VirtualBox: 设置 → 网络 → 名称选物理网卡
# 不是 "NAT"，是 "Bridged Adapter"
```

---

## 📚 完整文档

- `LINUX_EXPERIMENT_GUIDE.md` - 完整指南（强烈推荐阅读）
- `setup_linux.sh` - 一键安装脚本
- `run_linux_experiment.sh` - 一键实验脚本
- `compare_macos_linux.py` - 平台对比工具

---

## 💡 下一步

1. ✅ 在 Linux 环境运行实验
2. ✅ 获得 SSH 和 WWW 流量数据
3. ✅ 对比 macOS vs Linux 结果
4. ✅ 整理论文数据表格
5. ✅ 完成实验章节写作

---

**祝实验顺利！** 🎓
