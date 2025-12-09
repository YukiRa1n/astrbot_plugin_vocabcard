# -*- coding: utf-8 -*-
"""
生成 README 示例图片 (使用 Playwright)
"""

import asyncio
import json
from pathlib import Path

project_dir = Path(__file__).parent.parent

# CDN 背景图
CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
]


async def main():
    """生成示例英语单词卡片"""
    from playwright.async_api import async_playwright

    print("正在生成示例图片...")

    # 加载英语词汇
    words_path = project_dir / "languages" / "english" / "words.json"
    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    # 选择 extraordinary
    word_data = None
    for w in words:
        if w.get("word") == "extraordinary":
            word_data = w
            break

    if not word_data:
        word_data = words[2]

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

    # 保存临时 HTML
    temp_html = project_dir / "temp_card.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html)

    output_path = project_dir / "example.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 432, "height": 540}, device_scale_factor=2
            )
            await page.goto(temp_html.as_uri())

            # 等待背景图加载
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass
            await page.wait_for_timeout(3000)

            # 截图
            await page.screenshot(path=str(output_path), type="png", scale="device")
            await browser.close()

        print(f"示例图片已生成: {output_path}")
    finally:
        if temp_html.exists():
            temp_html.unlink()


if __name__ == "__main__":
    asyncio.run(main())
