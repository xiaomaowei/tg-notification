# -*- coding: utf-8 -*-

"""
主应用模块

用于协调配置、日志监控和通知组件。
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional

from .config import ConfigManager
from .log_monitor import LogMonitor
from .telegram_notifier import NotificationManager
from .task_scheduler import TaskScheduler, ServiceManager

logger = logging.getLogger("tg_notification")

class Application:
    """应用主类，协调各组件工作"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化应用
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_manager = ConfigManager(config_dir)
        self.log_monitor = None
        self.notification_manager = None
        self.scheduler = None
        self.service_manager = ServiceManager()
    
    def initialize(self) -> bool:
        """
        初始化应用组件
        
        Returns:
            是否成功初始化
        """
        try:
            # 验证配置
            logger.info("正在验证配置...")
            if not self._validate_configs():
                logger.error("配置验证失败，无法继续初始化")
                return False
            
            # 初始化日志监控器
            logger.info("正在初始化日志监控器...")
            keyword_config = self.config_manager.get_keyword_config()
            log_configs = keyword_config.get("log_files", [])
            self.log_monitor = LogMonitor(log_configs)
            
            # 初始化通知管理器
            logger.info("正在初始化通知管理器...")
            telegram_config = self.config_manager.get_telegram_config()
            self.notification_manager = NotificationManager(telegram_config)
            
            logger.info("应用初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"应用初始化失败: {e}")
            return False
    
    def _validate_configs(self) -> bool:
        """
        验证配置
        
        Returns:
            配置是否有效
        """
        try:
            # 验证关键词配置
            if not self.config_manager.validate_keyword_config():
                logger.error("关键词配置验证失败")
                return False
            
            # 验证Telegram配置
            if not self.config_manager.validate_telegram_config():
                logger.error("Telegram配置验证失败")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False
    
    def _monitoring_task(self):
        """日志监控任务"""
        try:
            # 获取关键词配置（用于检查新文件）
            keyword_config = self.config_manager.get_keyword_config(True)  # 强制重新加载配置
            log_configs = keyword_config.get("log_files", [])
            
            # 检查日志，传入配置以便检查新文件
            matches = self.log_monitor.check_logs(log_configs)
            
            if matches:
                logger.info(f"发现 {len(matches)} 个匹配项")
                
                # 发送通知
                for match in matches:
                    self.notification_manager.add_notification(match)
                
                # 处理队列中的通知
                sent_count = self.notification_manager.process_queue()
                logger.info(f"已发送 {sent_count} 条通知")
        
        except Exception as e:
            logger.error(f"监控任务执行失败: {e}")
    
    def start_service(self, interval: int = 60, as_daemon: bool = True) -> bool:
        """
        启动服务
        
        Args:
            interval: 监控间隔（秒）
            as_daemon: 是否以守护程序模式运行
            
        Returns:
            是否成功启动
        """
        # 初始化应用
        if not self.initialize():
            logger.error("应用初始化失败，无法启动服务")
            return False
        
        # 创建调度器
        self.scheduler = TaskScheduler(interval)
        
        # 添加监控任务
        self.scheduler.add_task(self._monitoring_task, "日志监控")
        
        # 启动服务
        return self.service_manager.start(self.scheduler, as_daemon)
    
    def stop_service(self) -> bool:
        """
        停止服务
        
        Returns:
            是否成功停止
        """
        return self.service_manager.stop()
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            服务状态字典
        """
        return self.service_manager.get_status()
    
    def test_notification(self, message: str = "测试消息") -> bool:
        """
        发送测试通知
        
        Args:
            message: 测试消息内容
            
        Returns:
            是否发送成功
        """
        try:
            # 初始化必要组件
            telegram_config = self.config_manager.get_telegram_config()
            notification_manager = NotificationManager(telegram_config)
            
            # 发送测试通知
            return notification_manager.test_notification(message)
            
        except Exception as e:
            logger.error(f"发送测试通知失败: {e}")
            return False 