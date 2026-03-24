#!/bin/bash
#
# Linux 环境一键安装脚本
# 用于在 Ubuntu/Debian/CentOS 上快速配置 MLT 实验环境
#

set -e

echo "============================================================"
echo "Linux 环境 MLT 实验工具安装脚本"
echo "============================================================"
echo ""

# 检测系统类型
if [ -f /etc/debian_version ]; then
    SYSTEM="debian"
    echo "[✓] 检测到 Debian/Ubuntu 系统"
elif [ -f /etc/redhat-release ]; then
    SYSTEM="redhat"
    echo "[✓] 检测到 RHEL/CentOS 系统"
else
    SYSTEM="unknown"
    echo "[⚠] 未知系统，尝试使用通用方法"
fi

echo ""

# 1. 安装系统依赖
echo "[1/5] 安装系统依赖..."

install_debian() {
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv tcpdump git wget curl
}

install_redhat() {
    sudo yum install -y python3 python3-pip tcpdump git wget curl
}

case $SYSTEM in
    debian)
        install_debian
        ;;
    redhat)
        install_redhat
        ;;
    *)
        # 尝试自动安装
        if command -v apt &> /dev/null; then
            install_debian
        elif command -v yum &> /dev/null; then
            install_redhat
        else
            echo "[!] 无法自动安装依赖，请手动安装 python3, pip3, tcpdump"
            exit 1
        fi
        ;;
esac

echo "[✓] 系统依赖安装完成"
echo ""

# 2. 检查并创建 Python 虚拟环境
echo "[2/5] 配置 Python 虚拟环境..."

if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "[✓] 虚拟环境已激活"
echo ""

# 3. 升级 pip
echo "[3/5] 升级 pip..."
pip install --upgrade pip

# 4. 安装 Python 依赖
echo "[4/5] 安装 Python 依赖..."

cat > requirements.txt << EOF
scapy>=2.5.0
numpy>=1.20.0
scipy>=1.7.0
matplotlib>=3.4.0
EOF

pip install -r requirements.txt
echo "[✓] Python 依赖安装完成"
echo ""

# 5. 验证安装
echo "[5/5] 验证安装..."

python3 -c "import scapy; import numpy; import scipy; print('所有依赖加载成功')"

echo ""
echo "============================================================"
echo "✓ 安装完成！"
echo "============================================================"
echo ""
echo "下一步操作:"
echo ""
echo "1. 查看网络接口:"
echo "   ip addr show"
echo ""
echo "2. 开始抓包 (替换 eth0 为你的接口名):"
echo "   sudo python3 capture_traffic.py -i eth0 -t 600 -o my_capture"
echo ""
echo "3. 分析 PCAP 文件:"
echo "   python3 experiment/quick_validate.py my_capture.pcap -o analysis"
echo ""
echo "4. 按应用场景分类:"
echo "   python3 analyze_by_app.py analysis/mlt_full_series.json"
echo ""
echo "提示: 确保在抓包时产生 SSH 和 WWW 流量"
echo ""
