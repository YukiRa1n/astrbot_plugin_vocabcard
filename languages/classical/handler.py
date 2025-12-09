# -*- coding: utf-8 -*-
"""古文词汇处理器"""

from typing import List
from ...core.base_handler import BaseLanguageHandler, WordEntry


class ClassicalLanguageHandler(BaseLanguageHandler):
    """古文词汇处理器"""

    def load_words(self) -> List[WordEntry]:
        """加载古文词汇"""
        raw_data = self.loader.load_json()

        words = []
        for item in raw_data:
            word_entry = WordEntry(
                word=item.get("keyword", ""),
                phonetic=f"第{item.get('sentence_num', '')}句",
                pos="古文",
                definition=item.get("content", ""),
                example="",
                extra_fields={"sentence_num": item.get("sentence_num", "")}
            )

            if word_entry.word and word_entry.definition:
                words.append(word_entry)

        self.words = words
        return words

    def render_card(self, word: WordEntry, **kwargs) -> str:
        """渲染古文卡片"""
        template_vars = {
            "keyword": word.word,
            "sentence_num": word.extra_fields.get("sentence_num", ""),
            "content": word.definition,
            "bg_url": kwargs.get("bg_url", ""),
            "theme_color": kwargs.get("theme_color", "#2F4F4F"),
            "bg_position": kwargs.get("bg_position", "50% 50%"),
            "font_word": self.config.fonts.get("word", "serif"),
            "font_content": self.config.fonts.get("content", "serif"),
            "keyword_size": self.config.styles.get("keyword_size", "42px"),
            "content_size": self.config.styles.get("content_size", "16px"),
            "tag1": "#古文",
            "tag2": "#Daily",
            "brand": "古文卡片"
        }
        return self.renderer.render("card_classical.html", template_vars)
