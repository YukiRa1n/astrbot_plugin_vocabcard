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
    """

    lang_id: str
    lang_name: str
    fonts: Dict[str, str]
    styles: Dict[str, any]
    card_size: tuple = (432, 540)
    theme_colors: List[str] = field(default_factory=list)

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
