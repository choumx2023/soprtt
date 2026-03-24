# Linux 实际场景测试指南

## 📋 实验目标

在**真实 Linux 环境**下捕获 SSH 和 WWW 流量，验证不同 ACK 策略下的 MLT 测量效果。

---

## 🎯 为什么选择 Linux？

### 学术价值
1. **TCP 栈实现透明** - Linux TCP 代码开源，便于深入分析
2. **ACK 策略可配置** - 可通过 `/proc/sys/net/ipv4/` 调整行为
3. **学术界标准平台** - 大多数网络研究使用 Linux
4. **Delayed ACK 行为典型** - 保留传统实现，便于观察

### macOS 的局限性
- BSD 网络栈，与主流服务器环境不同
- TCP 实现封闭，难以深入分析
- Delayed ACK 行为不典型
- 审稿人可能质疑结果普适性

---

## 🚀 快速开始（3 种方案）

### 方案 1: Ubuntu 虚拟机 ⭐ 推荐

#### 安装步骤
```bash
# 1. 下载 VirtualBox
https://www.virtualbox.org/wiki/Downloads

# 2. 下载 Ubuntu 22.04 LTS ISO
https://ubuntu.com/download/desktop

# 3. 创建虚拟机
- 内存：至少 4GB
- 硬盘：至少 20GB
- 网络：**桥接模式** (Bridged Adapter) ← 重要！
```

#### 安装后配置
```bash
# 在 Ubuntu 虚拟机中执行
sudo apt update
sudo apt install -y python3 python3-pip tcpdump wireshark git

# 克隆你的项目
git clone <your-repo-url>
cd soprtt

# 安装依赖
pip3 install scapy numpy scipy matplotlib
```

#### 开始抓包
```bash
# 1. 查看网络接口名称
ip addr show
# 通常是 eth0 或 enp0s3

# 2. 开始抓包 (600 秒)
sudo python3 capture_traffic.py -i eth0 -t 600 -o linux_ssh_www

# 3. 同时产生流量（另开终端）
# SSH 流量
ssh github.com "cat /dev/zero > /dev/null" &

# WWW 流量
curl -o /dev/null https://www.example.com/large-file.zip &
wget -O /dev/null https://httpbin.org/stream-bytes/10M &
```

---

### 方案 2: 云服务器 (AWS EC2)

#### 免费套餐
- **AWS EC2 t2.micro**: 12 个月免费
- **Google Cloud e2-micro**: 永久免费层
- **Azure B1S**: 12 个月免费

#### AWS EC2 快速开始
```bash
# 1. 创建实例
# - 选择 Amazon Linux 2 或 Ubuntu 22.04
# - 实例类型：t2.micro (Free tier)
# - 安全组：开放 SSH(22), HTTP(80), HTTPS(443)

# 2. SSH 连接
ssh -i your-key.pem ec2-user@your-instance-ip

# 3. 安装依赖
sudo yum install -y python3 tcpdump  # Amazon Linux
# 或
sudo apt install -y python3-pip tcpdump  # Ubuntu

# 4. 上传你的脚本
scp -i your-key.pem capture_traffic.py ec2-user@your-instance-ip:~/
scp -i your-key.pem experiment/ ec2-user@your-instance-ip:~/ -r

# 5. 开始抓包
sudo python3 capture_traffic.py -i eth0 -t 600 -o aws_capture
```

---

### 方案 3: WSL2 (Windows Subsystem for Linux)

```bash
# Windows 10/11 上安装 WSL2
wsl --install -d Ubuntu

# 重启后，在 Ubuntu 中：
sudo apt update
sudo apt install -y python3 python3-pip tcpdump

# 注意：WSL2 的网络是虚拟化的，可能需要特殊配置才能抓包
```

---

## 📊 实验设计

### 实验 1: SSH 会话数据分析

```bash
#!/bin/bash
# run_ssh_experiment.sh

echo "=== SSH 流量捕获实验 ==="

# 1. 开始抓包
sudo python3 capture_traffic.py -i eth0 -t 300 -o ssh_only &
CAPTURE_PID=$!

# 2. 产生 SSH 流量
echo "产生 SSH 流量..."
for i in {1..5}; do
    ssh user@server "cat /dev/zero > /dev/null" &
    sleep 2
done

# 3. 等待完成
wait $CAPTURE_PID

# 4. 分析
python3 experiment/quick_validate.py ssh_only.pcap -o ssh_analysis
python3 analyze_by_app.py ssh_analysis/mlt_full_series.json
```

### 实验 2: WWW 流量分析

```bash
#!/bin/bash
# run_www_experiment.sh

echo "=== WWW 流量捕获实验 ==="

# 1. 开始抓包
sudo python3 capture_traffic.py -i eth0 -t 300 -o www_only &
CAPTURE_PID=$!

# 2. 产生 HTTP/HTTPS 流量
echo "产生 WWW 流量..."
curl -o /dev/null https://github.com &
curl -o /dev/null https://www.wikipedia.org &
wget -O /dev/null https://httpbin.org/stream-bytes/5M &
sleep 30

# 3. 等待完成
wait $CAPTURE_PID

# 4. 分析
python3 experiment/quick_validate.py www_only.pcap -o www_analysis
python3 analyze_by_app.py www_analysis/mlt_full_series.json
```

### 实验 3: 混合流量对比

