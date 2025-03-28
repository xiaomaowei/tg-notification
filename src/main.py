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
from logging.handlers import RotatingFileHandler
import time

from .application import Application

# 设置日志
def setup_logger(log_level=logging.INFO):
    """设置日志记录器"""
    logger = logging.getLogger("tg_notification")
    logger.setLevel(log_level)
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 文件处理器，支持日志轮转
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "tg_notification.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
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
        
        if app.start_service(args.interval, not args.no_daemon):
            print(f"监控服务已启动，日志文件位置: logs/tg_notification.log")
            
            # 如果是前台模式，则保持主进程运行
            if args.no_daemon:
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("接收到中断信号，正在停止服务...")
                    app.stop_service()
                    print("服务已停止")
        else:
            print("启动服务失败，请检查日志了解详情")
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
            scheduler = status.get("scheduler", {})
            print(f"任务数量: {scheduler.get('tasks_count', 0)}")
            print(f"执行次数: {scheduler.get('execution_count', 0)}")
            print(f"错误次数: {scheduler.get('error_count', 0)}")
        else:
            print("服务状态: 未运行")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 