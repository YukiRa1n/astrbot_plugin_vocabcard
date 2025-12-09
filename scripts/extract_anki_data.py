# -*- coding: utf-8 -*-
"""
从 Anki 卡组中提取日语词汇数据并转换为 JSON 格式
"""

import sqlite3
import json
import re
from pathlib import Path

def extract_anki_data(db_path, output_path, limit=None):
    """
    从 Anki 数据库提取词汇数据

    Args:
        db_path: Anki 数据库文件路径
        output_path: 输出 JSON 文件路径
        limit: 限制提取的词汇数量（用于测试）
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查看表结构
    print("=== 数据库表列表 ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")

    # 查看 notes 表结构
    print("\n=== notes 表结构 ===")
    cursor.execute("PRAGMA table_info(notes)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]}: {col[2]}")

    # 提取前几条数据查看格式（不打印，避免编码问题）
    print("\n=== 提取前 5 条数据用于分析 ===")

    # 统计总数
    cursor.execute("SELECT COUNT(*) FROM notes")
    total = cursor.fetchone()[0]
    print(f"\n=== 总词汇数: {total} ===")

    # 提取所有数据
    print("\n=== 开始提取数据 ===")
    query = "SELECT id, flds FROM notes"
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    notes = cursor.fetchall()

    words_data = []
    for note_id, flds in notes:
        fields = flds.split('\x1f')

        # 清理 HTML 标签
        clean_fields = []
        for field in fields:
            # 移除 HTML 标签
            clean = re.sub(r'<[^>]+>', '', field)
            # 移除多余空白
            clean = ' '.join(clean.split())
            clean_fields.append(clean)

        # 根据字段数量判断数据格式
        # 需要根据实际数据调整字段映射
        if len(clean_fields) >= 3:
            word_entry = {
                "id": note_id,
                "fields": clean_fields,
                "field_count": len(clean_fields)
            }
            words_data.append(word_entry)

    # 保存原始数据用于分析
    analysis_path = output_path.parent / "anki_raw_analysis.json"
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(words_data[:50], f, ensure_ascii=False, indent=2)

    print(f"\n已提取 {len(words_data)} 条数据")
    print(f"原始数据分析已保存到: {analysis_path}")

    conn.close()
    return words_data

if __name__ == "__main__":
    # 设置路径
    project_dir = Path(__file__).parent.parent
    db_path = project_dir / "temp_repo" / "anki-jlpt-decks" / "extracted" / "collection.anki21"
    output_dir = project_dir / "data"
    output_dir.mkdir(exist_ok=True)

    # 提取数据（先提取 100 条用于分析）
    print(f"数据库路径: {db_path}")
    print(f"输出目录: {output_dir}")

    if db_path.exists():
        words_data = extract_anki_data(
            db_path,
            output_dir / "words_ja.json",
            limit=100  # 先提取 100 条分析格式
        )
        print("\n✅ 数据提取完成！")
        print("请查看 data/anki_raw_analysis.json 了解数据格式")
    else:
        print(f"❌ 数据库文件不存在: {db_path}")
