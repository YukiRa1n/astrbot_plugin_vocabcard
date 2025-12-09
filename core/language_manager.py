# -*- coding: utf-8 -*-
"""
语种管理器
"""

from pathlib import Path
from typing import Dict, Type, List

from .base_handler import BaseLanguageHandler
from .language_config import LanguageConfig


class LanguageManager:
    """
    语种管理器

    负责：
    - 注册和管理所有语种处理器
    - 加载语种配置
    - 提供统一的访问接口
    """

    def __init__(self, plugin_dir: Path):
        """
        初始化管理器

        Args:
            plugin_dir: 插件根目录
        """
        self.plugin_dir = plugin_dir
        self.languages_dir = plugin_dir / "languages"
        self._handlers: Dict[str, BaseLanguageHandler] = {}
        self._configs: Dict[str, LanguageConfig] = {}
        self._handler_classes: Dict[str, Type[BaseLanguageHandler]] = {}

    def register_language(self, lang_id: str, handler_class: Type[BaseLanguageHandler]):
        """
        注册语种处理器

        Args:
            lang_id: 语种 ID（如 'english', 'japanese'）
            handler_class: 处理器类
        """
        self._handler_classes[lang_id] = handler_class

        # 加载配置
        config_path = self.languages_dir / lang_id / "config.json"
        if config_path.exists():
            config = LanguageConfig.from_json(config_path)
            self._configs[lang_id] = config

    def get_handler(self, lang_id: str) -> BaseLanguageHandler:
        """
        获取语种处理器（懒加载）

        Args:
            lang_id: 语种 ID

        Returns:
            语种处理器实例

        Raises:
            ValueError: 语种未注册
        """
        # 如果已经实例化，直接返回
        if lang_id in self._handlers:
            return self._handlers[lang_id]

        # 检查是否已注册
        if lang_id not in self._handler_classes:
            raise ValueError(f"语种 '{lang_id}' 未注册")

        # 实例化处理器
        handler_class = self._handler_classes[lang_id]
        config = self._configs.get(lang_id)
        lang_dir = self.languages_dir / lang_id

        if not config:
            raise ValueError(f"语种 '{lang_id}' 配置文件不存在")

        handler = handler_class(config, lang_dir)
        self._handlers[lang_id] = handler

        return handler

    def list_languages(self) -> List[Dict[str, str]]:
        """
        列出所有已注册的语种

        Returns:
            语种信息列表
        """
        languages = []
        for lang_id in self._handler_classes.keys():
            config = self._configs.get(lang_id)
            languages.append({
                'id': lang_id,
                'name': config.lang_name if config else lang_id
            })
        return languages

    def is_registered(self, lang_id: str) -> bool:
        """
        检查语种是否已注册

        Args:
            lang_id: 语种 ID

        Returns:
            True 如果已注册
        """
        return lang_id in self._handler_classes
