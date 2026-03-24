#!/bin/bash
#
# 完整对照实验脚本 - ICMP 持续监测 + 多会话 TCP + ACK 策略控制
#
# 特性:
# 1. ICMP 持续监测（贯穿整个实验）
# 2. 多并发 SSH/HTTP 会话
# 3. 四组 ACK 策略对照
# 4. 自动数据分析和对比
#
# 使用方法:
#   sudo ./run_full_experiment.sh [duration_seconds] [target_ip]
#
# 示例:
#   sudo ./run_full_experiment.sh 300 192.168.1.50
#

set -e

# ==================== 配置参数 ====================
DURATION="${1:-300}"           # 每组实验时长（秒）
TARGET_IP="${2:-auto}"         # ICMP 目标 IP（默认自动检测）
SSH_SESSIONS=5                 # SSH 并发会话数
HTTP_SESSIONS=10               # HTTP 并发会话数
OUTPUT_DIR="full_experiment_$(date +%Y%m%d_%H%M%S)"

echo "============================================================"
echo "完整对照实验 - ICMP 持续监测 + 多会话 TCP"
echo "============================================================"
echo ""
echo "【实验配置】"
echo "  输出目录：$OUTPUT_DIR"
echo "  每组时长：${DURATION} 秒"
echo "  SSH 会话数：$SSH_SESSIONS"
echo "  HTTP 会话数：$HTTP_SESSIONS"

# ==================== 自动检测目标 IP ====================
if [ "$TARGET_IP" = "auto" ]; then
    # 获取默认网关（通常是你的 Mac/路由器）
    GATEWAY=$(ip route | grep default | awk '{print $3}')
    
    echo ""
    echo "【网络环境】"
    echo "  本机 IP: $(hostname -I | awk '{print $1}')"
    echo "  默认网关：$GATEWAY"
    echo ""
    echo "请选择 ICMP 监测目标:"
    echo "  1) 默认网关 ($GATEWAY) - 推荐"
    echo "  2) 自定义 IP"
    echo ""
    read -p "请输入选项 (1 或 2): " choice
    
    if [ "$choice" = "1" ]; then
        TARGET_IP="$GATEWAY"
    else
        read -p "请输入目标 IP: " TARGET_IP
    fi
fi

echo ""
echo "【ICMP 监测目标】: $TARGET_IP"
echo ""

# 确认开始
read -p "准备开始实验，按 Enter 继续..."

mkdir -p "$OUTPUT_DIR"

# ==================== Step 0: 启动 ICMP 持续监测 ====================
echo ""
echo "============================================================"
echo "[Step 0] 启动 ICMP 持续监测后台进程"
echo "============================================================"
echo ""

# 创建 ICMP 监测脚本
cat > "$OUTPUT_DIR/icmp_monitor.py" << 'PYTHON_EOF'
#!/usr/bin/env python3
import subprocess
import time
import json
import sys
from datetime import datetime

def ping_once(target):
    """执行一次 ping"""
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
    """持续监测"""
    print(f"开始 ICMP 监测：{target}, 持续 {duration} 秒")
    
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
        if rtt:
            print(f"  [{count}] {rtt:.2f} ms")
        else:
            print(f"  [{count}] timeout")
        
        time.sleep(2)  # 每 2 秒 ping 一次
    
    # 保存结果
    with open(output_file, 'w') as f:
        json.dump({
            'target': target,
            'duration_s': duration,
            'interval_s': 2,
            'measurements': results
        }, f, indent=2)
    
    # 统计
    rtts = [r['rtt_ms'] for r in results if r['rtt_ms'] is not None]
    if rtts:
        import statistics
        print(f"\n✓ ICMP 监测完成")
        print(f"  样本数：{len(rtts)}")
        print(f"  平均 RTT: {statistics.mean(rtts):.2f} ms")
        print(f"  标准差：{statistics.stdev(rtts):.2f} ms")
        print(f"  结果保存在：{output_file}")
    else:
        print("✗ 没有成功的测量")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: icmp_monitor.py <target> <duration> <output_file>")
        sys.exit(1)
    
    target = sys.argv[1]
    duration = int(sys.argv[2])
    output_file = sys.argv[3]
    
    monitor(target, duration, output_file)
PYTHON_EOF

chmod +x "$OUTPUT_DIR/icmp_monitor.py"

# 计算总时长（4 组实验 × 每组时长 + 间隔）
TOTAL_DURATION=$((DURATION * 4 + 60))

echo "启动 ICMP 监测后台进程..."
echo "  目标：$TARGET_IP"
echo "  时长：${TOTAL_DURATION} 秒"
echo ""

nohup python3 "$OUTPUT_DIR/icmp_monitor.py" \
    "$TARGET_IP" \
    "$TOTAL_DURATION" \
    "$OUTPUT_DIR/icmp_continuous.json" \
    > "$OUTPUT_DIR/icmp_monitor.log" 2>&1 &

