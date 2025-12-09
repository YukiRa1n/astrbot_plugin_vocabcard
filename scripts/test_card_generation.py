# -*- coding: utf-8 -*-
"""
测试所有卡组的卡片生成功能
"""

import asyncio
import json
import random
import sys
from pathlib import Path

# 添加项目根目录到路径
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class WordEntry:
    word: str
    phonetic: Optional[str] = None
    pos: Optional[str] = None
    definition: str = ""
    example: Optional[str] = None
    extra_fields: Dict = field(default_factory=dict)

    def validate(self):
        return bool(self.word and self.definition)


class LanguageConfig:
    def __init__(self, data):
        self.lang_id = data.get("lang_id", "")
        self.lang_name = data.get("lang_name", "")
        self.fonts = data.get("fonts", {})
        self.styles = data.get("styles", {})
        self.theme_colors = data.get("theme_colors", [])

    @classmethod
    def from_json(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))


class CardRenderer:
    def __init__(self, templates_dir):
        self.templates_dir = templates_dir

    def render(self, template_name, variables):
        template_path = self.templates_dir / template_name
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

        # 简单的模板替换
        for key, value in variables.items():
            html = html.replace("{{" + key + "}}", str(value) if value else "")

        # 处理简单的 {% if %} 条件
        import re
        # 移除 {% if xxx %} ... {% endif %} 中内容为空的块
        pattern = r'\{% if (\w+) %\}(.*?)\{% endif %\}'
        def replace_if(match):
            var_name = match.group(1)
            content = match.group(2)
            if variables.get(var_name):
                return content
            return ""
        html = re.sub(pattern, replace_if, html, flags=re.DOTALL)

        return html


# CDN 背景图
CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/marek-piwnicki-lm_CeNw9bH4-unsplash.jpg",
]


