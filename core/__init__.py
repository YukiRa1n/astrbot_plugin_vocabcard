# -*- coding: utf-8 -*-
"""
核心模块 - 多语种/多卡片类型支持架构
"""

from .language_config import LanguageConfig
from .base_handler import BaseLanguageHandler, WordEntry
from .word_loader import WordLoader
from .card_renderer import CardRenderer
from .language_manager import LanguageManager

__all__ = [
    'LanguageConfig',
    'BaseLanguageHandler',
    'WordEntry',
    'WordLoader',
    'CardRenderer',
    'LanguageManager'
]