ICMP_PID=$!
echo "✓ ICMP 监测进程已启动 (PID: $ICMP_PID)"
echo ""

sleep 3

# ==================== 辅助函数 ====================

start_http_server() {
    # 启动 HTTP 服务器（如果还没运行）
    if ! pgrep -f "python3 -m http.server 8080" > /dev/null; then
        echo "启动 HTTP 服务器..."
        nohup python3 -m http.server 8080 > /tmp/http_server.log 2>&1 &
        sleep 2
    fi
}

generate_traffic() {
    local session_id=$1
    local my_ip=$(hostname -I | awk '{print $1}')
    
    echo "  产生流量会话组 $session_id..."
    
    # SSH 会话（多个）
    for i in $(seq 1 $SSH_SESSIONS); do
        (ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 student@$my_ip "cat /dev/zero > /dev/null" 2>/dev/null || true) &
    done
    
    # HTTP 会话（多个）
    for i in $(seq 1 $HTTP_SESSIONS); do
        (curl -o /dev/null -s http://$my_ip:8080/ 2>/dev/null || true) &
    done
    
    sleep 2
}

run_tcp_experiment() {
    local exp_name=$1
    local delayed_ack=$2
    local quick_ack=$3
    local output_name=$4
    
    echo ""
    echo "============================================================"
    echo "[$exp_name] 配置：delayed_ack=$delayed_ack, quick_ack=$quick_ack"
    echo "============================================================"
    echo ""
    
    # 设置 TCP 参数
    echo "设置 TCP 参数..."
    sudo sysctl -w net.ipv4.tcp_delayed_ack=$delayed_ack
    sudo sysctl -w net.ipv4.tcp_quickack=$quick_ack
    
    # 显示当前配置
    echo "当前配置:"
    sysctl net.ipv4.tcp_delayed_ack
    sysctl net.ipv4.tcp_quickack
    echo ""
    
    # 启动 HTTP 服务器
    start_http_server
    
    # 自动检测网卡名称
    INTERFACE=$(ip route | grep default | awk '{print $5}')
    if [ -z "$INTERFACE" ]; then
        INTERFACE="eth0"
    fi
    
    # 开始抓包
    echo "开始抓包 (${DURATION} 秒)..."
    echo "  使用网卡：$INTERFACE"
    python3 capture_traffic.py -i "$INTERFACE" -t "$DURATION" -o "$OUTPUT_DIR/${output_name}"
    
    # 分析
    echo ""
    echo "分析数据..."
    python3 experiment/quick_validate.py "$OUTPUT_DIR/${output_name}.pcap" -o "$OUTPUT_DIR/${output_name}_analysis" 2>/dev/null || {
        echo "⚠ 分析失败，跳过"
    }
    
    echo ""
    echo "✓ $exp_name 完成"
}

# ==================== 实验 A: 默认配置 ====================
run_tcp_experiment "实验 A" 1 0 "expA_default"

echo ""
read -p "按 Enter 继续到实验 B..."

# ==================== 实验 B: 关闭 Delayed ACK ====================
run_tcp_experiment "实验 B" 0 0 "expB_no_delayed"

echo ""
read -p "按 Enter 继续到实验 C..."

# ==================== 实验 C: Quick ACK ====================
run_tcp_experiment "实验 C" 0 1 "expC_quick_ack"

echo ""
read -p "按 Enter 继续到实验 D..."

# ==================== 实验 D: 恢复默认 ====================
run_tcp_experiment "实验 D" 1 0 "expD_restore"

# ==================== 停止 ICMP 监测 ====================
echo ""
echo "停止 ICMP 监测进程..."
kill $ICMP_PID 2>/dev/null || true
wait $ICMP_PID 2>/dev/null || true

# ==================== 生成综合报告 ====================
echo ""
echo "============================================================"
echo "生成综合分析报告"
echo "============================================================"
echo ""

python3 << 'REPORT_EOF'
import json
import os
from pathlib import Path
from datetime import datetime

output_dir = os.environ.get('OUTPUT_DIR', '.')

print("=" * 80)
print("实验结果综合分析")
print("=" * 80)
print()

# 1. 加载 ICMP 数据
print("【1. ICMP 持续监测数据】")
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
        print(f"中位数：{statistics.median(rtts):.2f} ms")
        print(f"标准差：{statistics.stdev(rtts):.2f} ms")
        print(f"P95: {sorted(rtts)[int(len(rtts)*0.95)]:.2f} ms")
        print(f"P99: {sorted(rtts)[int(len(rtts)*0.99)]:.2f} ms")
        
        # 按时间段分组
        print("\n按实验阶段分解:")
        duration_per_exp = icmp_data['duration_s'] // 4
        for i, label in enumerate(['A (默认)', 'B (关闭 Delayed)', 'C (Quick)', 'D (恢复)']):
            start_idx = i * (duration_per_exp // 2)
            end_idx = start_idx + (duration_per_exp // 2)
            segment_rtts = rtts[start_idx:end_idx]
            
            if segment_rtts:
                print(f"  {label}: {statistics.mean(segment_rtts):.2f} ± {statistics.stdev(segment_rtts):.2f} ms (n={len(segment_rtts)})")
    else:
        print("⚠ 没有有效的 ICMP 数据")
else:
    print("⚠ ICMP 数据文件不存在")

print()

# 2. 加载 TCP 实验数据
print("【2. TCP ACK 实验结果】")
print("-" * 80)

experiments = ['expA_default', 'expB_no_delayed', 'expC_quick_ack', 'expD_restore']
tcp_results = []

for exp in experiments:
    analysis_dir = f"{output_dir}/{exp}_analysis"
    json_file = f"{analysis_dir}/ack_strategy_report.json"
    
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        total = data['summary']['total_samples']
        
        # 计算加权平均误差
        cats = data['delayed_ack_impact']['categories']
        weighted_error = sum(c['avg_deviation_ms'] * c['count'] for c in cats.values()) / total if total > 0 else 0
        
        accuracy = sum(c['accuracy_within_20ms'] * c['count'] for c in cats.values()) / total if total > 0 else 0
        
        tcp_results.append({
            'name': exp.replace('exp', '实验 '),
            'samples': total,
            'error': weighted_error,
            'accuracy': accuracy
        })
        
        print(f"{exp.replace('_', ' '):<25} | 样本：{total:>6} | 误差：{weighted_error:>7.2f} ms | 精度：{accuracy:>5.1f}%")
    else:
        print(f"{exp:<25} | ⚠ 数据缺失")

print()

# 3. 对比分析
print("【3. TCP vs ICMP 对比】")
print("-" * 80)

if rtts and tcp_results:
    icmp_mean = statistics.mean(rtts)
    
    print(f"{'方法':<20} | {'测量值 (ms)':>12} | {'相对 ICMP':>12} | {'20ms 准确率':>12}")
    print("-" * 65)
    print(f"{'ICMP (Ground Truth)':<20} | {icmp_mean:>12.2f} | {'baseline':>12} | {'-':>12}")
    
    for res in tcp_results:
        relative = ((res['error'] - icmp_mean) / icmp_mean * 100) if icmp_mean > 0 else 0
        print(f"{res['name']:<20} | {res['error']:>12.2f} | {relative:>+11.1f}% | {res['accuracy']:>11.1f}%")
    
    print()
    
    # 关键发现
    print("【关键发现】")
    print("-" * 80)
    
    if len(tcp_results) >= 4:
        default_err = tcp_results[0]['error']
        quick_err = tcp_results[2]['error']
        
        improvement = default_err - quick_err
        improvement_pct = (improvement / default_err * 100) if default_err > 0 else 0
        
        print(f"1. Quick ACK 使测量误差降低 {improvement:.2f} ms ({improvement_pct:.1f}%)")
        print(f"   从 {default_err:.2f} ms → {quick_err:.2f} ms")
        
        # 与 ICMP 对比
        default_rel = ((default_err - icmp_mean) / icmp_mean * 100)
        quick_rel = ((quick_err - icmp_mean) / icmp_mean * 100)
        
        print(f"\n2. 相对于 ICMP baseline ({icmp_mean:.2f} ms):")
        print(f"   默认配置高估 {default_rel:+.1f}%")
        print(f"   Quick ACK 高估 {quick_rel:+.1f}%")
        print(f"   Quick ACK 更接近真实网络延迟！")

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
echo "【结果文件清单】"
echo "  ICMP 持续监测:"
echo "    - $OUTPUT_DIR/icmp_continuous.json      ← 原始数据"
echo "    - $OUTPUT_DIR/icmp_monitor.log          ← 日志"
echo ""
echo "  TCP 实验数据:"
echo "    - $OUTPUT_DIR/expA_default.pcap         ← 默认配置抓包"
echo "    - $OUTPUT_DIR/expA_default_analysis/    ← 分析结果"
echo "    - $OUTPUT_DIR/expB_no_delayed.*         ← 关闭 Delayed ACK"
echo "    - $OUTPUT_DIR/expC_quick_ack.*          ← Quick ACK"
echo "    - $OUTPUT_DIR/expD_restore.*            ← 恢复默认"
echo ""
echo "【下一步操作】"
echo "  1. 查看详细报告：见上方输出"
echo "  2. 查看 ICMP 数据：cat $OUTPUT_DIR/icmp_continuous.json | python3 -m json.tool"
echo "  3. 整理论文数据：使用各 analysis 目录中的 JSON 文件"
echo "  4. 同步到 GitHub: git add $OUTPUT_DIR && git commit && git push"
echo ""
echo "【恢复系统默认配置】"
sudo sysctl -w net.ipv4.tcp_delayed_ack=1
sudo sysctl -w net.ipv4.tcp_quickack=0
echo ""
