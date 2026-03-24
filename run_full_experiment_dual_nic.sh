#!/bin/bash
#
# 完整对照实验脚本 - 双网卡版本 (NAT + Host-Only)
#
# 特性:
# 1. 支持双网卡配置（NAT 上网 + Host-Only 通 Mac）
# 2. ICMP 持续监测 Mac 或网关
# 3. 多并发 SSH/HTTP 会话
# 4. 四组 ACK 策略对照
#
# 使用方法:
#   sudo ./run_full_experiment_dual_nic.sh [duration] [mac_ip]
#
# 示例:
#   sudo ./run_full_experiment_dual_nic.sh 300 192.168.10.50
#

set -e

DURATION="${1:-300}"
MAC_IP="${2:-ask}"         # Mac 在 Host-Only 网络的 IP
SSH_SESSIONS=5
HTTP_SESSIONS=10
OUTPUT_DIR="full_experiment_dual_$(date +%Y%m%d_%H%M%S)"

echo "============================================================"
echo "完整对照实验 - 双网卡版本 (NAT + Host-Only)"
echo "============================================================"
echo ""

# ==================== 检测双网卡 ====================
echo "【检测网络接口】"

# 获取两个网卡的 IP
NAT_IP=$(ip addr show ens33 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
HOSTONLY_IP=$(ip addr show ens34 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d'/' -f1)

if [ -z "$NAT_IP" ]; then
    echo "⚠ 未检测到 ens33 (NAT 网卡)"
fi

if [ -z "$HOSTONLY_IP" ]; then
    echo "⚠ 未检测到 ens34 (Host-Only 网卡)"
    echo ""
    echo "请确认已在 VMware 中添加第二个网卡:"
    echo "  1. 关闭虚拟机"
    echo "  2. VM → Settings → Add... → Network Adapter"
    echo "  3. 选择 Host-only 模式"
    echo "  4. 启动虚拟机"
    exit 1
fi

echo "  ✓ ens33 (NAT): $NAT_IP"
echo "  ✓ ens34 (Host-Only): $HOSTONLY_IP"
echo ""

# ==================== 确定 Mac IP ====================
if [ "$MAC_IP" = "ask" ]; then
    echo "【配置 ICMP 监测目标】"
    echo ""
    echo "请在 Mac 上运行以下命令查看 Host-Only 网络 IP:"
    echo "  ifconfig | grep 'inet ' | grep -v 127.0.0.1"
    echo ""
    echo "Mac 的 IP 通常是 192.168.10.x 或 192.168.xx.x"
    echo "(必须与 Ubuntu 的 ens34 在同一网段)"
    echo ""
    read -p "请输入 Mac 在 Host-Only 网络的 IP: " MAC_IP
    
    echo ""
    echo "【配置确认】"
    echo "  Ubuntu Host-Only IP: $HOSTONLY_IP"
    echo "  Mac IP: $MAC_IP"
    echo "  ICMP 监测：从 Ubuntu ping Mac ($MAC_IP)"
    echo "  SSH/HTTP: 从 Mac 连接到 Ubuntu ($HOSTONLY_IP)"
    echo ""
else
    echo "【配置确认】"
    echo "  Mac IP: $MAC_IP"
    echo "  ICMP 监测：从 Ubuntu ping Mac ($MAC_IP)"
    echo ""
fi

read -p "准备开始实验，按 Enter 继续..."

mkdir -p "$OUTPUT_DIR"

# ==================== Step 0: 启动 ICMP 持续监测 ====================
echo ""
echo "============================================================"
echo "[Step 0] 启动 ICMP 持续监测 (Ubuntu → Mac)"
echo "============================================================"
echo ""

cat > "$OUTPUT_DIR/icmp_monitor.py" << 'PYTHON_EOF'
#!/usr/bin/env python3
import subprocess
import time
import json
import sys
from datetime import datetime

def ping_once(target):
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '2', target],
            capture_output=True,
            text=True,
            timeout=3
        )
        output = result.stdout + result.stderr
        import re
        match = re.search(r'time[=<](\d+\.?\d*)\s*ms', output)
        if match:
            return float(match.group(1))
        return None
    except:
        return None

