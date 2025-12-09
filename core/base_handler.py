# -*- coding: utf-8 -*-
"""
语种处理器基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from .language_config import LanguageConfig
from .word_loader import WordLoader
from .card_renderer import CardRenderer


@dataclass
class WordEntry:
    """
    统一的单词数据模型

    提供跨语种的统一数据结构，支持通过 extra_fields 扩展
    """

    word: str
    phonetic: Optional[str] = None
    pos: Optional[str] = None
    definition: str = ""
    example: Optional[str] = None
    extra_fields: Dict[str, any] = field(default_factory=dict)

    def validate(self) -> bool:
        """
        验证数据完整性

        Returns:
            True 如果数据有效
        """
        return bool(self.word and self.definition)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'word': self.word,
            'phonetic': self.phonetic,
            'pos': self.pos,
            'definition': self.definition,
            'example': self.example,
            **self.extra_fields
        }


class BaseLanguageHandler(ABC):
    """
    语种处理器基类

    定义所有语种处理器必须实现的接口，包括：
    - 词汇加载
    - 单词选择
    - 卡片渲染
    - 字体和样式配置
    """

    def __init__(self, config: LanguageConfig, lang_dir: Path):
        """
        初始化处理器

        Args:
            config: 语种配置
            lang_dir: 语种目录路径
        """
        self.config = config
        self.lang_dir = lang_dir
        self.words: List[WordEntry] = []

        # 初始化加载器（支持共享词库路径）
        shared_path = getattr(config, 'shared_words_path', None)
        self.loader = WordLoader(lang_dir / "words.json", shared_path)
        # 使用根目录下的 templates
        self.renderer = CardRenderer(lang_dir.parent.parent / "templates")

    @abstractmethod
    def load_words(self) -> List[WordEntry]:
        """
        加载词汇数据

        子类必须实现此方法，将原始数据转换为 WordEntry 列表

        Returns:
            WordEntry 列表
        """
        pass

    @abstractmethod
    def render_card(self, word: WordEntry, **kwargs) -> str:
        """
        渲染卡片 HTML

        子类必须实现此方法，根据语种特点渲染卡片

        Args:
            word: 单词数据
            **kwargs: 额外参数（背景图、主题色等）

        Returns:
            渲染后的 HTML 字符串
        """
        pass

    def get_fonts(self) -> Dict[str, str]:
        """
        获取字体配置

        Returns:
            字体配置字典
        """
        return self.config.fonts

    def get_styles(self) -> Dict[str, any]:
        """
        获取样式配置

        Returns:
            样式配置字典
        """
        return self.config.styles

    def get_theme_colors(self) -> List[str]:
        """
        获取主题色列表

        Returns:
            主题色列表
        """
        return self.config.theme_colors if self.config.theme_colors else [
            "#2F4F4F", "#4B0082", "#006400", "#8B0000",
            "#2F2F4F", "#4A4A6A", "#1a1a2e", "#16213e",
            "#0f3460", "#533483"
        ]
