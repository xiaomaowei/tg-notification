# -*- coding: utf-8 -*-

"""
任务调度模块

用于定时执行日志监控任务。
"""

import os
import time
import signal
import logging
import threading
import sys
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger("tg_notification")

class TaskScheduler:
    """任务调度器，用于定时执行任务"""
    
    def __init__(self, interval: int = 60):
        """
        初始化任务调度器
        
        Args:
            interval: 任务执行间隔（秒）
        """
        self.interval = interval
        self.running = False
        self.stop_event = threading.Event()
        self.tasks = []
        self.thread = None
        self.last_run_time = None
        self.execution_count = 0
        self.error_count = 0
    
    def add_task(self, task: Callable, name: str = None) -> int:
        """
        添加任务
        
        Args:
            task: 任务函数
            name: 任务名称
            
        Returns:
            任务ID
        """
        task_id = len(self.tasks)
        task_name = name if name else f"Task-{task_id}"
        
        self.tasks.append({
            "id": task_id,
            "name": task_name,
            "func": task,
            "execution_count": 0,
            "error_count": 0,
            "last_execution_time": None,
            "last_execution_duration": None
        })
        
        logger.info(f"添加任务: {task_name} (ID: {task_id})")
        return task_id
    
    def _run_tasks(self):
        """运行所有任务"""
        for task in self.tasks:
            task_name = task["name"]
            task_func = task["func"]
            
            start_time = time.time()
            try:
                logger.debug(f"开始执行任务: {task_name}")
                task_func()
                task["execution_count"] += 1
                self.execution_count += 1
                logger.debug(f"任务执行完成: {task_name}")
            except Exception as e:
                task["error_count"] += 1
                self.error_count += 1
                logger.error(f"任务执行失败: {task_name}, 错误: {e}")
            finally:
                end_time = time.time()
                duration = end_time - start_time
                task["last_execution_time"] = start_time
                task["last_execution_duration"] = duration
                logger.debug(f"任务 {task_name} 执行时间: {duration:.2f}秒")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        logger.info(f"任务调度器已启动，间隔: {self.interval}秒")
        
        while not self.stop_event.is_set():
            loop_start_time = time.time()
            self.last_run_time = loop_start_time
            
            try:
                # 执行所有任务
                self._run_tasks()
            except Exception as e:
                logger.error(f"任务执行循环发生错误: {e}")
            
            # 计算下一次运行的等待时间
            elapsed = time.time() - loop_start_time
            wait_time = max(0.1, self.interval - elapsed)
            
            # 如果任务执行时间超过了间隔，发出警告
            if elapsed > self.interval:
                logger.warning(f"任务执行时间 ({elapsed:.2f}秒) 超过了调度间隔 ({self.interval}秒)")
            
            # 等待下一次执行，但可以被stop_event中断
            logger.debug(f"等待下一次执行，等待时间: {wait_time:.2f}秒")
            self.stop_event.wait(wait_time)
        
        logger.info("任务调度器已停止")
    
    def start(self) -> bool:
        """
        启动任务调度器
        
        Returns:
            是否成功启动
        """
        if self.running:
            logger.warning("任务调度器已经在运行")
            return False
        
        if not self.tasks:
            logger.warning("没有任务，调度器未启动")
            return False
        
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"任务调度器已启动，{len(self.tasks)}个任务将每{self.interval}秒执行一次")
        return True
    
    def stop(self, timeout: int = 5) -> bool:
        """
        停止任务调度器
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            是否成功停止
        """
        if not self.running:
            logger.warning("任务调度器未运行")
            return False
        
        logger.info("正在停止任务调度器...")
        self.running = False
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout)
            if self.thread.is_alive():
                logger.warning(f"任务调度器线程未在{timeout}秒内结束")
                return False
        
        logger.info("任务调度器已停止")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            调度器状态字典
        """
        now = time.time()
        time_since_last_run = now - self.last_run_time if self.last_run_time else None
        
        return {
            "running": self.running,
            "tasks_count": len(self.tasks),
            "interval": self.interval,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "last_run_time": self.last_run_time,
            "time_since_last_run": time_since_last_run,
            "next_run_in": self.interval - time_since_last_run if time_since_last_run else None,
            "tasks": [{
                "id": task["id"],
                "name": task["name"],
                "execution_count": task["execution_count"],
                "error_count": task["error_count"],
                "last_execution_time": task["last_execution_time"],
                "last_execution_duration": task["last_execution_duration"]
            } for task in self.tasks]
        }

class ServiceManager:
    """服务管理器，管理整个应用服务的生命周期"""
    
    def __init__(self):
        """初始化服务管理器"""
        self.scheduler = None
        self.running = False
        self.pid_file = "/tmp/tg_notification.pid"  # 设置默认PID文件路径
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """
        处理信号
        
        Args:
            signum: 信号编号
            frame: 当前栈帧
        """
        sig_name = signal.Signals(signum).name
        logger.info(f"接收到信号: {sig_name} ({signum})")
        self.stop()
    
    def create_pid_file(self, pid_dir: str = "/tmp") -> bool:
        """
        创建PID文件
        
        Args:
            pid_dir: PID文件目录
            
        Returns:
            是否成功创建
        """
        try:
            pid = os.getpid()
            self.pid_file = os.path.join(pid_dir, "tg_notification.pid")
            
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            
            logger.info(f"创建PID文件: {self.pid_file} (PID: {pid})")
            return True
        except Exception as e:
            logger.error(f"创建PID文件失败: {e}")
            return False
    
    def remove_pid_file(self) -> bool:
        """
        删除PID文件
        
        Returns:
            是否成功删除
        """
        if not self.pid_file or not os.path.exists(self.pid_file):
            return False
        
        try:
            os.remove(self.pid_file)
            logger.info(f"已删除PID文件: {self.pid_file}")
            return True
        except Exception as e:
            logger.error(f"删除PID文件失败: {e}")
            return False
    
    def is_process_running(self, pid: int) -> bool:
        """
        检查进程是否在运行
        
        Args:
            pid: 进程ID
            
        Returns:
            进程是否在运行
        """
        try:
            # 在Unix/Linux系统中，向进程发送信号0用于检查进程是否存在
            os.kill(pid, 0)
            return True
        except OSError:
            # 进程不存在
            return False
        except Exception as e:
            logger.error(f"检查进程状态时发生错误: {e}")
            return False
    
    def check_pid_file(self) -> Optional[int]:
        """
        检查PID文件是否存在并读取PID
        
        Returns:
            进程ID，如果文件不存在或无效则返回None
        """
        if not os.path.exists(self.pid_file):
            return None
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                return pid
        except (IOError, ValueError) as e:
            logger.error(f"读取PID文件失败: {e}")
            return None
    
    def start(self, scheduler: TaskScheduler, as_daemon: bool = True) -> bool:
        """
        启动服务
        
        Args:
            scheduler: 任务调度器
            as_daemon: 是否以守护程序模式运行
            
        Returns:
            是否成功启动
        """
        if self.running:
            logger.warning("服务已经在运行")
            return False
        
        self.scheduler = scheduler
        
        if as_daemon:
            # 创建守护进程
            try:
                pid = os.fork()
                if pid > 0:
                    # 父进程退出
                    logger.info(f"已创建守护进程 (PID: {pid})")
                    sys.exit(0)
            except OSError as e:
                logger.error(f"创建守护进程失败: {e}")
                return False
            
            # 子进程继续运行
            # 脱离控制终端
            os.setsid()
            
            # 设置工作目录为根目录
            os.chdir("/")
            
            # 重定向标准输入输出到/dev/null
            sys.stdout.flush()
            sys.stderr.flush()
            with open(os.devnull, 'r') as f:
                os.dup2(f.fileno(), sys.stdin.fileno())
            with open(os.devnull, 'a+') as f:
                os.dup2(f.fileno(), sys.stdout.fileno())
                os.dup2(f.fileno(), sys.stderr.fileno())
            
            # 创建PID文件
            self.create_pid_file()
        
        # 启动调度器
        if self.scheduler.start():
            self.running = True
            logger.info("服务已启动")
            return True
        else:
            logger.error("启动服务失败")
            if as_daemon:
                self.remove_pid_file()
            return False
    
    def stop(self) -> bool:
        """
        停止服务
        
        Returns:
            是否成功停止
        """
        if not self.running:
            logger.warning("服务未运行")
            return False
        
        # 停止调度器
        if self.scheduler:
            self.scheduler.stop()
        
        # 删除PID文件
        self.remove_pid_file()
        
        self.running = False
        logger.info("服务已停止")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            服务状态字典
        """
        # 检查PID文件中的进程是否在运行
        pid = self.check_pid_file()
        is_daemon_running = False
        
        if pid:
            is_daemon_running = self.is_process_running(pid)
            
        status = {
            "running": self.running or is_daemon_running,
            "pid": pid if is_daemon_running else os.getpid(),
            "pid_file": self.pid_file,
            "pid_file_exists": os.path.exists(self.pid_file),
            "daemon_mode": is_daemon_running,
            "start_time": None,
            "uptime": None,
            "scheduler": None
        }
        
        if self.scheduler:
            status["scheduler"] = self.scheduler.get_status()
        
        return status 