def monitor(target, duration, output_file):
    print(f"开始 ICMP 监测：{target}, 持续 {duration} 秒\n")
    
    results = []
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        rtt = ping_once(target)
        timestamp = datetime.now().isoformat()
        
        results.append({
            'timestamp': timestamp,
            'rtt_ms': rtt,
            'elapsed_s': round(time.time() - start_time, 1)
        })
        
        count += 1
        status = f"{rtt:.2f} ms" if rtt else "timeout"
        print(f"  [{count}] {status}")
        
        time.sleep(2)
    
    with open(output_file, 'w') as f:
        json.dump({
            'target': target,
            'duration_s': duration,
            'interval_s': 2,
            'measurements': results
        }, f, indent=2)
    
    rtts = [r['rtt_ms'] for r in results if r['rtt_ms'] is not None]
    if rtts:
        import statistics
        print(f"\n✓ ICMP 监测完成")
        print(f"  样本数：{len(rtts)}")
        print(f"  平均 RTT: {statistics.mean(rtts):.2f} ms")
        print(f"  标准差：{statistics.stdev(rtts):.2f} ms")
    else:
        print("✗ 没有成功的测量")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: icmp_monitor.py <target> <duration> <output_file>")
        sys.exit(1)
    
    monitor(sys.argv[1], int(sys.argv[2]), sys.argv[3])
PYTHON_EOF

chmod +x "$OUTPUT_DIR/icmp_monitor.py"

TOTAL_DURATION=$((DURATION * 4 + 60))

echo "启动 ICMP 监测后台进程..."
echo "  目标：$MAC_IP"
echo "  时长：${TOTAL_DURATION} 秒"
echo ""

nohup python3 "$OUTPUT_DIR/icmp_monitor.py" \
    "$MAC_IP" \
    "$TOTAL_DURATION" \
    "$OUTPUT_DIR/icmp_continuous.json" \
    > "$OUTPUT_DIR/icmp_monitor.log" 2>&1 &

ICMP_PID=$!
echo "✓ ICMP 监测进程已启动 (PID: $ICMP_PID)"
echo ""

sleep 3

# ==================== 辅助函数 ====================

start_http_server() {
    if ! pgrep -f "python3 -m http.server 8080" > /dev/null; then
        echo "  启动 HTTP 服务器..."
        nohup python3 -m http.server 8080 > /tmp/http_server.log 2>&1 &
        sleep 2
    fi
}

