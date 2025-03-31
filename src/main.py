#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram通知程序

这个程序用于监控指定日志文件中的关键词，并通过Telegram Bot发送通知。
"""

import os
import sys
import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
import time
import threading
import signal
from datetime import datetime

from .application import Application

class StandardizedLogFormatter(logging.Formatter):
    """标准化日志格式化器，在格式化时添加文件名相关信息"""
    
    def __init__(self, fmt=None, datefmt=None, style='%', module_name="unspecified"):
        super().__init__(fmt, datefmt, style)
        self.module_name = module_name
    
    def format(self, record):
        """重写format方法，为日志记录添加额外的信息"""
        # 创建新的记录副本，避免修改原始记录
        record_copy = logging.makeLogRecord(record.__dict__)
        # 添加模块名称
        record_copy.module_name = self.module_name
        return super().format(record_copy)

class StandardizedFileHandler(TimedRotatingFileHandler):
    """标准化文件处理器，动态生成符合标准的日志文件名"""
    
    def __init__(self, log_dir, module_name, level_name, when='midnight', interval=1, backupCount=10):
        """
        初始化处理器
        
        Args:
            log_dir: 日志目录
            module_name: 模块/功能名称
            level_name: 日志级别名称
            when: 日志滚动时间单位
            interval: 滚动间隔
            backupCount: 保留文件数量
        """
        self.log_dir = log_dir
        self.module_name = module_name
        self.level_name = level_name
        self.when = when
        self.interval = interval
        self.backupCount = backupCount
        self.file_created = False
        
        # 创建日志文件名前缀
        self.filename_prefix = f"{module_name}_{level_name}"
        self.current_filename = None
        
        # 先使用临时文件路径初始化父类
        # 使用/dev/null（Unix/Linux）或NUL（Windows）作为临时文件，避免在磁盘创建不必要的文件
        temp_file = os.devnull
        
        # 初始化父类，但禁用自动轮转 - 我们将使用自己的方式管理文件
        super().__init__(
            temp_file, 
            when=when, 
            interval=interval, 
            backupCount=backupCount
        )
        # 禁用自动轮转
        self.rolloverAt = float('inf')  # 设置一个非常大的值，实际上禁用了自动轮转
        
        # 设置格式化器
        formatter = StandardizedLogFormatter(
            '%(asctime)s - %(levelname)s - %(module_name)s - %(message)s',
            module_name=module_name
        )
        self.setFormatter(formatter)
    
    def _create_real_file(self):
        """当需要写入日志时，创建实际的日志文件"""
        if not self.file_created:
            # 使用当前时间创建文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_filename = f"{self.module_name}_{timestamp}_{self.level_name}.log"
            self.baseFilename = os.path.join(self.log_dir, self.current_filename)
            
            # 确保日志目录存在
            os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)
            
            if self.stream:
                self.stream.close()
                self.stream = None
            
            # 打开实际的日志文件
            self.stream = self._open()
            self.file_created = True
    
    def emit(self, record):
        """重写emit方法，确保在写入日志前创建实际的日志文件"""
        # 创建实际的日志文件（如果尚未创建）
        self._create_real_file()
        
        # 调用父类的emit方法写入日志
        super().emit(record)
    
    def doRollover(self):
        """重写轮转方法，使用自定义的命名方式"""
        # 我们完全禁用了自动轮转，所以这个方法不会被调用
        # 但为了安全起见，如果被调用，就创建一个新的文件
        if self.file_created:
            if self.stream:
                self.stream.close()
                self.stream = None
            
            # 创建新的日志文件
            self.file_created = False
            self._create_real_file()

# 设置日志
def setup_logger(log_level=logging.INFO, module_name="tg_notification"):
    """
    设置日志记录器，使用标准化的文件命名
    
    Args:
        log_level: 日志级别
        module_name: 模块/功能名称
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)
    
    # 清除可能存在的旧处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 为不同级别创建不同的处理器
    level_handlers = {
        logging.INFO: StandardizedFileHandler(log_dir, module_name, "INFO"),
        logging.WARNING: StandardizedFileHandler(log_dir, module_name, "WARNING"),
        logging.ERROR: StandardizedFileHandler(log_dir, module_name, "ERROR"),
        logging.DEBUG: StandardizedFileHandler(log_dir, module_name, "DEBUG"),
    }
    
    # 配置各级别的处理器
    for level, handler in level_handlers.items():
        handler.setLevel(level)
        
        # 设置过滤器，只处理特定级别的日志
        def filter_level(record, target_level=level):
            return record.levelno == target_level
            
        handler.addFilter(filter_level)
        logger.addHandler(handler)
    
    # 控制台处理器（显示所有级别日志）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加控制台处理器
    logger.addHandler(console_handler)
    
    return logger

