# -*- coding: utf-8 -*-

"""
配置管理模块

用于加载和管理YAML配置文件，提供配置访问接口。
"""

import os
import logging
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger("tg_notification")

class ConfigLoader:
    """配置加载器，用于读取YAML配置文件"""
    
    def __init__(self, config_dir: str):
        """
        初始化配置加载器
        
        Args:
            config_dir: 配置文件目录路径
        """
        # 确保config_dir是绝对路径，以防守护进程模式下工作目录变更
        if not os.path.isabs(config_dir):
            # 获取程序主目录（src的上一级目录）
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_dir = os.path.abspath(os.path.join(base_dir, config_dir))
        else:
            self.config_dir = config_dir
            
        logger.debug(f"配置目录路径: {self.config_dir}")
        self._config_cache = {}
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        加载指定的配置文件
        
        Args:
            config_name: 配置文件名（不包含扩展名）
            
        Returns:
            配置字典
        
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
        """
        config_path = os.path.join(self.config_dir, f"{config_name}.yml")
        
        logger.debug(f"尝试加载配置文件: {config_path}")
        
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            raise FileNotFoundError(f"找不到配置文件: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                if config is None:
                    logger.error(f"配置文件为空或格式错误: {config_path}")
                    raise ValueError(f"配置文件为空或格式错误: {config_path}")
                    
                self._config_cache[config_name] = config
                logger.debug(f"已加载配置文件: {config_path}")
                return config
        except yaml.YAMLError as e:
            logger.error(f"配置文件解析错误: {config_path}, 错误: {e}")
            raise ValueError(f"配置文件解析错误: {config_path}, 错误: {e}")
        except Exception as e:
            logger.error(f"读取配置文件时发生错误: {config_path}, 错误: {e}")
            raise
    
    def get_config(self, config_name: str, reload: bool = False) -> Dict[str, Any]:
        """
        获取配置，如果配置已加载则直接返回，否则加载配置
        
        Args:
            config_name: 配置文件名（不包含扩展名）
            reload: 是否强制重新加载
            
        Returns:
            配置字典
        """
        if reload or config_name not in self._config_cache:
            return self.load_config(config_name)
        
        return self._config_cache[config_name]

class ConfigManager:
    """配置管理器，单例模式"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """确保只有一个实例"""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        # 避免重复初始化
        if self._initialized:
            return
            
        self.config_loader = ConfigLoader(config_dir)
        self._keyword_config = None
        self._telegram_config = None
        self._initialized = True
    
    def get_keyword_config(self, reload: bool = False) -> Dict[str, Any]:
        """
        获取关键词配置
        
        Args:
            reload: 是否强制重新加载
            
        Returns:
            关键词配置字典
        """
        if reload or self._keyword_config is None:
            self._keyword_config = self.config_loader.get_config("keyword_config", reload)
        
        return self._keyword_config
    
    def get_telegram_config(self, reload: bool = False) -> Dict[str, Any]:
        """
        获取Telegram配置
        
        Args:
            reload: 是否强制重新加载
            
        Returns:
            Telegram配置字典
        """
        if reload or self._telegram_config is None:
            self._telegram_config = self.config_loader.get_config("telegram_config", reload)
        
        return self._telegram_config
    
    def validate_keyword_config(self) -> bool:
        """
        验证关键词配置是否有效
        
        Returns:
            配置是否有效
        """
        try:
            config = self.get_keyword_config()
            
            # 检查必要的配置项
            if not config:
                logger.error("关键词配置为空")
                return False
                
            if "log_files" not in config or not config["log_files"]:
                logger.error("缺少日志文件配置")
                return False
                
            for log_file in config["log_files"]:
                if "path" not in log_file:
                    logger.error("日志文件缺少路径配置")
                    return False
                    
                if "keywords" not in log_file or not log_file["keywords"]:
                    logger.warning(f"日志文件没有关键词配置: {log_file.get('path')}")
            
            return True
            
        except Exception as e:
            logger.error(f"关键词配置验证失败: {e}")
            return False
    
    def validate_telegram_config(self) -> bool:
        """
        验证Telegram配置是否有效
        
        Returns:
            配置是否有效
        """
        try:
            config = self.get_telegram_config()
            
            # 检查必要的配置项
            if not config:
                logger.error("Telegram配置为空")
                return False
                
            if "bot_token" not in config or not config["bot_token"]:
                logger.error("缺少Bot Token配置")
                return False
                
            if "chat_id" not in config or not config["chat_id"]:
                logger.error("缺少Chat ID配置")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Telegram配置验证失败: {e}")
            return False 