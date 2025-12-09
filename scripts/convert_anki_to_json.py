# -*- coding: utf-8 -*-
"""
将 Anki 数据转换为插件所需的 JSON 格式
"""

import sqlite3
import json
import re
from pathlib import Path

def clean_html(text):
    """移除 HTML 标签"""
    if not text:
        return ""
    # 移除 HTML 标签
    clean = re.sub(r'<[^>]+>', '', text)
    # 移除多余空白
    clean = ' '.join(clean.split())
    return clean

def extract_level_from_tags(tags):
    """从标签中提取 JLPT 等级"""
    if not tags:
        return "JLPT"

    # 查找 N1-N5 标签
    for level in ['N1', 'N2', 'N3', 'N4', 'N5']:
        if level in tags:
            return f"JLPT-{level}"

    return "JLPT"

def convert_anki_to_words(db_path, output_path, limit=None):
    """
    将 Anki 数据库转换为词汇 JSON 格式

    字段映射（基于分析）：
    - 字段 1: 日语单词
    - 字段 2: 重音标记
    - 字段 3: 词性
    - 字段 4: 假名读音
    - 字段 5: 简体中文释义
    - 字段 10: 日语例句
    - 字段 12: 中文例句翻译
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 提取数据（包含标签用于等级判断）
    query = "SELECT id, flds, tags FROM notes"
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    notes = cursor.fetchall()

    words_data = []
    skipped = 0

    for note_id, flds, tags in notes:
        fields = flds.split('\x1f')

        # 确保有足够的字段
        if len(fields) < 13:
            skipped += 1
            continue

        # 提取关键字段
        word = clean_html(fields[1])  # 日语单词
        accent = clean_html(fields[2])  # 重音标记
        pos = clean_html(fields[3])  # 词性
        kana = clean_html(fields[4])  # 假名读音
        definition_cn = clean_html(fields[5])  # 中文释义
        example_ja = clean_html(fields[10])  # 日语例句
        example_cn = clean_html(fields[12])  # 中文例句翻译

        # 跳过空数据
        if not word or not kana or not definition_cn:
            skipped += 1
            continue

        # 提取等级
        level = extract_level_from_tags(tags)

        # 构建词条
        word_entry = {
            "word": word,
            "kana": kana,
            "accent": accent if accent else "",
            "pos": pos if pos else "名",
            "definition_cn": definition_cn,
            "example_ja": example_ja if example_ja else "",
            "example_cn": example_cn if example_cn else "",
            "level": level
        }

        words_data.append(word_entry)

    conn.close()

    # 保存为 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)

    print(f"转换完成！")
    print(f"  - 成功转换: {len(words_data)} 条")
    print(f"  - 跳过: {skipped} 条")
    print(f"  - 输出文件: {output_path}")

    return words_data

if __name__ == "__main__":
    # 设置路径
    project_dir = Path(__file__).parent.parent
    db_path = project_dir / "temp_repo" / "anki-jlpt-decks" / "extracted" / "collection.anki21"
    output_path = project_dir / "data" / "words_ja.json"

    print(f"数据库路径: {db_path}")
    print(f"输出路径: {output_path}")
    print()

    if db_path.exists():
        # 转换所有数据
        words_data = convert_anki_to_words(db_path, output_path)

        # 显示前3条示例
        print("\n=== 前 3 条数据示例 ===")
        for i, word in enumerate(words_data[:3], 1):
            print(f"\n{i}. {word['word']} ({word['kana']})")
            print(f"   词性: {word['pos']}")
            print(f"   释义: {word['definition_cn']}")
            print(f"   例句: {word['example_ja']}")
            print(f"   翻译: {word['example_cn']}")
            print(f"   等级: {word['level']}")
    else:
        print(f"错误: 数据库文件不存在: {db_path}")
