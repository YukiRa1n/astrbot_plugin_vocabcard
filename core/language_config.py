# -*- coding: utf-8 -*-
"""
语种配置模型
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class LanguageConfig:
    """
    语种配置数据类

    存储每个语种/卡片类型的特定配置，包括：
    - 基本信息（ID、名称）
    - 字体配置
    - 样式配置
    - 卡片尺寸
    - 主题色
    - 等级过滤器（用于日语 JLPT 分级）
    - 共享词库路径（用于多卡组共享数据）
    """

    lang_id: str
    lang_name: str
    fonts: Dict[str, str]
    styles: Dict[str, any]
    card_size: tuple = (432, 540)
    theme_colors: List[str] = field(default_factory=list)
    level_filter: str = "all"  # JLPT 等级过滤器
    shared_words_path: Optional[str] = None  # 共享词库文件路径（相对于 languages 目录）

    @classmethod
    def from_json(cls, config_path: Path) -> 'LanguageConfig':
        """
        从 JSON 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            LanguageConfig 实例
        """
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 处理默认值
        if 'card_size' in data and isinstance(data['card_size'], list):
            data['card_size'] = tuple(data['card_size'])

        if 'theme_colors' not in data:
            data['theme_colors'] = []

        if 'level_filter' not in data:
            data['level_filter'] = "all"

        if 'shared_words_path' not in data:
            data['shared_words_path'] = None

        return cls(**data)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'lang_id': self.lang_id,
            'lang_name': self.lang_name,
            'fonts': self.fonts,
            'styles': self.styles,
            'card_size': list(self.card_size),
            'theme_colors': self.theme_colors
        }
