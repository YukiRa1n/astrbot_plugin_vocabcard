# -*- coding: utf-8 -*-
"""
成语词汇处理器
"""

from typing import List
from ...core.base_handler import BaseLanguageHandler, WordEntry


class IdiomLanguageHandler(BaseLanguageHandler):
    """成语词汇处理器"""

    def load_words(self) -> List[WordEntry]:
        """加载成语词汇"""
        raw_data = self.loader.load_json()

        words = []
        for item in raw_data:
            word_entry = WordEntry(
                word=item.get("word", ""),
                phonetic="",
                pos="成语",
                definition=item.get("definition", ""),
                example="",
                extra_fields={}
            )

            if word_entry.validate():
                words.append(word_entry)

        self.words = words
        return words

    def render_card(self, word: WordEntry, **kwargs) -> str:
        """渲染成语卡片"""
        template_vars = {
            "word": word.word,
            "definition": word.definition,
            "bg_url": kwargs.get("bg_url", ""),
            "theme_color": kwargs.get("theme_color", "#8B0000"),
            "bg_position": kwargs.get("bg_position", "50% 50%"),
            "font_word": self.config.fonts.get("word", "serif"),
            "font_definition": self.config.fonts.get("definition", "sans-serif"),
            "word_size": self.config.styles.get("word_size", "56px"),
            "definition_size": self.config.styles.get("definition_size", "18px"),
            "tag1": "#成语",
            "tag2": "#Daily",
            "brand": "成语卡片"
        }

        return self.renderer.render("card_idiom.html", template_vars)
