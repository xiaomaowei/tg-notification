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
import resource  # 添加resource模块导入
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
        
        # 启动调度器 - 在daemon模式前先启动调度器验证配置
        if not self.scheduler.start():
            logger.error("启动任务调度器失败")
            return False
        
        # 如果是守护进程模式，创建守护进程
        if as_daemon:
            # 先停止已启动的调度器，在子进程中再次启动
            self.scheduler.stop()
            
            # 保存当前工作目录
            original_dir = os.getcwd()
            logger.debug(f"当前工作目录: {original_dir}")
            
            # 创建守护进程
            try:
                # 第一次fork
                pid = os.fork()
                if pid > 0:
                    # 父进程退出
                    logger.info(f"已创建守护进程 (PID: {pid})")
                    # 等待子进程初始化
                    time.sleep(1)
                    sys.exit(0)
            except OSError as e:
                logger.error(f"创建守护进程失败: {e}")
                return False
            
            # 子进程继续运行
            try:
                # 创建新会话
                os.setsid()
                
                # 第二次fork，防止终端重新获取控制
                pid = os.fork()
                if pid > 0:
                    # 第一个子进程退出
                    sys.exit(0)
            except OSError as e:
                logger.error(f"守护进程二次fork失败: {e}")
                sys.exit(1)
            
            # 第二个子进程继续运行（真正的守护进程）
            
            try:
                # 设置工作目录，使用原来的工作目录，不切换到根目录
                os.chdir(original_dir)
                logger.debug(f"守护进程工作目录: {os.getcwd()}")
                
                # 重设文件创建掩码
                os.umask(0)
                
                # 关闭所有打开的文件描述符
                maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
                if maxfd == resource.RLIM_INFINITY:
                    maxfd = 1024
                
                # 关闭所有继承的文件描述符
                for fd in range(3, maxfd):
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                
                # 重定向标准输入/输出/错误到/dev/null
                sys.stdout.flush()
                sys.stderr.flush()
                with open(os.devnull, 'r') as f:
                    os.dup2(f.fileno(), sys.stdin.fileno())
                with open(os.devnull, 'a+') as f:
                    os.dup2(f.fileno(), sys.stdout.fileno())
                    os.dup2(f.fileno(), sys.stderr.fileno())
                
                # 创建PID文件
                self.create_pid_file()
                
                # 配置日志记录器，确保日志也写入文件
                log_file = os.path.join(original_dir, "logs", "tg_notification.log")
                try:
                    from logging.handlers import RotatingFileHandler
                    file_handler = RotatingFileHandler(
                        log_file,
                        maxBytes=10 * 1024 * 1024,  # 10MB
                        backupCount=5
                    )
                    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                    file_handler.setFormatter(formatter)
                    logger.addHandler(file_handler)
                    logger.debug("守护进程添加了文件日志处理器")
                except Exception as e:
                    # 如果无法配置日志，至少将错误写入系统日志
                    import syslog
                    syslog.syslog(syslog.LOG_ERR, f"守护进程日志配置失败: {e}")
                
                # 在子进程中重新启动调度器
                logger.info("守护进程正在启动任务调度器...")
                if not self.scheduler.start():
                    logger.error("在守护进程中启动任务调度器失败")
                    self.remove_pid_file()
                    sys.exit(1)
                
                logger.info("守护进程已成功启动服务")
                self.running = True
                
                # 注意：这里不应返回，而是在子进程中持续运行
                # 子进程需要持续存在，防止退出
                while True:
                    # 每隔一段时间记录一条心跳日志，确保程序正在运行
                    time.sleep(3600)  # 每小时记录一次
                    logger.debug("守护进程心跳")
                
            except Exception as e:
                # 捕获并记录子进程中的任何异常
                logger.critical(f"守护进程初始化时发生严重错误: {e}", exc_info=True)
                try:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.critical(f"详细错误信息: {error_details}")
                    
                    # 也尝试写入系统日志
                    import syslog
                    syslog.syslog(syslog.LOG_CRIT, f"守护进程崩溃: {e}")
                except:
                    pass
                
                try:
                    self.remove_pid_file()
                except:
                    pass
                sys.exit(1)
        
        # 非守护进程模式
        self.running = True
        logger.info("服务已启动（前台模式）")
        return True
    
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