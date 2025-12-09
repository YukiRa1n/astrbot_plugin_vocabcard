# -*- coding: utf-8 -*-
"""
英语语种处理器
"""

import random
from typing import List, Dict
from pathlib import Path

from ...core.base_handler import BaseLanguageHandler, WordEntry
from ...core.language_config import LanguageConfig


class EnglishLanguageHandler(BaseLanguageHandler):
    """
    英语词汇处理器

    负责：
    - 加载英语词汇数据
    - 渲染英语卡片
    - 提供英语特定的样式和字体配置
    """

    def load_words(self) -> List[WordEntry]:
        """
        加载英语词汇

        从 words.json 加载数据并转换为 WordEntry 列表

        Returns:
            WordEntry 列表
        """
        raw_data = self.loader.load_json()

        words = []
        for item in raw_data:
            word_entry = WordEntry(
                word=item.get("word", ""),
                phonetic=item.get("phonetic", ""),
                pos=item.get("pos", ""),
                definition=item.get("definition_cn", ""),
                example=item.get("example", ""),
                extra_fields={}
            )

            if word_entry.validate():
                words.append(word_entry)

        self.words = words
        return words

    def render_card(self, word: WordEntry, **kwargs) -> str:
        """
        渲染英语卡片

        Args:
            word: 单词数据
            **kwargs: 额外参数
                - bg_url: 背景图 URL
                - theme_color: 主题色
                - bg_position: 背景位置

        Returns:
            渲染后的 HTML 字符串
        """
        # 准备模板变量
        template_vars = {
            # 单词数据
            "word": word.word,
            "phonetic": word.phonetic or "",
            "pos": (word.pos or "WORD").upper(),
            "definition_cn": word.definition,
            "example": word.example or "",

            # 背景和主题
            "bg_url": kwargs.get("bg_url", ""),
            "theme_color": kwargs.get("theme_color", "#2F4F4F"),
            "bg_position": kwargs.get("bg_position", "50% 50%"),

            # 字体配置
            "font_word": self.config.fonts.get("word", "serif"),
            "font_phonetic": self.config.fonts.get("phonetic", "monospace"),
            "font_definition": self.config.fonts.get("definition", "sans-serif"),
            "font_example": self.config.fonts.get("example", "serif"),

            # 样式配置
            "word_size": self.config.styles.get("word_size", "52px"),
            "word_letter_spacing": self.config.styles.get("word_letter_spacing", "-1px"),
            "phonetic_size": self.config.styles.get("phonetic_size", "15px"),
            "definition_size": self.config.styles.get("definition_size", "18px"),
            "example_size": self.config.styles.get("example_size", "14px"),
            "example_style": self.config.styles.get("example_style", "italic"),

            # 标签
            "tag1": "#CET6",
            "tag2": "#Daily",
            "brand": "Daily Vocab"
        }

        # 渲染模板
        return self.renderer.render("card.html", template_vars)

    def _get_background_url(self, word: WordEntry, backgrounds: List[Path]) -> str:
        """
        获取背景图 URL

        Args:
            word: 单词数据
            backgrounds: 背景图列表

        Returns:
            背景图 URL
        """
        if not backgrounds:
            # 降级方案：纯色背景
            return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1080' height='1350'%3E%3Crect fill='%231a1a2e' width='100%25' height='100%25'/%3E%3C/svg%3E"

        bg_path = random.choice(backgrounds)
        return f"file:///{bg_path.as_posix()}"

    def _random_bg_position(self) -> str:
        """
        生成随机背景位置

        Returns:
            CSS 背景位置字符串
        """
        bg_x = random.randint(0, 100)
        bg_y = random.randint(0, 100)
        return f"{bg_x}% {bg_y}%"
