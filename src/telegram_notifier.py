# -*- coding: utf-8 -*-

"""
Telegram通知模块

用于格式化消息并发送到Telegram Bot。
"""

import os
import time
import logging
import requests
import html
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("tg_notification")

class MessageFormatter:
    """消息格式化器，用于将日志消息格式化为Telegram消息"""
    
    def __init__(self, format_type: str = "html"):
        """
        初始化消息格式化器
        
        Args:
            format_type: 消息格式类型，支持"html"和"markdown"
        """
        self.format_type = format_type.lower()
        if self.format_type not in ["html", "markdown"]:
            logger.warning(f"不支持的消息格式类型: {format_type}，使用默认类型: html")
            self.format_type = "html"
    
    def format_text(self, text: str) -> str:
        """
        格式化文本，处理特殊字符
        
        Args:
            text: 原始文本
            
        Returns:
            格式化后的文本
        """
        if self.format_type == "html":
            return html.escape(text)
        elif self.format_type == "markdown":
            # 处理Markdown特殊字符
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, f"\\{char}")
            return text
        return text
    
    def format_message(self, match_info: Dict[str, Any]) -> str:
        """
        格式化匹配信息为Telegram消息
        
        Args:
            match_info: 匹配信息字典
            
        Returns:
            格式化后的消息
        """
        log_path = match_info.get("log_path", "未知文件")
        matched_line = match_info.get("matched_line", "")
        context = match_info.get("context", [])
        timestamp = match_info.get("timestamp", time.time())
        
        # 转换时间戳为可读格式
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        if self.format_type == "html":
            message = f"<b>⚠️ 关键词告警</b>\n\n"
            message += f"<b>时间:</b> {time_str}\n"
            message += f"<b>日志文件:</b> <code>{self.format_text(log_path)}</code>\n\n"
            message += f"<b>匹配内容:</b>\n<pre>{self.format_text(matched_line)}</pre>\n\n"
            
            if context:
                message += f"<b>上下文:</b>\n<pre>"
                for line in context:
                    message += f"{self.format_text(line)}\n"
                message += "</pre>"
        elif self.format_type == "markdown":
            message = f"*⚠️ 关键词告警*\n\n"
            message += f"*时间:* {time_str}\n"
            message += f"*日志文件:* `{self.format_text(log_path)}`\n\n"
            message += f"*匹配内容:*\n```\n{self.format_text(matched_line)}\n```\n\n"
            
            if context:
                message += f"*上下文:*\n```\n"
                for line in context:
                    message += f"{self.format_text(line)}\n"
                message += "```"
        else:
            # 纯文本格式
            message = f"⚠️ 关键词告警\n\n"
            message += f"时间: {time_str}\n"
            message += f"日志文件: {log_path}\n\n"
            message += f"匹配内容:\n{matched_line}\n\n"
            
            if context:
                message += f"上下文:\n"
                for line in context:
                    message += f"{line}\n"
        
        return message

class TelegramNotifier:
    """Telegram通知器，用于发送消息到Telegram Bot"""
    
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "HTML"):
        """
        初始化Telegram通知器
        
        Args:
            bot_token: Telegram Bot的token
            chat_id: 接收消息的chat_id
            parse_mode: 消息解析模式，支持"HTML"和"Markdown"
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.message_formatter = MessageFormatter(parse_mode.lower())
        
        # 请求超时设置（秒）
        self.timeout = 10
        
        # 重试设置
        self.max_retries = 3
        self.retry_delay = 2  # 秒
    
    def send_message(self, text: str) -> bool:
        """
        发送消息到Telegram
        
        Args:
            text: 消息文本
            
        Returns:
            是否发送成功
        """
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": self.parse_mode
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    logger.info("消息发送成功")
                    return True
                else:
                    error = result.get("description", "未知错误")
                    logger.error(f"发送消息失败: {error}")
                    
                    # 如果是解析模式错误，尝试以纯文本模式重发
                    if "parse_mode" in error.lower():
                        logger.warning("尝试以纯文本模式重发消息")
                        payload.pop("parse_mode", None)
                        
                        text_response = requests.post(
                            self.api_url,
                            json=payload,
                            timeout=self.timeout
                        )
                        
                        if text_response.json().get("ok"):
                            logger.info("以纯文本模式重发消息成功")
                            return True
                    
                    return False
                    
            except requests.RequestException as e:
                logger.error(f"请求错误 (尝试 {attempt+1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error("达到最大重试次数，放弃发送")
                    return False
        
        return False
    
    def send_notification(self, match_info: Dict[str, Any]) -> bool:
        """
        发送通知
        
        Args:
            match_info: 匹配信息字典
            
        Returns:
            是否发送成功
        """
        message = self.message_formatter.format_message(match_info)
        return self.send_message(message)

class NotificationManager:
    """通知管理器，用于协调消息格式化和发送"""
    
    def __init__(self, telegram_config: Dict[str, Any]):
        """
        初始化通知管理器
        
        Args:
            telegram_config: Telegram配置字典
        """
        self.bot_token = telegram_config.get("bot_token", "")
        self.chat_id = telegram_config.get("chat_id", "")
        self.parse_mode = telegram_config.get("parse_mode", "HTML")
        
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram配置不完整，无法初始化通知管理器")
            raise ValueError("Telegram配置不完整")
        
        self.notifier = TelegramNotifier(self.bot_token, self.chat_id, self.parse_mode)
        
        # 消息队列和去重集合
        self.message_queue = []
        self.sent_message_hashes = set()
        
        # 配置项
        self.batch_size = telegram_config.get("batch_size", 1)
        self.deduplicate = telegram_config.get("deduplicate", True)
        self.max_queue_size = 100
    
    def add_notification(self, match_info: Dict[str, Any]) -> bool:
        """
        添加通知到队列
        
        Args:
            match_info: 匹配信息字典
            
        Returns:
            是否成功添加
        """
        # 生成消息哈希用于去重
        msg_hash = hash(f"{match_info.get('log_path')}:{match_info.get('matched_line')}")
        
        # 去重检查
        if self.deduplicate and msg_hash in self.sent_message_hashes:
            logger.debug("忽略重复消息")
            return False
        
        # 添加到队列
        self.message_queue.append(match_info)
        
        # 如果队列足够大，立即发送
        if len(self.message_queue) >= self.batch_size:
            self.process_queue()
        
        # 如果队列超过最大大小，移除旧消息
        if len(self.message_queue) > self.max_queue_size:
            self.message_queue = self.message_queue[-self.max_queue_size:]
        
        return True
    
    def process_queue(self) -> int:
        """
        处理消息队列
        
        Returns:
            成功发送的消息数量
        """
        success_count = 0
        
        while self.message_queue:
            match_info = self.message_queue.pop(0)
            
            if self.notifier.send_notification(match_info):
                success_count += 1
                
                # 添加到已发送集合
                if self.deduplicate:
                    msg_hash = hash(f"{match_info.get('log_path')}:{match_info.get('matched_line')}")
                    self.sent_message_hashes.add(msg_hash)
                
                # 限制已发送集合大小
                if len(self.sent_message_hashes) > 10000:
                    self.sent_message_hashes = set(list(self.sent_message_hashes)[-5000:])
        
        return success_count
    
    def test_notification(self, message: str = "测试消息") -> bool:
        """
        发送测试通知
        
        Args:
            message: 测试消息内容
            
        Returns:
            是否发送成功
        """
        match_info = {
            "log_path": "测试",
            "matched_line": message,
            "context": ["测试上下文行1", f">> {message}", "测试上下文行2"],
            "timestamp": time.time()
        }
        
        return self.notifier.send_notification(match_info) 