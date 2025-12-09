# -*- coding: utf-8 -*-
"""
测试 Playwright 渲染器
"""

import json
import sys
from pathlib import Path

project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
]


def main():
    """测试渲染器"""
    from core.image_renderer import get_image_renderer

    print("测试 Playwright 渲染器...")

    # 加载词汇
    words_path = project_dir / "languages" / "english" / "words.json"
    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    word_data = words[2]  # extraordinary

    # 加载模板
    template_path = project_dir / "languages" / "english" / "templates" / "card.html"
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 替换变量
    variables = {
        "word": word_data["word"],
        "phonetic": word_data.get("phonetic", ""),
        "pos": word_data.get("pos", ""),
        "definition_cn": word_data.get("definition_cn", ""),
        "example": word_data.get("example", ""),
        "bg_url": CDN_BACKGROUNDS[0],
        "theme_color": "#1a1a2e",
        "bg_position": "50% 30%",
        "font_definition": "'Noto Sans SC', 'Microsoft YaHei', sans-serif",
        "font_word": "'Georgia', serif",
        "font_phonetic": "'Consolas', monospace",
        "font_example": "'Georgia', serif",
        "word_size": "52px",
        "phonetic_size": "15px",
        "definition_size": "18px",
        "example_size": "14px",
        "example_style": "italic",
        "word_letter_spacing": "-1px",
        "tag1": "#CET6",
        "tag2": "#Daily",
        "brand": "VocabCard",
    }

    html = template
    for key, value in variables.items():
        html = html.replace("{{ " + key + " }}", str(value) if value else "")
        html = html.replace("{{" + key + "}}", str(value) if value else "")

    # 测试渲染
    renderer = get_image_renderer()
    output_path = str(project_dir / "test_output.png")
    renderer.render_to_file(html, output_path, width=432, height=540, scale=2)

    print(f"测试成功！图片已生成: {output_path}")


if __name__ == "__main__":
    main()
