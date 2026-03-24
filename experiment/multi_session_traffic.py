#!/usr/bin/env python3
"""
多会话并发流量生成器

支持：
- 多个并发 SSH 会话
- 多个并发 HTTP/HTTPS 会话
- 混合流量模式
- 可配置的流量强度和模式

使用方法:
    python3 multi_session_traffic.py --ssh-sessions 5 --http-sessions 10 --duration 600
"""

import argparse
import subprocess
import threading
import time
import random
import os
import signal
import sys
from datetime import datetime
from typing import List, Optional


class TrafficGenerator:
    """基础流量生成器"""
    
    def __init__(self, name: str):
        self.name = name
        self.running = False
        self.processes: List[subprocess.Popen] = []
        self.stats = {
            'start_time': None,
            'packets_sent': 0,
            'bytes_transferred': 0
        }
    
    def start(self):
        """启动流量生成"""
        self.running = True
        self.stats['start_time'] = datetime.now()
    
    def stop(self):
        """停止所有流量生成进程"""
        self.running = False
        for proc in self.processes:
            try:
                proc.terminate()
            except:
                pass
        self.processes.clear()
    
    def get_stats(self):
        """获取统计信息"""
        return self.stats.copy()


class SSHTrafficGenerator(TrafficGenerator):
    """SSH 流量生成器 - 支持多会话"""
    
    def __init__(self, sessions: int = 3, servers: Optional[List[str]] = None):
        super().__init__("SSH")
        self.sessions = sessions
        self.servers = servers or [
            'github.com',
            'gitlab.com',
            'bitbucket.org'
        ]
        
    def start(self):
        """启动多个 SSH 会话"""
        super().start()
        print(f"[SSH] 启动 {self.sessions} 个并发 SSH 会话...")
        
        # 创建指定数量的 SSH 会话
        for i in range(self.sessions):
            server = random.choice(self.servers)
            self._create_ssh_session(i, server)
        
        print(f"[SSH] ✓ 已启动 {len(self.processes)} 个 SSH 会话")
    
    def _create_ssh_session(self, session_id: int, server: str):
        """创建单个 SSH 会话"""
        
        # 不同的流量模式
        modes = [
            # 模式 1: 持续数据传输
            f'ssh -o StrictHostKeyChecking=no {server} "cat /dev/zero > /dev/null"',
            
            # 模式 2: 间歇性小数据包
            f'ssh -o StrictHostKeyChecking=no {server} "while true; do echo ping; sleep 0.1; done"',
            
            # 模式 3: 批量数据传输
            f'ssh -o StrictHostKeyChecking=no {server} "dd if=/dev/zero of=/dev/null bs=1M count=100"',
            
            # 模式 4: 交互式命令
            f'ssh -o StrictHostKeyChecking=no {server} "ls -la / && pwd && whoami"',
        ]
        
        # 随机选择一个模式
        cmd = random.choice(modes)
        
        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.processes.append(proc)
            print(f"  [SSH-{session_id}] 连接到 {server}")
        except Exception as e:
            print(f"  [SSH-{session_id}] ✗ 失败：{e}")
    
    def maintain_sessions(self):
        """维护会话，自动重启断开的连接"""
        while self.running:
            # 检查并重启终止的进程
            for i, proc in enumerate(self.processes):
                if proc.poll() is not None:
                    print(f"[SSH] 会话 {i} 已终止，重新启动...")
                    server = random.choice(self.servers)
                    self._create_ssh_session(i, server)
            
            time.sleep(5)  # 每 5 秒检查一次
    
    def stop(self):
        """停止所有 SSH 会话"""
        print(f"[SSH] 停止 {len(self.processes)} 个会话...")
        super().stop()


class HTTPTrafficGenerator(TrafficGenerator):
    """HTTP/HTTPS 流量生成器 - 支持多会话"""
    
    def __init__(self, sessions: int = 5):
        super().__init__("HTTP")
        self.sessions = sessions
        
        # URL 池
        self.urls = {
            'large_files': [
                'https://httpbin.org/stream-bytes/10M',
                'https://httpbin.org/stream-bytes/5M',
                'https://test-debian.s3.amazonaws.com/pool/main/l/linux-signed-amd64/linux-image-6.1.0-0.deb',
            ],
            'websites': [
                'https://www.example.com',
                'https://www.wikipedia.org',
                'https://www.github.com',
                'https://www.stackoverflow.com',
            ],
            'api_endpoints': [
                'https://api.github.com/users/octocat',
                'https://jsonplaceholder.typicode.com/posts/1',
                'https://httpbin.org/get',
            ],
            'streaming': [
                'https://httpbin.org/stream/100',
                'https://httpbin.org/delay/5',
            ]
        }
    
    def start(self):
        """启动多个 HTTP 会话"""
        super().start()
        print(f"[HTTP] 启动 {self.sessions} 个并发 HTTP 会话...")
        
        # 分配不同类型的会话
        for i in range(self.sessions):
            session_type = random.choice(['large_download', 'web_browse', 'api_call', 'streaming'])
            self._create_http_session(i, session_type)
        
        print(f"[HTTP] ✓ 已启动 {len(self.processes)} 个 HTTP 会话")
    
    def _create_http_session(self, session_id: int, session_type: str):
        """创建单个 HTTP 会话"""
        
        if session_type == 'large_download':
            url = random.choice(self.urls['large_files'])
            cmd = f'curl -o /dev/null -s {url}'
            
        elif session_type == 'web_browse':
            url = random.choice(self.urls['websites'])
            cmd = f'curl -o /dev/null -s -L {url}'
            
        elif session_type == 'api_call':
            url = random.choice(self.urls['api_endpoints'])
            cmd = f'curl -s {url}'
            
        elif session_type == 'streaming':
            url = random.choice(self.urls['streaming'])
            cmd = f'curl -o /dev/null -s {url}'
        else:
            url = random.choice(self.urls['websites'])
            cmd = f'curl -o /dev/null -s {url}'
        
        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.processes.append(proc)
            print(f"  [HTTP-{session_id}] {session_type}: {url[:50]}...")
        except Exception as e:
            print(f"  [HTTP-{session_id}] ✗ 失败：{e}")
    
    def maintain_sessions(self):
        """持续产生 HTTP 流量"""
        while self.running:
            # 随机启动新的请求
            if len(self.processes) < self.sessions * 2:  # 保持一定的并发量
                session_id = len(self.processes)
                session_type = random.choice(['large_download', 'web_browse', 'api_call'])
                self._create_http_session(session_id, session_type)
            
            # 清理已完成的进程
            self.processes = [p for p in self.processes if p.poll() is None]
            
            time.sleep(random.uniform(1, 3))  # 随机间隔
    
    def stop(self):
        """停止所有 HTTP 会话"""
        print(f"[HTTP] 停止 {len(self.processes)} 个会话...")
        super().stop()


