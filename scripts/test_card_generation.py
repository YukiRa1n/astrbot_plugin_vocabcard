# -*- coding: utf-8 -*-
"""
测试所有卡组的卡片生成功能
"""

import asyncio
import random
import sys
from pathlib import Path

# 添加项目根目录到路径
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

# CDN 背景图
CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/marek-piwnicki-lm_CeNw9bH4-unsplash.jpg",
]


async def main():
    from core.image_renderer import get_image_renderer
    from core.language_manager import LanguageManager
    from languages.classical import ClassicalLanguageHandler
    from languages.english import EnglishLanguageHandler
    from languages.idiom import IdiomLanguageHandler
    from languages.japanese import JapaneseLanguageHandler
    from languages.radio import RadioLanguageHandler

    print("=" * 50)
    print("测试所有卡组的卡片生成")
    print("=" * 50)

    lang_manager = LanguageManager(project_dir)
    lang_manager.register_language("english", EnglishLanguageHandler)
    lang_manager.register_language("japanese", JapaneseLanguageHandler)
    lang_manager.register_language("japanese_n1", JapaneseLanguageHandler)
    lang_manager.register_language("idiom", IdiomLanguageHandler)
    lang_manager.register_language("classical", ClassicalLanguageHandler)
    lang_manager.register_language("radio", RadioLanguageHandler)

    output_dir = project_dir / "test_output"
    output_dir.mkdir(exist_ok=True)

    decks = [
        ("english", "英语"),
        ("japanese", "日语"),
        ("japanese_n1", "日语N1"),
        ("idiom", "成语"),
        ("classical", "古文"),
        ("radio", "无线电法规"),
    ]

    image_renderer = get_image_renderer()
    try:
        for deck_id, deck_name in decks:
            print(f"\n[{deck_name}]")
            handler = lang_manager.get_handler(deck_id)
            words = handler.load_words()
            print(f"  词条数: {len(words)}")

            word = random.choice(words)
            print(
                f"  测试词: {word.word[:30]}..."
                if len(word.word) > 30
                else f"  测试词: {word.word}"
            )

            bg_url = random.choice(CDN_BACKGROUNDS)
            theme_colors = handler.get_theme_colors()
            theme_color = random.choice(theme_colors) if theme_colors else "#1a1a2e"
            bg_pos = f"{random.randint(0, 100)}% {random.randint(0, 100)}%"
            html = handler.render_card(
                word, bg_url=bg_url, theme_color=theme_color, bg_position=bg_pos
            )

            output_path = output_dir / f"test_{deck_id}.png"
            width, height = handler.config.card_size
            await image_renderer.render_to_file(
                html, str(output_path), width=width, height=height, scale=2
            )
            print(f"  ✓ 生成成功: {output_path.name}")
    finally:
        await image_renderer.close()

    print("\n" + "=" * 50)
    print(f"测试完成！图片保存在: {output_dir}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
