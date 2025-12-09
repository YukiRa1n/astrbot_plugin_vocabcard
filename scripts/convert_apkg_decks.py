# -*- coding: utf-8 -*-
"""
将 new/ 文件夹中的 apkg 文件转换为插件所需的 JSON 格式
支持：成语、古文、无线电法规、日语N1
"""

import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def clean_html(text):
    """移除 HTML 标签"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', str(text))
    clean = ' '.join(clean.split())
    return clean


def extract_apkg_notes(apkg_path):
    """从 apkg 文件中提取 notes 数据"""
    notes = []
    with zipfile.ZipFile(apkg_path, 'r') as z:
        with tempfile.TemporaryDirectory() as tmpdir:
            z.extractall(tmpdir)
            db_path = Path(tmpdir) / "collection.anki2"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT id, flds, tags FROM notes")
                for row in cursor.fetchall():
                    note_id, flds, tags = row
                    fields = flds.split(chr(31))  # Anki 字段分隔符
                    notes.append({
                        "id": note_id,
                        "fields": [clean_html(f) for f in fields],
                        "tags": tags
                    })
                conn.close()
    return notes


def convert_idiom(apkg_path, output_path):
    """
    转换成语词库 (_reversed_card.apkg)
    字段: [成语, 释义]
    """
    print(f"\n=== 转换成语词库 ===")
    notes = extract_apkg_notes(apkg_path)

    words_list = []
    for note in notes:
        fields = note["fields"]
        if len(fields) >= 2:
            idiom = fields[0].strip()
            definition = fields[1].strip()
            if idiom and definition:
                words_list.append({
                    "word": idiom,
                    "definition": definition
                })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, ensure_ascii=False, indent=2)

    print(f"  成功转换: {len(words_list)} 条")
    print(f"  输出文件: {output_path}")
    if words_list:
        print(f"  示例: {words_list[0]['word']} - {words_list[0]['definition'][:30]}...")
    return words_list


def convert_classical(apkg_path, output_path):
    """
    转换古文词库 (_.apkg)
    字段: [句子标题, 原文+翻译]
    """
    print(f"\n=== 转换古文词库 ===")
    notes = extract_apkg_notes(apkg_path)

    words_list = []
    for note in notes:
        fields = note["fields"]
        if len(fields) >= 2:
            # 提取句子编号和关键字
            title = fields[0].strip()
            content = fields[1].strip()

            # 解析标题（如 "第1句 初，"）
            match = re.match(r'第(\d+)句\s*(.+)?', title)
            if match:
                sentence_num = match.group(1)
                keyword = match.group(2) or ""
            else:
                sentence_num = ""
                keyword = title

            if content:
                words_list.append({
                    "sentence_num": sentence_num,
                    "keyword": keyword.strip("，。"),
                    "content": content
                })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, ensure_ascii=False, indent=2)

    print(f"  成功转换: {len(words_list)} 条")
    print(f"  输出文件: {output_path}")
    if words_list:
        print(f"  示例: 第{words_list[0]['sentence_num']}句 - {words_list[0]['content'][:30]}...")
    return words_list


def convert_radio(apkg_path, output_path):
    """
    转换无线电法规词库 (A.apkg)
    字段: [问题, 答案]
    """
    print(f"\n=== 转换无线电法规词库 ===")
    notes = extract_apkg_notes(apkg_path)

    words_list = []
    for note in notes:
        fields = note["fields"]
        tags = note.get("tags", "")
        if len(fields) >= 2:
            question = fields[0].strip()
            answer = fields[1].strip()

            # 提取题号
            match = re.match(r'(LK\d+)\s*(.+)', question)
            if match:
                question_id = match.group(1)
                question_text = match.group(2)
            else:
                question_id = ""
                question_text = question

            if question_text and answer:
                words_list.append({
                    "question_id": question_id,
                    "question": question_text,
                    "answer": answer,
                    "tags": tags.strip()
                })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, ensure_ascii=False, indent=2)

    print(f"  成功转换: {len(words_list)} 条")
    print(f"  输出文件: {output_path}")
    if words_list:
        print(f"  示例: {words_list[0]['question'][:40]}...")
    return words_list


def convert_japanese_n1(apkg_path, output_path):
    """
    转换日语N1词库 (N1.apkg)
    字段: [序号, 等级, 音频, 单词, 读音, 汉字, 词性, 释义, 例句]
    """
    print(f"\n=== 转换日语N1词库 ===")
    notes = extract_apkg_notes(apkg_path)

    words_list = []
    for note in notes:
        fields = note["fields"]
        if len(fields) >= 8:
            # 字段映射
            word = fields[3].strip()  # 单词/假名
            reading = fields[4].strip()  # 读音标记
            kanji = fields[5].strip()  # 汉字写法
            pos = fields[6].strip() if len(fields) > 6 else ""  # 词性
            definition = fields[7].strip() if len(fields) > 7 else ""  # 释义
            example = fields[8].strip() if len(fields) > 8 else ""  # 例句

            # 清理音频标记
            word = re.sub(r'\[sound:[^\]]+\]', '', word).strip()

            if word and definition:
                words_list.append({
                    "word": word,
                    "kanji": kanji,
                    "reading": reading,
                    "pos": pos,
                    "definition": definition,
                    "example": example,
                    "level": "N1"
                })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, ensure_ascii=False, indent=2)

    print(f"  成功转换: {len(words_list)} 条")
    print(f"  输出文件: {output_path}")
    if words_list:
        sample = words_list[0]
        print(f"  示例: {sample['word']} ({sample['kanji']}) - {sample['definition'][:30]}...")
    return words_list


if __name__ == "__main__":
    project_dir = Path(__file__).parent.parent
    new_dir = project_dir / "new"
    languages_dir = project_dir / "languages"

    # 转换各词库
    convert_idiom(
        new_dir / "_reversed_card.apkg",
        languages_dir / "idiom" / "words.json"
    )

    convert_classical(
        new_dir / "_.apkg",
        languages_dir / "classical" / "words.json"
    )

    convert_radio(
        new_dir / "A.apkg",
        languages_dir / "radio" / "words.json"
    )

    convert_japanese_n1(
        new_dir / "N1.apkg",
        languages_dir / "japanese_n1" / "words.json"
    )

    print("\n=== 全部转换完成 ===")