class MixedTrafficScheduler:
    """混合流量调度器 - 协调多种类型的流量"""
    
    def __init__(self, ssh_sessions: int = 3, http_sessions: int = 5, duration: int = 600):
        self.duration = duration
        self.start_time = None
        
        # 创建流量生成器
        self.ssh_gen = SSHTrafficGenerator(sessions=ssh_sessions)
        self.http_gen = HTTPTrafficGenerator(sessions=http_sessions)
        
        self.threads = []
        self.running = False
        
        print("=" * 70)
        print("混合流量调度器初始化完成")
        print(f"  SSH 会话数：{ssh_sessions}")
        print(f"  HTTP 会话数：{http_sessions}")
        print(f"  持续时间：{duration} 秒")
        print("=" * 70)
    
    def start(self):
        """启动所有流量生成器"""
        self.running = True
        self.start_time = datetime.now()
        
        print(f"\n[{self.start_time.strftime('%H:%M:%S')}] 开始生成混合流量...\n")
        
        # 启动 SSH 流量
        self.ssh_gen.start()
        ssh_thread = threading.Thread(target=self.ssh_gen.maintain_sessions)
        ssh_thread.daemon = True
        self.threads.append(ssh_thread)
        ssh_thread.start()
        
        # 等待 2 秒再启动 HTTP
        time.sleep(2)
        
        # 启动 HTTP 流量
        self.http_gen.start()
        http_thread = threading.Thread(target=self.http_gen.maintain_sessions)
        http_thread.daemon = True
        self.threads.append(http_thread)
        http_thread.start()
        
        print(f"\n✓ 所有流量生成器已启动\n")
    
    def run(self):
        """运行指定时长"""
        try:
            elapsed = 0
            while self.running and elapsed < self.duration:
                time.sleep(10)
                elapsed = (datetime.now() - self.start_time).total_seconds()
                
                # 每 30 秒打印状态
                if int(elapsed) % 30 < 10:
                    self._print_status(elapsed)
        
        except KeyboardInterrupt:
            print("\n\n用户中断...")
            self.stop()
    
    def _print_status(self, elapsed: float):
        """打印当前状态"""
        ssh_count = len([p for p in self.ssh_gen.processes if p.poll() is None])
        http_count = len([p for p in self.http_gen.processes if p.poll() is None])
        
        remaining = self.duration - elapsed
        print(f"[{(elapsed/60):.1f}min] 活跃会话：SSH={ssh_count}, HTTP={http_count} | 剩余：{remaining:.0f}s")
    
    def stop(self):
        """停止所有流量生成器"""
        print("\n停止所有流量生成器...")
        self.running = False
        
        self.ssh_gen.stop()
        self.http_gen.stop()
        
        # 等待线程结束
        for thread in self.threads:
            thread.join(timeout=2)
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print("流量生成完成")
        print(f"  总持续时间：{duration:.1f} 秒")
        print(f"  SSH 会话峰值：{len(self.ssh_gen.processes)}")
        print(f"  HTTP 会话峰值：{len(self.http_gen.processes)}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='多会话并发流量生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认配置（3 个 SSH + 5 个 HTTP，持续 10 分钟）
  python3 multi_session_traffic.py
  
  # 自定义配置（10 个 SSH + 20 个 HTTP，持续 15 分钟）
  python3 multi_session_traffic.py --ssh-sessions 10 --http-sessions 20 --duration 900
  
  # 仅 HTTP 流量
  python3 multi_session_traffic.py --ssh-sessions 0 --http-sessions 15
        """
    )
    
    parser.add_argument(
        '--ssh-sessions',
        type=int,
        default=3,
        help='SSH 会话数量 (默认：3)'
    )
    
    parser.add_argument(
        '--http-sessions',
        type=int,
        default=5,
        help='HTTP/HTTPS 会话数量 (默认：5)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=600,
        help='持续时间（秒）(默认：600)'
    )
    
    args = parser.parse_args()
    
    # 创建调度器
    scheduler = MixedTrafficScheduler(
        ssh_sessions=args.ssh_sessions,
        http_sessions=args.http_sessions,
        duration=args.duration
    )
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n收到中断信号...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动
    scheduler.start()
    scheduler.run()


if __name__ == "__main__":
    main()
