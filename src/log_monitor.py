# -*- coding: utf-8 -*-

"""
日志监控模块

用于读取日志文件并匹配关键词，发现匹配的日志时通知。
"""

import os
import time
import re
import glob
import logging
from typing import Dict, List, Set, Optional, Any, Tuple

logger = logging.getLogger("tg_notification")

class LogReader:
    """日志读取器，用于读取和跟踪日志文件"""
    
    def __init__(self, log_path: str, multiline_config: Optional[Dict[str, Any]] = None):
        """
        初始化日志读取器
        
        Args:
            log_path: 日志文件路径
            multiline_config: 多行日志配置，包含类型和模式
        """
        self.log_path = log_path
        self.last_position = 0
        self.last_inode = None
        self.file_exists = False
        self.multiline_config = multiline_config
        self.multiline_pattern = None
        
        # 如果有多行配置，则编译正则表达式
        if self.multiline_config and self.multiline_config.get("type") == "pattern":
            pattern = self.multiline_config.get("pattern", "")
            if pattern:
                try:
                    self.multiline_pattern = re.compile(pattern)
                    logger.debug(f"已编译多行匹配模式: {pattern}")
                except re.error as e:
                    logger.error(f"多行匹配模式编译失败: {pattern}, 错误: {e}")
    
    def get_file_inode(self) -> Optional[int]:
        """
        获取文件的inode，用于检测文件是否被替换
        
        Returns:
            文件的inode，如果文件不存在则返回None
        """
        try:
            if os.path.exists(self.log_path):
                return os.stat(self.log_path).st_ino
            return None
        except OSError as e:
            logger.error(f"获取文件inode失败: {self.log_path}, 错误: {e}")
            return None
    
    def check_file_changed(self) -> bool:
        """
        检查文件是否发生变化（被替换或新建）
        
        Returns:
            文件是否变化
        """
        current_inode = self.get_file_inode()
        
        # 文件不存在
        if current_inode is None:
            if self.file_exists:
                logger.warning(f"日志文件不存在或无法访问: {self.log_path}")
                self.file_exists = False
            return False
        
        # 文件新建或被替换
        if self.last_inode != current_inode:
            self.last_inode = current_inode
            self.last_position = 0
            self.file_exists = True
            logger.info(f"日志文件已变更或新建: {self.log_path}")
            return True
        
        # 文件大小变化
        try:
            current_size = os.path.getsize(self.log_path)
            if current_size < self.last_position:
                logger.info(f"日志文件被截断: {self.log_path}")
                self.last_position = 0
                return True
            elif current_size > self.last_position:
                return True
        except OSError as e:
            logger.error(f"获取文件大小失败: {self.log_path}, 错误: {e}")
        
        return False
    
    def _process_multiline_logs(self, raw_lines: List[str]) -> List[str]:
        """
        处理多行日志，将属于同一条日志的多行合并
        
        Args:
            raw_lines: 原始日志行列表
            
        Returns:
            处理后的日志行列表
        """
        if not self.multiline_pattern:
            return raw_lines
        
        processed_lines = []
        current_log = None
        
        for line in raw_lines:
            # 检查是否是新日志的开始
            if self.multiline_pattern.match(line):
                # 如果有当前日志，则添加到结果中
                if current_log is not None:
                    processed_lines.append(current_log)
                current_log = line
            else:
                # 如果不是新日志的开始，则附加到当前日志
                if current_log is not None:
                    current_log += "\n" + line
                else:
                    # 如果没有当前日志（可能是文件的第一行不匹配模式），则创建一个新日志
                    current_log = line
        
        # 添加最后一条日志
        if current_log is not None:
            processed_lines.append(current_log)
        
        return processed_lines
    
    def read_new_lines(self) -> List[str]:
        """
        读取日志文件中的新行
        
        Returns:
            新增的日志行列表
        """
        if not os.path.exists(self.log_path):
            return []
        
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='replace') as file:
                file.seek(0, os.SEEK_END)
                end_position = file.tell()
                
                if end_position <= self.last_position:
                    return []
                
                file.seek(self.last_position)
                raw_lines = file.readlines()
                self.last_position = end_position
                
                # 去除行尾换行符
                raw_lines = [line.rstrip('\n') for line in raw_lines]
                
                # 如果有多行配置，则处理多行日志
                if self.multiline_pattern:
                    return self._process_multiline_logs(raw_lines)
                
                return raw_lines
        except Exception as e:
            logger.error(f"读取日志文件失败: {self.log_path}, 错误: {e}")
            return []

class KeywordMatcher:
    """关键词匹配器，用于在日志行中匹配关键词"""
    
    def __init__(self, keywords: List[str], use_regex: bool = False):
        """
        初始化关键词匹配器
        
        Args:
            keywords: 关键词列表
            use_regex: 是否使用正则表达式匹配
        """
        self.keywords = keywords
        self.use_regex = use_regex
        self.regex_patterns = []
        
        if use_regex:
            self.compile_regex_patterns()
    
    def compile_regex_patterns(self):
        """编译正则表达式模式"""
        self.regex_patterns = []
        for keyword in self.keywords:
            try:
                pattern = re.compile(keyword)
                self.regex_patterns.append(pattern)
            except re.error as e:
                logger.error(f"正则表达式编译失败: {keyword}, 错误: {e}")
    
    def match(self, line: str) -> bool:
        """
        检查日志行是否匹配关键词
        
        Args:
            line: 日志行
            
        Returns:
            是否匹配
        """
        if self.use_regex:
            for pattern in self.regex_patterns:
                if pattern.search(line):
                    return True
        else:
            for keyword in self.keywords:
                if keyword in line:
                    return True
        
        return False
    
    def get_context(self, lines: List[str], matched_index: int, context_lines: int = 2) -> List[str]:
        """
        获取匹配行的上下文
        
        Args:
            lines: 所有日志行
            matched_index: 匹配行的索引
            context_lines: 上下文行数
            
        Returns:
            包含上下文的日志行列表
        """
        start = max(0, matched_index - context_lines)
        end = min(len(lines), matched_index + context_lines + 1)
        
        context = []
        for i in range(start, end):
            prefix = ">> " if i == matched_index else "   "
            context.append(f"{prefix}{lines[i]}")
        
        return context

