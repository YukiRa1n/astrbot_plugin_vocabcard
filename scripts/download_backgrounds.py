#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 gallery-dl 从 Unsplash 下载背景图
运行前请先安装: pip install gallery-dl
"""

import subprocess
import sys
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    plugin_dir = script_dir.parent
    backgrounds_dir = plugin_dir / "backgrounds"
    backgrounds_dir.mkdir(parents=True, exist_ok=True)

    # Unsplash 集合/搜索 URL 列表
    # 使用热门的风景/自然主题
    urls = [
        # 自然风景
        "https://unsplash.com/s/photos/nature-landscape",
        "https://unsplash.com/s/photos/mountain",
        "https://unsplash.com/s/photos/forest",
        "https://unsplash.com/s/photos/ocean",
        "https://unsplash.com/s/photos/sunset",
        "https://unsplash.com/s/photos/sky",
        # 抽象/简约
        "https://unsplash.com/s/photos/abstract",
        "https://unsplash.com/s/photos/gradient",
        "https://unsplash.com/s/photos/minimal",
        "https://unsplash.com/s/photos/texture",
    ]

    print("=" * 50)
    print("使用 gallery-dl 从 Unsplash 下载背景图")
    print(f"保存目录: {backgrounds_dir}")
    print("=" * 50)

    # 每个分类下载约20张，共约200张
    images_per_category = 20

    for url in urls:
        print(f"\n下载: {url}")
        try:
            cmd = [
                "gallery-dl",
                "--dest", str(backgrounds_dir),
                "--range", f"1-{images_per_category}",
                "--filename", "{category}_{id}.{extension}",
                url
            ]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  下载失败: {e}")
        except FileNotFoundError:
            print("错误: 未找到 gallery-dl，请先安装:")
            print("  pip install gallery-dl")
            sys.exit(1)

    # 统计下载结果
    downloaded = list(backgrounds_dir.glob("*.*"))
    print(f"\n完成！共下载 {len(downloaded)} 张图片")


if __name__ == "__main__":
    main()
