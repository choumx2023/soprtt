#!/bin/bash
#
# Linux 实际场景测试 - 一键运行脚本
# 自动捕获 SSH + WWW 流量并完成分析
#

set -e

OUTPUT_NAME="${1:-linux_hybrid_capture}"
DURATION="${2:-600}"  # 默认 600 秒

echo "============================================================"
echo "Linux 实际场景测试 - 一键运行"
echo "============================================================"
echo ""

# 检测网络接口
INTERFACE=""
if ip addr show eth0 &>/dev/null; then
    INTERFACE="eth0"
elif ip addr show enp0s3 &>/dev/null; then
    INTERFACE="enp0s3"
elif ip addr show ens33 &>/dev/null; then
    INTERFACE="ens33"
else
    echo "[!] 未找到常见网络接口，请手动指定:"
    ip addr show | grep -E "^[0-9]+:" | awk -F: '{print "  - " $2}'
    echo ""
    read -p "请输入网络接口名称: " INTERFACE
fi

echo "使用网络接口：$INTERFACE"
echo "捕获时长：${DURATION} 秒"
echo "输出文件：${OUTPUT_NAME}.pcap"
echo ""

# 检查是否 root
if [ "$EUID" -ne 0 ]; then 
    echo "[⚠]  需要使用 sudo 权限"
    echo "请使用以下命令运行:"
    echo "  sudo ./run_linux_experiment.sh [output_name] [duration]"
    exit 1
fi

# 开始抓包
echo "============================================================"
echo "[1/4] 开始捕获网络流量..."
echo "============================================================"
echo ""

python3 capture_traffic.py -i "$INTERFACE" -t "$DURATION" -o "$OUTPUT_NAME" &
CAPTURE_PID=$!

# 等待 5 秒让抓包稳定
sleep 5

# 产生流量
echo ""
echo "============================================================"
echo "[2/4] 产生 SSH 和 WWW 流量..."
echo "============================================================"
echo ""

# SSH 流量 (后台运行)
echo "→ 产生 SSH 流量..."
if command -v ssh &> /dev/null; then
    # 尝试连接到常见服务器
    (ssh github.com "cat /dev/zero > /dev/null" 2>/dev/null || true) &
    (ssh gitlab.com "cat /dev/zero > /dev/null" 2>/dev/null || true) &
    echo "  ✓ SSH 流量生成中..."
else
    echo "  ⚠ ssh 命令不可用，跳过 SSH 流量"
fi

# WWW 流量
echo "→ 产生 WWW (HTTP/HTTPS) 流量..."
if command -v curl &> /dev/null; then
    curl -o /dev/null -s https://www.example.com &
    curl -o /dev/null -s https://httpbin.org/stream-bytes/5M &
    curl -o /dev/null -s https://www.wikipedia.org &
    echo "  ✓ CURL 正在下载测试数据..."
fi

if command -v wget &> /dev/null; then
    wget -O /dev/null -q https://httpbin.org/stream-bytes/3M &
    echo "  ✓ WGET 正在下载测试数据..."
fi

echo ""
echo "流量生成完成，等待抓包结束..."
echo "(按 Ctrl+C 可提前停止，但仍会分析已捕获的数据)"
echo ""

# 等待抓包完成
wait $CAPTURE_PID 2>/dev/null || true

# 杀死后台进程
kill $(jobs -p) 2>/dev/null || true

echo ""
echo "============================================================"
echo "[3/4] 分析 PCAP 文件..."
echo "============================================================"
echo ""

python3 experiment/quick_validate.py "${OUTPUT_NAME}.pcap" -o "${OUTPUT_NAME}_analysis"

echo ""
echo "============================================================"
echo "[4/4] 按应用场景分类统计..."
echo "============================================================"
echo ""

python3 analyze_by_app.py "${OUTPUT_NAME}_analysis/mlt_full_series.json"

echo ""
echo "============================================================"
echo "✓ 实验完成！"
echo "============================================================"
echo ""
echo "结果文件:"
echo "  - PCAP 文件：${OUTPUT_NAME}.pcap"
echo "  - 分析报告：${OUTPUT_NAME}_analysis/"
echo "    · mlt_full_series.json"
echo "    · ack_strategy_report.json"
echo "    · ack_strategy_comparison.png"
echo "    · mlt_time_series.png"
echo ""
echo "下一步:"
echo "  1. 查看分析结果："
echo "     cat ${OUTPUT_NAME}_analysis/ack_strategy_report.json"
echo ""
echo "  2. 生成对比图表："
echo "     python3 experiment/cdf_plot.py ..."
echo ""
echo "  3. 整理论文数据（见 analyze_by_app.py 输出）"
echo ""