generate_traffic_to_mac() {
    echo "  产生到 Mac ($MAC_IP) 的流量..."
    
    # SSH 会话（多个）
    for i in $(seq 1 $SSH_SESSIONS); do
        (ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 student@$MAC_IP "cat /dev/zero > /dev/null" 2>/dev/null || true) &
    done
    
    # HTTP 会话（多个）- 需要 Mac 上有 HTTP 服务器
    # 这里简化为只产生 SSH 流量
    for i in $(seq 1 $HTTP_SESSIONS); do
        (curl -o /dev/null -s -m 5 http://$MAC_IP:8080/ 2>/dev/null || true) &
    done
    
    sleep 3
    echo "  ✓ 流量生成中..."
}

run_tcp_experiment() {
    local exp_name=$1
    local delayed_ack=$2
    local quick_ack=$3
    local output_name=$4
    
    echo ""
    echo "============================================================"
    echo "[$exp_name]"
    echo "============================================================"
    echo ""
    
    echo "设置 TCP 参数..."
    sudo sysctl -w net.ipv4.tcp_delayed_ack=$delayed_ack
    sudo sysctl -w net.ipv4.tcp_quickack=$quick_ack
    
    echo "当前配置:"
    sysctl net.ipv4.tcp_delayed_ack
    sysctl net.ipv4.tcp_quickack
    echo ""
    
    start_http_server
    
    echo "开始抓包 (${DURATION} 秒)..."
    echo "同时产生到 Mac 的流量..."
    
    # 在后台产生流量
    generate_traffic_to_mac &
    TRAFFIC_PID=$!
    
    # 开始抓包（监听 ens34 - Host-Only 网卡）
    python3 capture_traffic.py -i ens34 -t "$DURATION" -o "$OUTPUT_DIR/${output_name}"
    
    # 等待流量进程结束
    wait $TRAFFIC_PID 2>/dev/null || true
    
    echo ""
    echo "分析数据..."
    python3 experiment/quick_validate.py "$OUTPUT_DIR/${output_name}.pcap" -o "$OUTPUT_DIR/${output_name}_analysis" 2>/dev/null || {
        echo "⚠ 分析失败，跳过"
        return 1
    }
    
    echo ""
    echo "✓ $exp_name 完成"
}

# ==================== 实验 A-D ====================

run_tcp_experiment "实验 A" 1 0 "expA_default"
echo ""
read -p "按 Enter 继续到实验 B..."

run_tcp_experiment "实验 B" 0 0 "expB_no_delayed"
echo ""
read -p "按 Enter 继续到实验 C..."

run_tcp_experiment "实验 C" 0 1 "expC_quick_ack"
echo ""
read -p "按 Enter 继续到实验 D..."

run_tcp_experiment "实验 D" 1 0 "expD_restore"

# ==================== 停止 ICMP 监测 ====================
echo ""
echo "停止 ICMP 监测进程..."
kill $ICMP_PID 2>/dev/null || true
wait $ICMP_PID 2>/dev/null || true

# ==================== 生成报告 ====================
echo ""
echo "============================================================"
echo "生成综合分析报告"
echo "============================================================"
echo ""

python3 << 'REPORT_EOF'
import json
import os
from pathlib import Path

output_dir = os.environ.get('OUTPUT_DIR', '.')

print("=" * 80)
print("实验结果综合分析")
print("=" * 80)
print()

# 加载 ICMP 数据
print("【1. ICMP 持续监测数据 (Ubuntu → Mac)】")
print("-" * 80)

icmp_file = f"{output_dir}/icmp_continuous.json"
if os.path.exists(icmp_file):
    with open(icmp_file, 'r') as f:
        icmp_data = json.load(f)
    
    measurements = icmp_data['measurements']
    rtts = [m['rtt_ms'] for m in measurements if m['rtt_ms'] is not None]
    
    if rtts:
        import statistics
        print(f"监测时长：{icmp_data['duration_s']} 秒")
        print(f"样本数：{len(rtts)}")
        print(f"平均 RTT: {statistics.mean(rtts):.2f} ms")
        print(f"标准差：{statistics.stdev(rtts):.2f} ms")
    else:
        print("⚠ 没有有效的 ICMP 数据")
else:
    print("⚠ ICMP 数据文件不存在")

print()
print("【2. TCP ACK 实验结果】")
print("-" * 80)

experiments = ['expA_default', 'expB_no_delayed', 'expC_quick_ack', 'expD_restore']

for exp in experiments:
    analysis_dir = f"{output_dir}/{exp}_analysis"
    json_file = f"{analysis_dir}/ack_strategy_report.json"
    
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        total = data['summary']['total_samples']
        cats = data['delayed_ack_impact']['categories']
        weighted_error = sum(c['avg_deviation_ms'] * c['count'] for c in cats.values()) / total if total > 0 else 0
        accuracy = sum(c['accuracy_within_20ms'] * c['count'] for c in cats.values()) / total if total > 0 else 0
        
        print(f"{exp.replace('_', ' '):<25} | 样本：{total:>6} | 误差：{weighted_error:>7.2f} ms | 精度：{accuracy:>5.1f}%")
    else:
        print(f"{exp:<25} | ⚠ 数据缺失")

print()
print("=" * 80)
print("✓ 综合分析完成")
print("=" * 80)
REPORT_EOF

# ==================== 完成 ====================
echo ""
echo "============================================================"
echo "✓ 完整实验全部完成！"
echo "============================================================"
echo ""
echo "【结果文件】"
echo "  - $OUTPUT_DIR/icmp_continuous.json       ← ICMP 监测数据"
echo "  - $OUTPUT_DIR/expA_default_analysis/     ← 四组实验结果"
echo "  - $OUTPUT_DIR/expB_no_delayed_analysis/"
echo "  - $OUTPUT_DIR/expC_quick_ack_analysis/"
echo "  - $OUTPUT_DIR/expD_restore_analysis/"
echo ""

# 恢复默认配置
sudo sysctl -w net.ipv4.tcp_delayed_ack=1
sudo sysctl -w net.ipv4.tcp_quickack=0