```bash
#!/bin/bash
# run_hybrid_experiment.sh

echo "=== 混合流量实验 ==="

# 1. 开始抓包
sudo python3 capture_traffic.py -i eth0 -t 600 -o hybrid_capture &
CAPTURE_PID=$!

# 2. 同时产生 SSH 和 WWW 流量
echo "产生混合流量..."

# SSH 流量
ssh user@server "cat /dev/zero > /dev/null" &

# WWW 流量
curl -o /dev/null https://www.example.com &
wget -O /dev/null https://httpbin.org/stream-bytes/10M &

# 3. 等待完成
wait $CAPTURE_PID

# 4. 分析
python3 experiment/quick_validate.py hybrid_capture.pcap -o hybrid_analysis
python3 analyze_by_app.py hybrid_analysis/mlt_full_series.json
```

---

## 🔬 高级实验：控制 ACK 策略

### 修改 Linux TCP 参数

```bash
# 查看当前 TCP 配置
sysctl net.ipv4.tcp_delayed_ack
sysctl net.ipv4.tcp_quickack
sysctl net.ipv4.tcp_slow_start_after_idle

# 临时关闭 Delayed ACK (需要 root)
sudo sysctl -w net.ipv4.tcp_quickack=1

# 恢复默认
sudo sysctl -w net.ipv4.tcp_quickack=0
```

### 对比实验设计

```bash
# 实验 A: 默认配置
sudo sysctl -w net.ipv4.tcp_quickack=0
./run_hybrid_experiment.sh
mv hybrid_analysis analysis_default_ack

# 实验 B: 快速 ACK
sudo sysctl -w net.ipv4.tcp_quickack=1
./run_hybrid_experiment.sh
mv hybrid_analysis analysis_quick_ack

# 对比结果
python compare_ack_strategies.py analysis_default_ack/ analysis_quick_ack/
```

---

## 📈 数据分析模板

### 生成对比图表

```bash
# SSH vs WWW CDF 对比
python experiment/cdf_plot.py \
    ssh_analysis/mlt_full_series.json \
    www_analysis/mlt_full_series.json \
    --labels "SSH Traffic" "WWW Traffic" \
    -o ssh_www_cdf_comparison.png \
    --title "MLT Distribution: SSH vs WWW on Linux"
```

### 论文数据表格

运行 `analyze_by_app.py` 后，你会得到类似输出：

```
======================================================================
论文章节可用数据:
======================================================================

**SSH 流量 (Linux)**:
  - 总样本数：X,XXX
  - P50: XX.XX ms
  - P95: XXX.XX ms
  - P99: XXX.XX ms
  - ACK 类型分布:
    · syn: XXX (X.X%)
    · b2b: X,XXX (XX.X%)
    · data: X,XXX (XX.X%)

**WWW 流量 (Linux)**:
  - 总样本数：X,XXX
  - P50: X.XX ms
  - P95: XXX.XX ms
  - P99: XXX.XX ms
  - ACK 类型分布:
    · syn: XXX (X.X%)
    · b2b: X,XXX (XX.X%)
    · data: X,XXX (XX.X%)
```

---

## ✅ 实验检查清单

### 准备阶段
- [ ] 已安装 Linux 环境（虚拟机/云服务器）
- [ ] 网络设置为桥接模式
- [ ] 已安装 Python 3 和依赖
- [ ] 已测试工具包 (`python test_toolkit.py`)

### 数据采集
- [ ] 成功捕获 SSH 流量（PCAP 文件 > 1MB）
- [ ] 成功捕获 WWW 流量（PCAP 文件 > 5MB）
- [ ] PCAP 文件包含足够的 TCP 数据包（> 10,000）

### 分析阶段
- [ ] MLT 样本数 > 1000
- [ ] SSH 样本占比 > 10%
- [ ] WWW 样本占比 > 50%
- [ ] 生成了 ACK 策略分析报告
- [ ] 生成了 CDF 对比图

### 论文写作
- [ ] 整理了 SSH vs WWW 对比表格
- [ ] 记录了 Linux 环境和配置
- [ ] 说明了实验局限性
- [ ] 讨论了与 macOS 结果的差异

---

## 🐛 常见问题

### Q1: 抓不到 SSH 流量
```bash
# 主动产生大量 SSH 流量
while true; do
    ssh user@server "dd if=/dev/zero of=/dev/null bs=1M count=100" &
    sleep 5
done
```

### Q2: 权限错误
```bash
# 确保使用 sudo
sudo python3 capture_traffic.py ...

# 或将用户加入 wireshark 组
sudo usermod -aG wireshark $USER
```

### Q3: 找不到网络接口
```bash
# 查看可用接口
ip addr show
ifconfig -a

# 常见接口名：eth0, enp0s3, ens33
```

### Q4: VM 桥接模式无法抓包
```bash
# VirtualBox 中，确保：
# 1. 选择正确的物理网卡
# 2. 不是 NAT 模式
# 3. 主机防火墙没有阻止
```

---

## 📚 预期结果

基于 Linux 环境的典型结果：

| 指标 | SSH | WWW | 说明 |
|------|-----|-----|------|
| 样本数 | 2,000-5,000 | 8,000-15,000 | 取决于抓包时长 |
| P50 (ms) | 0.1-0.5 | 0.05-0.3 | WWW 通常更快 |
| P95 (ms) | 50-150 | 100-300 | SSH 延迟更稳定 |
| Delayed ACK % | 10-30% | 5-20% | Linux 较保守 |
| b2b 比例 | 50-70% | 60-80% | 主要 ACK 类型 |

---

## 🎓 学术价值

通过 Linux 实际场景测试，你可以：

1. **验证方法论有效性** - 在标准平台上证明你的方法
2. **对比不同系统** - macOS vs Linux 的差异分析
3. **控制实验变量** - 通过调整 TCP 参数进行对照实验
4. **增强论文说服力** - 真实环境数据更有说服力

---

**最后更新**: 2026-03-24  
**适用版本**: Ubuntu 20.04+, CentOS 7+, Debian 10+
