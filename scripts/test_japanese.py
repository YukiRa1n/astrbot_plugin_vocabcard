# -*- coding: utf-8 -*-
"""
测试日语卡片生成
"""

import asyncio
import json
import sys
from pathlib import Path

project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
]


async def main():
    from core.image_renderer import get_image_renderer
    from core.card_renderer import CardRenderer

    print("测试日语卡片生成...")

    # 加载日语词汇
    words_path = project_dir / "languages" / "japanese" / "words.json"
    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    # 选择一个词
    word_data = words[0]  # 高校
    print(f"测试词汇: {word_data['word']} ({word_data['kana']})")

    # 加载配置
    config_path = project_dir / "languages" / "japanese" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 准备模板变量
    template_vars = {
        "word": word_data["word"],
        "kana": word_data.get("kana", ""),
        "accent": word_data.get("accent", ""),
        "pos": word_data.get("pos", ""),
        "definition_cn": word_data.get("definition_cn", ""),
        "example_ja": word_data.get("example_ja", ""),
        "example_cn": word_data.get("example_cn", ""),
        "bg_url": CDN_BACKGROUNDS[0],
        "theme_color": "#8B4513",
        "bg_position": "50% 30%",
        "font_word": config["fonts"]["word"],
        "font_phonetic": config["fonts"]["phonetic"],
        "font_definition": config["fonts"]["definition"],
        "font_example": config["fonts"]["example"],
        "word_size": config["styles"]["word_size"],
        "word_letter_spacing": config["styles"]["word_letter_spacing"],
        "phonetic_size": config["styles"]["phonetic_size"],
        "definition_size": config["styles"]["definition_size"],
        "example_size": config["styles"]["example_size"],
        "example_style": config["styles"]["example_style"],
        "tag1": f"#{word_data.get('level', 'JLPT')}",
        "tag2": "#Daily",
        "brand": "毎日単語",
    }

    # 渲染模板
    renderer = CardRenderer(project_dir / "templates")
    html = renderer.render("card_japanese.html", template_vars)

    # 生成图片
    image_renderer = get_image_renderer()
    output_path = str(project_dir / "test_japanese.png")
    await image_renderer.render_to_file(html, output_path, width=432, height=540, scale=2)

    print(f"日语卡片已生成: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
