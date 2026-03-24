#!/usr/bin/env python3
"""
Linux 本地 TCP 行为测试工具

目的：
- 研究 Linux 本机的 ACK 策略
- 不依赖外部网站
- 完全可控的实验环境

使用方式:
    # 模式 1: 本地自测（lo 接口）
    sudo python3 local_linux_test.py --mode loopback
    
    # 模式 2: 监听模式（等待外部连接）
    sudo python3 local_linux_test.py --mode listen
    
    # 模式 3: 主动连接（连接到外部）
    sudo python3 local_linux_test.py --mode connect --target 192.168.1.100
"""

import argparse
import subprocess
import threading
import time
import socket
import os
from datetime import datetime


class LocalTrafficGenerator:
    """本地流量生成器 - 不依赖外部网络"""
    
    def __init__(self, mode: str, target: str = None):
        self.mode = mode
        self.target = target
        self.processes = []
        self.running = False
        
    def start(self):
        """根据模式启动不同的流量生成"""
        self.running = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动 {self.mode} 模式...")
        
        if self.mode == 'loopback':
            self._start_loopback()
        elif self.mode == 'listen':
            self._start_listener()
        elif self.mode == 'connect':
            self._start_connector()
    
    def _start_loopback(self):
        """本地回环测试 - 完全在 localhost 内"""
        print("\n=== 本地回环测试模式 ===")
        print("此模式下，流量完全在 Linux 本机内部")
        print("可以精确控制服务器和客户端行为\n")
        
        # 1. 启动本地 HTTP 服务器
        print("[1] 启动本地 HTTP 服务器 (端口 8080)...")
        http_server = subprocess.Popen(
            ['python3', '-m', 'http.server', '8080'],
            cwd='/tmp',
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.processes.append(http_server)
        time.sleep(1)
        
        # 2. 启动本地 FTP 服务器（可选）
        print("[2] 启动本地 Python FTP 服务器 (端口 2121)...")
        # 简化版，实际需要更复杂的设置
        
        # 3. 产生多个并发连接
        print("[3] 启动并发客户端连接...")
        for i in range(5):
            self._create_local_client(i)
        
        print("✓ 本地回环测试已启动\n")
    
    def _create_local_client(self, client_id: int):
        """创建本地客户端连接"""
        
        # 不同的访问模式
        modes = [
            # 模式 1: 大文件下载
            f'curl -o /dev/null -s http://localhost:8080/../etc/passwd',
            
            # 模式 2: 持续连接
            f'curl -o /dev/null -s http://localhost:8080/ && sleep 2',
            
            # 模式 3: 高频小请求
            f'for i in {{1..10}}; do curl -s http://localhost:8080/ > /dev/null; done',
        ]
        
        cmd = modes[client_id % len(modes)]
        
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.processes.append(proc)
        print(f"  客户端 {client_id}: 已启动")
    
    def _start_listener(self):
        """监听模式 - 等待外部连接"""
        print("\n=== 监听模式 ===")
        print("等待外部机器连接到此 Linux 系统\n")
        
        # 获取本机 IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        print(f"本机 IP 地址：{local_ip}")
        print(f"SSH 端口：22")
        print(f"HTTP 端口：80")
        print("")
        print("从其他机器连接:")
        print(f"  ssh student@{local_ip} \"cat /dev/zero > /dev/null\"")
        print(f"  curl http://{local_ip}/largefile")
        print("")
        print("按 Ctrl+C 停止...\n")
        
        # 保持运行，等待连接
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    def _start_connector(self):
        """主动连接模式 - 连接到指定目标"""
        if not self.target:
            print("错误：--target 参数必填")
            return
        
        print(f"\n=== 主动连接模式 ===")
        print(f"目标服务器：{self.target}\n")
        
        # 产生多种类型的连接
        connections = [
            f'ssh -o StrictHostKeyChecking=no {self.target} "cat /dev/zero > /dev/null"',
            f'curl -o /dev/null -s http://{self.target}/',
            f'wget -O /dev/null -q http://{self.target}/test',
        ]
        
        for i, cmd in enumerate(connections):
            print(f"[连接 {i+1}] {cmd[:60]}...")
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.processes.append(proc)
        
        print("\n✓ 连接已建立\n")
    
    def maintain(self):
        """维护连接"""
        while self.running:
            # 清理已完成的进程
            self.processes = [p for p in self.processes if p.poll() is None]
            
            # 如果是 loopback 模式，定期产生新连接
            if self.mode == 'loopback' and len(self.processes) < 3:
                for i in range(2):
                    self._create_local_client(len(self.processes))
            
            time.sleep(5)
    
    def stop(self):
        """停止所有进程"""
        print("\n停止流量生成...")
        self.running = False
        
        for proc in self.processes:
            try:
                proc.terminate()
            except:
                pass
        
        print("✓ 已停止\n")


def main():
    parser = argparse.ArgumentParser(
        description='Linux 本地 TCP 行为测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 模式 1: 本地回环测试（推荐）
  sudo python3 local_linux_test.py --mode loopback
  
  # 模式 2: 监听模式（等待外部连接）
  sudo python3 local_linux_test.py --mode listen
  
  # 模式 3: 主动连接到特定目标
  sudo python3 local_linux_test.py --mode connect --target 192.168.1.100
        """
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['loopback', 'listen', 'connect'],
        required=True,
        help='流量生成模式'
    )
    
    parser.add_argument(
        '--target',
        type=str,
        help='目标服务器 IP（仅 connect 模式需要）'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=600,
        help='持续时间（秒）'
    )
    
    args = parser.parse_args()
    
    # 创建生成器
    gen = LocalTrafficGenerator(mode=args.mode, target=args.target)
    
    # 启动
    gen.start()
    
    # 运行指定时长
    try:
        print(f"运行 {args.duration} 秒...\n")
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        gen.stop()


if __name__ == "__main__":
    main()