def parse_arguments():
    """解析命令行参数"""
    # 创建主解析器
    parser = argparse.ArgumentParser(description="Telegram通知程序")
    
    # 全局选项
    parser.add_argument("--config", type=str, default="config", help="配置文件目录路径")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 启动监控服务命令
    start_parser = subparsers.add_parser("start", help="启动监控服务")
    start_parser.add_argument("--no-daemon", action="store_true", help="前台运行，不作为守护进程")
    start_parser.add_argument("--interval", type=int, default=60, help="日志检查间隔（秒）")
    
    # 停止监控服务命令
    stop_parser = subparsers.add_parser("stop", help="停止监控服务")
    
    # 发送测试消息命令
    test_parser = subparsers.add_parser("test", help="发送测试消息")
    test_parser.add_argument("--message", type=str, default="测试消息", help="测试消息内容")
    
    # 查看状态命令
    status_parser = subparsers.add_parser("status", help="查看服务状态")
    
    args = parser.parse_args()
    
    # 如果没有指定命令，显示帮助信息
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    return args

def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志级别
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger(log_level)
    
    logger.info("Telegram通知程序启动中...")
    logger.debug(f"命令行参数: {args}")
    
    # 创建应用实例
    app = Application(args.config)
    
    # 根据命令执行相应的操作
    if args.command == "start":
        logger.info(f"启动监控服务，间隔: {args.interval}秒，守护进程模式: {not args.no_daemon}")
        
        try:
            if app.start_service(args.interval, not args.no_daemon):
                if not args.no_daemon:
                    print(f"监控服务已在后台启动，日志目录: logs/")
                    print(f"使用命令查看服务状态: python tg_notification.py status")
                    print(f"使用命令停止服务: python tg_notification.py stop")
                else:
                    print(f"监控服务已在前台启动，日志目录: logs/")
                    # 如果是前台模式，则保持主进程运行
                    try:
                        # 使用事件来等待，而不是无限循环
                        # 这样可以在接收到信号时立即退出
                        stop_event = threading.Event()
                        
                        # 注册信号处理函数
                        def signal_handler(signum, frame):
                            logger.info(f"接收到信号: {signal.Signals(signum).name} ({signum})")
                            print("接收到中断信号，正在停止服务...")
                            app.stop_service()
                            print("服务已停止")
                            stop_event.set()  # 设置事件，使得wait返回
                        
                        # 注册SIGINT信号处理函数
                        original_sigint_handler = signal.getsignal(signal.SIGINT)
                        signal.signal(signal.SIGINT, signal_handler)
                        
                        # 等待事件被设置
                        try:
                            while not stop_event.is_set():
                                stop_event.wait(1)  # 每秒检查一次
                        finally:
                            # 恢复原始信号处理函数
                            signal.signal(signal.SIGINT, original_sigint_handler)
                            
                    except Exception as e:
                        logger.error(f"前台运行模式发生错误: {e}")
                        app.stop_service()
                        print("服务已停止")
            else:
                print("启动服务失败，请检查日志了解详情")
                return 1
        except Exception as e:
            logger.error(f"启动服务时发生未处理的异常: {e}")
            print(f"启动服务失败: {e}")
            return 1
    
    elif args.command == "stop":
        logger.info("停止监控服务")
        if app.stop_service():
            print("监控服务已停止")
        else:
            print("停止服务失败，服务可能未在运行")
    
    elif args.command == "test":
        logger.info(f"发送测试消息: {args.message}")
        if app.test_notification(args.message):
            print(f"测试消息发送成功: {args.message}")
        else:
            print("测试消息发送失败，请检查日志了解详情")
            return 1
    
    elif args.command == "status":
        logger.info("查询服务状态")
        status = app.get_service_status()
        
        if status["running"]:
            print("服务状态: 运行中")
            print(f"进程ID: {status['pid']}")
            if status.get("daemon_mode", False):
                print("运行模式: 守护进程")
            else:
                print("运行模式: 前台")
                
            print(f"PID文件: {status['pid_file']}")
            
            scheduler = status.get("scheduler", {})
            if scheduler:
                print(f"任务数量: {scheduler.get('tasks_count', 0)}")
                print(f"执行次数: {scheduler.get('execution_count', 0)}")
                print(f"错误次数: {scheduler.get('error_count', 0)}")
                
                if scheduler.get("last_run_time"):
                    last_run = datetime.fromtimestamp(scheduler["last_run_time"])
                    print(f"上次执行: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                if scheduler.get("next_run_in"):
                    print(f"下次执行: {int(scheduler['next_run_in'])}秒后")
        else:
            print("服务状态: 未运行")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 