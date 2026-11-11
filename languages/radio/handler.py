# -*- coding: utf-8 -*-
"""无线电法规处理器"""

from typing import List
from ...core.base_handler import BaseLanguageHandler, WordEntry


class RadioLanguageHandler(BaseLanguageHandler):
    """无线电法规处理器"""

    def load_words(self) -> List[WordEntry]:
        """加载无线电法规题库"""
        raw_data = self.loader.load_json()

        words = []
        for item in raw_data:
            word_entry = WordEntry(
                word=item.get("question_id", ""),
                phonetic="",
                pos="法规",
                definition=item.get("answer", ""),
                example=item.get("question", ""),
                extra_fields={"tags": item.get("tags", "")},
            )

            if word_entry.example and word_entry.definition:
                words.append(word_entry)

        self.words = words
        return words

    def render_card(self, word: WordEntry, **kwargs) -> str:
        """渲染无线电法规卡片"""
        question = word.example or ""
        answer = word.definition or ""
        total_len = len(question) + len(answer)
        if total_len > 180:
            question_size = "14px"
            answer_size = "13px"
        elif total_len > 110:
            question_size = "15px"
            answer_size = "15px"
        else:
            question_size = self.config.styles.get("question_size", "16px")
            answer_size = self.config.styles.get("answer_size", "18px")

        template_vars = {
            "question_id": word.word,
            "question": question,
            "answer": answer,
            "tags": word.extra_fields.get("tags", ""),
            "bg_url": kwargs.get("bg_url", ""),
            "theme_color": kwargs.get("theme_color", "#0f3460"),
            "bg_position": kwargs.get("bg_position", "50% 50%"),
            "font_question": self.get_safe_font("question", "sans-serif"),
            "font_answer": self.get_safe_font("answer", "sans-serif"),
            "question_size": question_size,
            "answer_size": answer_size,
            "tag1": "#无线电",
            "tag2": "#法规",
            "brand": "无线电法规",
        }
        return self.renderer.render("card_radio.html", template_vars)