def load_words_gre(lang_dir):
    with open(lang_dir / "words.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    words = []
    for item in raw_data:
        definitions = item.get("definitions", [])
        definition_text = definitions[0] if definitions else ""
        word_entry = WordEntry(
            word=item.get("word", ""),
            phonetic=item.get("phonetic", ""),
            pos="",
            definition=definition_text,
            example=item.get("example", ""),
            extra_fields={
                "synonyms": item.get("synonyms", ""),
                "antonyms": item.get("antonyms", ""),
                "mnemo": item.get("mnemo", ""),
                "root": item.get("root", ""),
                "cognates": item.get("cognates", ""),
            },
        )
        if word_entry.validate():
            words.append(word_entry)
    return words


def load_words_idiom(lang_dir):
    with open(lang_dir / "words.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    words = []
    for item in raw_data:
        word_entry = WordEntry(
            word=item.get("word", ""),
            definition=item.get("definition", ""),
        )
        if word_entry.validate():
            words.append(word_entry)
    return words


def load_words_classical(lang_dir):
    with open(lang_dir / "words.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    words = []
    for item in raw_data:
        word_entry = WordEntry(
            word=item.get("keyword", ""),
            phonetic=f"第{item.get('sentence_num', '')}句",
            definition=item.get("content", ""),
            extra_fields={"sentence_num": item.get("sentence_num", "")},
        )
        if word_entry.word and word_entry.definition:
            words.append(word_entry)
    return words


def load_words_radio(lang_dir):
    with open(lang_dir / "words.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    words = []
    for item in raw_data:
        word_entry = WordEntry(
            word=item.get("question_id", ""),
            definition=item.get("answer", ""),
            example=item.get("question", ""),
            extra_fields={"tags": item.get("tags", "")},
        )
        if word_entry.example and word_entry.definition:
            words.append(word_entry)
    return words


def load_words_japanese_n1(lang_dir):
    with open(lang_dir / "words.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    words = []
    for item in raw_data:
        word_entry = WordEntry(
            word=item.get("word", ""),
            phonetic=item.get("reading", ""),
            pos=item.get("pos", ""),
            definition=item.get("definition", ""),
            example=item.get("example", ""),
            extra_fields={
                "kanji": item.get("kanji", ""),
                "level": item.get("level", "N1"),
            },
        )
        if word_entry.validate():
            words.append(word_entry)
    return words


def render_gre_card(word, config, renderer):
    mnemo = word.extra_fields.get("mnemo", "")
    if len(mnemo) > 200:
        mnemo = mnemo[:200] + "..."
    cognates = word.extra_fields.get("cognates", "")
    if len(cognates) > 100:
        cognates = cognates[:100] + "..."

    template_vars = {
        "word": word.word,
        "phonetic": word.phonetic or "",
        "definition": word.definition,
        "example": word.example or "",
        "mnemo": mnemo,
        "root": word.extra_fields.get("root", ""),
        "cognates": cognates,
        "bg_url": random.choice(CDN_BACKGROUNDS),
        "theme_color": random.choice(config.theme_colors) if config.theme_colors else "#1a1a2e",
        "bg_position": f"{random.randint(0,100)}% {random.randint(0,100)}%",
        "font_word": config.fonts.get("word", "serif"),
        "font_phonetic": config.fonts.get("phonetic", "monospace"),
        "font_definition": config.fonts.get("definition", "sans-serif"),
        "font_mnemo": config.fonts.get("mnemo", "sans-serif"),
        "word_size": config.styles.get("word_size", "48px"),
        "phonetic_size": config.styles.get("phonetic_size", "14px"),
        "definition_size": config.styles.get("definition_size", "15px"),
        "mnemo_size": config.styles.get("mnemo_size", "13px"),
        "word_letter_spacing": config.styles.get("word_letter_spacing", "-1px"),
        "tag1": "#GRE",
        "tag2": "#3000",
        "brand": "GRE Vocab",
    }
    return renderer.render("card.html", template_vars)


def render_idiom_card(word, config, renderer):
    template_vars = {
        "word": word.word,
        "definition": word.definition,
        "bg_url": random.choice(CDN_BACKGROUNDS),
        "theme_color": random.choice(config.theme_colors) if config.theme_colors else "#8B0000",
        "bg_position": f"{random.randint(0,100)}% {random.randint(0,100)}%",
        "font_word": config.fonts.get("word", "serif"),
        "font_definition": config.fonts.get("definition", "sans-serif"),
        "word_size": config.styles.get("word_size", "56px"),
        "definition_size": config.styles.get("definition_size", "18px"),
        "tag1": "#成语",
        "tag2": "#国学",
        "brand": "成语卡片",
    }
    return renderer.render("card.html", template_vars)


def render_classical_card(word, config, renderer):
    template_vars = {
        "keyword": word.word,
        "sentence_num": word.extra_fields.get("sentence_num", ""),
        "content": word.definition,
        "bg_url": random.choice(CDN_BACKGROUNDS),
        "theme_color": random.choice(config.theme_colors) if config.theme_colors else "#2F4F4F",
        "bg_position": f"{random.randint(0,100)}% {random.randint(0,100)}%",
        "font_word": config.fonts.get("word", "serif"),
        "font_content": config.fonts.get("content", "serif"),
        "keyword_size": config.styles.get("keyword_size", "42px"),
        "content_size": config.styles.get("content_size", "16px"),
        "tag1": "#古文",
        "tag2": "#经典",
        "brand": "古文卡片",
    }
    return renderer.render("card.html", template_vars)


def render_radio_card(word, config, renderer):
    template_vars = {
        "question_id": word.word,
        "question": word.example,
        "answer": word.definition,
        "bg_url": random.choice(CDN_BACKGROUNDS),
        "theme_color": random.choice(config.theme_colors) if config.theme_colors else "#0f3460",
        "bg_position": f"{random.randint(0,100)}% {random.randint(0,100)}%",
        "font_question": config.fonts.get("question", "sans-serif"),
        "font_answer": config.fonts.get("answer", "sans-serif"),
        "question_size": config.styles.get("question_size", "16px"),
        "answer_size": config.styles.get("answer_size", "18px"),
        "tag1": "#无线电",
        "tag2": "#法规",
        "brand": "无线电法规",
    }
    return renderer.render("card.html", template_vars)


def render_japanese_n1_card(word, config, renderer):
    template_vars = {
        "word": word.word,
        "kanji": word.extra_fields.get("kanji", ""),
        "reading": word.phonetic,
        "pos": word.pos or "",
        "definition": word.definition,
        "example": word.example or "",
        "level": word.extra_fields.get("level", "N1"),
        "bg_url": random.choice(CDN_BACKGROUNDS),
        "theme_color": random.choice(config.theme_colors) if config.theme_colors else "#533483",
        "bg_position": f"{random.randint(0,100)}% {random.randint(0,100)}%",
        "font_word": config.fonts.get("word", "sans-serif"),
        "font_reading": config.fonts.get("reading", "sans-serif"),
        "font_definition": config.fonts.get("definition", "sans-serif"),
        "word_size": config.styles.get("word_size", "48px"),
        "reading_size": config.styles.get("reading_size", "14px"),
        "definition_size": config.styles.get("definition_size", "16px"),
        "tag1": "#JLPT",
        "tag2": "#N1",
        "brand": "日语N1",
    }
    return renderer.render("card.html", template_vars)


async def generate_card_image(html_content, output_path):
    """使用 Playwright 生成卡片图片"""
    from playwright.async_api import async_playwright

    # 保存临时 HTML
    temp_html = output_path.parent / "temp_card.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 432, "height": 540}, device_scale_factor=2
            )
            await page.goto(temp_html.as_uri())

            # 等待背景图加载
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            await page.wait_for_timeout(2000)

            # 截图
            await page.screenshot(path=str(output_path), type="png", scale="device")
            await browser.close()

        print(f"  ✓ 生成成功: {output_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ 生成失败: {e}")
        return False
    finally:
        if temp_html.exists():
            temp_html.unlink()


async def main():
    print("=" * 50)
    print("测试所有卡组的卡片生成")
    print("=" * 50)

    languages_dir = project_dir / "languages"
    output_dir = project_dir / "test_output"
    output_dir.mkdir(exist_ok=True)

    # 定义卡组配置
    decks = [
        ("gre", "GRE3000", load_words_gre, render_gre_card),
        ("idiom", "成语", load_words_idiom, render_idiom_card),
        ("classical", "古文", load_words_classical, render_classical_card),
        ("radio", "无线电法规", load_words_radio, render_radio_card),
        ("japanese_n1", "日语N1", load_words_japanese_n1, render_japanese_n1_card),
    ]

    for deck_id, deck_name, load_func, render_func in decks:
        print(f"\n[{deck_name}]")
        lang_dir = languages_dir / deck_id

        # 加载配置
        config = LanguageConfig.from_json(lang_dir / "config.json")
        renderer = CardRenderer(lang_dir / "templates")

        # 加载词汇
        words = load_func(lang_dir)
        print(f"  词条数: {len(words)}")

        # 随机选一个词
        word = random.choice(words)
        print(f"  测试词: {word.word[:30]}..." if len(word.word) > 30 else f"  测试词: {word.word}")

        # 渲染 HTML
        html = render_func(word, config, renderer)

        # 生成图片
        output_path = output_dir / f"test_{deck_id}.png"
        await generate_card_image(html, output_path)

    print("\n" + "=" * 50)
    print(f"测试完成！图片保存在: {output_dir}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