class LogMonitor:
    """日志监控器，用于协调日志读取和关键词匹配"""
    
    def __init__(self, log_configs: List[Dict[str, Any]]):
        """
        初始化日志监控器
        
        Args:
            log_configs: 日志配置列表
        """
        self.log_readers = {}
        self.matchers = {}
        self.setup_monitors(log_configs)
        self.processed_hashes = set()  # 用于去重
    
    def _expand_path_patterns(self, path: str) -> List[str]:
        """
        展开路径中的通配符
        
        Args:
            path: 可能包含通配符的路径
            
        Returns:
            展开后的路径列表
        """
        # 检查路径中是否包含通配符
        if '*' in path or '?' in path or '[' in path:
            expanded_paths = glob.glob(path)
            if not expanded_paths:
                logger.warning(f"通配符路径没有匹配到任何文件: {path}")
            return expanded_paths
        else:
            return [path]
    
    def setup_monitors(self, log_configs: List[Dict[str, Any]]):
        """
        设置监控器
        
        Args:
            log_configs: 日志配置列表
        """
        for config in log_configs:
            log_path = config.get("path")
            if not log_path:
                logger.warning("日志配置中缺少路径，跳过")
                continue
            
            keywords = config.get("keywords", [])
            if not keywords:
                logger.warning(f"日志 {log_path} 没有配置关键词，跳过")
                continue
            
            use_regex = config.get("use_regex", False)
            
            # 获取多行配置
            multiline_config = config.get("multiline")
            
            # 展开通配符路径
            expanded_paths = self._expand_path_patterns(log_path)
            
            # 为每个匹配的路径创建日志读取器
            for path in expanded_paths:
                self.log_readers[path] = LogReader(path, multiline_config)
                self.matchers[path] = KeywordMatcher(keywords, use_regex)
                
                logger.info(f"已设置日志监控: {path}, 关键词数量: {len(keywords)}, 使用正则: {use_regex}, 多行模式: {bool(multiline_config)}")
            
            # 如果是通配符路径，记录展开结果
            if len(expanded_paths) > 1 or (expanded_paths and expanded_paths[0] != log_path):
                logger.info(f"通配符路径 {log_path} 已展开为 {len(expanded_paths)} 个文件")
    
    def check_for_new_files(self, log_configs: List[Dict[str, Any]]):
        """
        检查通配符路径是否有新文件
        
        Args:
            log_configs: 日志配置列表
        """
        for config in log_configs:
            log_path = config.get("path")
            if not log_path or ('*' not in log_path and '?' not in log_path and '[' not in log_path):
                continue
            
            # 展开通配符路径
            expanded_paths = self._expand_path_patterns(log_path)
            
            # 检查是否有新文件
            for path in expanded_paths:
                if path not in self.log_readers:
                    logger.info(f"发现新文件: {path}")
                    
                    # 获取多行配置
                    multiline_config = config.get("multiline")
                    keywords = config.get("keywords", [])
                    use_regex = config.get("use_regex", False)
                    
                    # 创建日志读取器
                    self.log_readers[path] = LogReader(path, multiline_config)
                    self.matchers[path] = KeywordMatcher(keywords, use_regex)
                    
                    logger.info(f"已设置日志监控: {path}, 关键词数量: {len(keywords)}, 使用正则: {use_regex}, 多行模式: {bool(multiline_config)}")
    
    def check_logs(self, log_configs: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        检查所有日志文件，查找匹配的日志行
        
        Args:
            log_configs: 可选的日志配置列表，用于检查新文件
            
        Returns:
            匹配的日志信息列表
        """
        # 如果提供了配置，检查是否有新文件
        if log_configs:
            self.check_for_new_files(log_configs)
            
        matches = []
        
        for log_path, reader in self.log_readers.items():
            matcher = self.matchers.get(log_path)
            if not matcher:
                continue
            
            # 检查文件是否有变化
            if reader.check_file_changed():
                new_lines = reader.read_new_lines()
                
                if new_lines:
                    logger.debug(f"读取到 {len(new_lines)} 行新日志: {log_path}")
                    
                    # 检查每一行是否匹配关键词
                    for i, line in enumerate(new_lines):
                        if matcher.match(line):
                            # 获取上下文
                            context = matcher.get_context(new_lines, i)
                            
                            # 生成匹配记录的哈希，用于去重
                            match_hash = hash(f"{log_path}:{line}")
                            
                            # 去重检查
                            if match_hash not in self.processed_hashes:
                                self.processed_hashes.add(match_hash)
                                
                                matches.append({
                                    "log_path": log_path,
                                    "matched_line": line,
                                    "context": context,
                                    "timestamp": time.time()
                                })
                                
                                logger.info(f"发现匹配: {log_path}: {line[:100]}...")
        
        # 限制哈希集合大小，避免内存泄漏
        if len(self.processed_hashes) > 10000:
            self.processed_hashes = set(list(self.processed_hashes)[-5000:])
        
        return matches 