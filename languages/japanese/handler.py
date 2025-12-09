# -*- coding: utf-8 -*-
"""
日语语种处理器
"""

import random
from typing import List, Dict
from pathlib import Path

from ...core.base_handler import BaseLanguageHandler, WordEntry
from ...core.language_config import LanguageConfig


class JapaneseLanguageHandler(BaseLanguageHandler):
    """
    日语词汇处理器

    负责：
    - 加载日语词汇数据（汉字、假名、JLPT等级）
    - 渲染日语卡片
    - 提供日语特定的样式和字体配置
    """

    def load_words(self, level_filter: str = None) -> List[WordEntry]:
        """
        加载日语词汇

        从 words.json 加载数据并转换为 WordEntry 列表
        日语数据包含：word(汉字), kana(假名), accent(重音), pos(词性),
        definition_cn(中文释义), example_ja(日语例句), example_cn(中文例句翻译),
        level(JLPT等级)

        Args:
            level_filter: JLPT等级筛选，可选值: all, N1, N2, N3, N4, N5
                         如果为 None，则使用配置文件中的 level_filter

        Returns:
            WordEntry 列表
        """
        # 优先使用传入参数，否则使用配置中的默认值
        filter_level = level_filter if level_filter is not None else getattr(self.config, 'level_filter', 'all')

        raw_data = self.loader.load_json()

        words = []
        for item in raw_data:
            # 等级筛选
            item_level = item.get("level", "")  # 格式: JLPT-N4
            if filter_level != "all":
                # 检查是否匹配指定等级
                if f"JLPT-{filter_level}" not in item_level and filter_level not in item_level:
                    continue

            word_entry = WordEntry(
                word=item.get("word", ""),
                phonetic=item.get("kana", ""),  # 假名读音
                pos=item.get("pos", ""),
                definition=item.get("definition_cn", ""),
                example=item.get("example_ja", ""),  # 日语例句
                extra_fields={
                    "accent": item.get("accent", ""),  # 重音标记
                    "example_cn": item.get("example_cn", ""),  # 中文例句翻译
                    "level": item_level  # JLPT等级
                }
            )

            if word_entry.validate():
                words.append(word_entry)

        self.words = words
        return words

    def render_card(self, word: WordEntry, **kwargs) -> str:
        """
        渲染日语卡片

        Args:
            word: 单词数据
            **kwargs: 额外参数
                - bg_url: 背景图 URL
                - theme_color: 主题色
                - bg_position: 背景位置

        Returns:
            渲染后的 HTML 字符串
        """
        # 提取日语特定字段
        accent = word.extra_fields.get("accent", "")
        example_cn = word.extra_fields.get("example_cn", "")
        level = word.extra_fields.get("level", "JLPT")

        # 准备模板变量
        template_vars = {
            # 单词数据
            "word": word.word,  # 汉字
            "kana": word.phonetic,  # 假名
            "accent": accent,  # 重音标记
            "pos": word.pos or "単語",
            "definition_cn": word.definition,
            "example_ja": word.example or "",  # 日语例句
            "example_cn": example_cn,  # 中文例句翻译

            # 背景和主题
            "bg_url": kwargs.get("bg_url", ""),
            "theme_color": kwargs.get("theme_color", "#8B4513"),
            "bg_position": kwargs.get("bg_position", "50% 50%"),

            # 字体配置
            "font_word": self.config.fonts.get("word", "serif"),
            "font_phonetic": self.config.fonts.get("phonetic", "sans-serif"),
            "font_definition": self.config.fonts.get("definition", "sans-serif"),
            "font_example": self.config.fonts.get("example", "serif"),

            # 样式配置
            "word_size": self.config.styles.get("word_size", "48px"),
            "word_letter_spacing": self.config.styles.get("word_letter_spacing", "0.05em"),
            "phonetic_size": self.config.styles.get("phonetic_size", "16px"),
            "definition_size": self.config.styles.get("definition_size", "18px"),
            "example_size": self.config.styles.get("example_size", "14px"),
            "example_style": self.config.styles.get("example_style", "normal"),

            # 标签
            "tag1": f"#{level}",  # JLPT等级
            "tag2": "#Daily",
            "brand": "毎日単語"  # 日语品牌名
        }

        # 渲染模板
        return self.renderer.render("card_japanese.html", template_vars)

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
            return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1080' height='1350'%3E%3Crect fill='%238B4513' width='100%25' height='100%25'/%3E%3C/svg%3E"

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
