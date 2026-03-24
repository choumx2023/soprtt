#!/bin/bash
#
# VirtualBox 网络配置验证脚本
# 在 Mac 主机上运行，检查 VM 网络设置
#

echo "============================================================"
echo "VirtualBox 网络配置验证工具"
echo "============================================================"
echo ""

# 检查 VirtualBox 是否安装
if ! command -v VBoxManage &> /dev/null; then
    echo "[✗] VirtualBox 未安装或不在 PATH 中"
    echo "请确保已安装 VirtualBox"
    exit 1
fi

echo "[✓] VirtualBox 已安装：$(VBoxManage --version)"
echo ""

# 列出所有虚拟机
echo "【可用的虚拟机】"
echo "------------------------------------------------------------"
VBoxManage list vms | while read line; do
    echo "  $line"
done
echo ""

# 获取第一个虚拟机的名称（如果没有指定）
VM_NAME=$(VBoxManage list vms | head -1 | cut -d'"' -f2)

if [ -z "$VM_NAME" ]; then
    echo "[✗] 未找到虚拟机，请先创建 Ubuntu 虚拟机"
    exit 1
fi

echo "默认检查虚拟机：$VM_NAME"
echo "(如需检查其他 VM，运行：$0 <VM 名称>)"
echo ""

# 如果提供了参数，使用参数作为 VM 名称
if [ -n "$1" ]; then
    VM_NAME="$1"
fi

# 检查网络适配器设置
echo "【网络适配器配置】"
echo "------------------------------------------------------------"

# 检查适配器 1
ADAPTER1=$(VBoxManage showvminfo "$VM_NAME" --machinereadable | grep -E "networkadapter|bridge")

echo "适配器 1 设置:"
VBoxManage showvminfo "$VM_NAME" --machinereadable | grep -E "^networkadapter1=" | sed 's/networkadapter1="/  类型：/;s/"$//'
VBoxManage showvminfo "$VM_NAME" --machinereadable | grep -E "^bridgeadapter1=" | sed 's/bridgeadapter1="/  桥接接口：/;s/"$//'
VBoxManage showvminfo "$VM_NAME" --machinereadable | grep -E "^cableconnected1=" | sed 's/cableconnected1="/  连接状态：/;s/"$//'

echo ""

# 提取桥接接口名称
BRIDGE_IFACE=$(VBoxManage showvminfo "$VM_NAME" --machinereadable | grep "^bridgeadapter1=" | cut -d'"' -f2)

# 验证桥接模式
if [[ "$ADAPTER1" == *"Bridged"* ]] || [[ -n "$BRIDGE_IFACE" ]]; then
    echo "[✓] 网络模式：桥接模式 (Bridged)"
    
    if [ -n "$BRIDGE_IFACE" ]; then
        echo "[✓] 桥接到主机接口：$BRIDGE_IFACE"
        
        # 检查主机上的该接口
        echo ""
        echo "【主机网络接口状态】"
        echo "------------------------------------------------------------"
        if ifconfig "$BRIDGE_IFACE" &>/dev/null; then
            echo "[✓] 主机接口 $BRIDGE_IFACE 存在"
            IP_ADDR=$(ifconfig "$BRIDGE_IFACE" | grep "inet " | awk '{print $2}')
            echo "  IP 地址：$IP_ADDR"
        else
            echo "[⚠] 主机接口 $BRIDGE_IFACE 未找到"
        fi
    fi
else
    echo "[✗] 警告：虚拟机未使用桥接模式！"
    echo ""
    echo "请在 VirtualBox 中修改设置："
    echo "1. 右键点击虚拟机 → 设置 → 网络"
    echo "2. 连接方式：选择 '桥接网卡'"
    echo "3. 界面名称：选择你的活动网卡（通常是 en0 或 en1）"
    echo "4. 勾选 '接入网络电缆'"
fi

echo ""
echo "【Mac 主机可用网络接口】"
echo "------------------------------------------------------------"
networksetup -listallhardwareports | grep -A1 "Hardware Port\|Device" | paste - - | while read line; do
    echo "  $line"
done

echo ""
echo "============================================================"
echo "下一步操作："
echo "============================================================"
echo ""
echo "1. 启动 Ubuntu 虚拟机"
echo "2. 在 Ubuntu 中运行：ip addr show"
echo "3. 确认 eth0 接口有 IP 地址（与主机在同一网段）"
echo "4. 测试网络：ping -c 3 www.baidu.com"
echo ""
echo "如果网络正常，继续运行实验脚本："
echo "  bash setup_linux.sh"
echo "  sudo ./run_linux_experiment.sh"
echo ""
