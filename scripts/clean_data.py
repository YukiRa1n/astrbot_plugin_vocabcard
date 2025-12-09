#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单词数据清洗脚本
将原始 txt 文件转换为规范化的 JSON 格式

输入格式:
    单词&[音标]&词性+释义&例句

输出格式 (words.json):
[
  {
    "word": "abnormal",
    "phonetic": "/æbˈnɔːm(ə)l/",
    "pos": "adj.",
    "definition_cn": "反常的；异常的；变态的；不规则的",
    "example": "His abnormal behavior made everyone in the room worried."
  }
]
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional


def parse_line(line: str, line_num: int) -> Optional[Dict]:
    """解析单行单词数据"""
    line = line.strip()

    if not line:
        return None

    # 必须包含 &
    if '&' not in line:
        return None

    try:
        # 分割各字段
        fields = line.split('&')
        if len(fields) < 4:
            return None

        word = fields[0].strip()
        phonetic_raw = fields[1].strip()
        pos_definition = fields[2].strip()
        example = fields[3].strip() if len(fields) > 3 else ""

        # 单词必须以英文字母开头（过滤中文标题）
        if not word or not word[0].isascii() or not word[0].isalpha():
            return None

        # 解析音标 - 去掉方括号，添加斜杠
        phonetic = phonetic_raw.strip('[]')
        if phonetic:
            phonetic = f"/{phonetic}/"

        # 解析词性和释义
        pos = ""
        definition_cn = pos_definition

        # 尝试提取词性 (如 adj. n. v. 等)
        pos_match = re.match(r'^([a-z]+\.)\s*(.+)', pos_definition)
        if pos_match:
            pos = pos_match.group(1)
            definition_cn = pos_match.group(2)

        return {
            "word": word,
            "phonetic": phonetic,
            "pos": pos,
            "definition_cn": definition_cn,
            "example": example,
            "_seq": line_num  # 用于保持顺序
        }

    except Exception as e:
        print(f"解析行失败: {line[:50]}... 错误: {e}")
        return None


def clean_vocabulary_file(input_path: Path) -> List[Dict]:
    """清洗单个词汇文件"""
    words = []

    # 尝试多种编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
    content = None

    for encoding in encodings:
        try:
            content = input_path.read_text(encoding=encoding)
            print(f"  使用编码 {encoding} 成功读取")
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError(f"无法读取文件: {input_path}")

    lines = content.splitlines()
    print(f"  共读取 {len(lines)} 行")

    for i, line in enumerate(lines):
        result = parse_line(line, i)
        if result:
            words.append(result)

    print(f"  成功解析 {len(words)} 个单词")
    return words


def merge_and_deduplicate(all_words: List[Dict]) -> List[Dict]:
    """合并并去重"""
    # 按序号排序
    all_words.sort(key=lambda x: x.get('_seq', 0))

    # 去重
    seen = set()
    unique_words = []
    for w in all_words:
        if w['word'].lower() not in seen:
            seen.add(w['word'].lower())
            # 移除临时字段
            w.pop('_seq', None)
            unique_words.append(w)

    return unique_words


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    script_dir = Path(__file__).parent
    plugin_dir = script_dir.parent
    project_dir = plugin_dir.parent

    # 输入文件
    input_files = [
        project_dir / "六级分类99.txt",
        project_dir / "99.六级核心.txt"
    ]

    # 输出目录
    output_dir = plugin_dir / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_words = []

    for input_file in input_files:
        if input_file.exists():
            print(f"\n处理文件: {input_file.name}")
            print("-" * 50)

            try:
                words = clean_vocabulary_file(input_file)
                all_words.extend(words)
            except Exception as e:
                print(f"  处理失败: {e}")
        else:
            print(f"文件不存在: {input_file}")

    if all_words:
        # 合并去重
        unique_words = merge_and_deduplicate(all_words)
        print(f"\n合并去重后: {len(unique_words)} 个单词")

        # 保存
        output_path = output_dir / "words.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unique_words, f, ensure_ascii=False, indent=2)

        print(f"已保存到: {output_path}")

        # 显示前5个单词作为示例
        print("\n前5个单词示例:")
        for w in unique_words[:5]:
            print(f"  {w['word']} {w['phonetic']} - {w['definition_cn'][:30]}...")
    else:
        print("\n未找到有效单词数据")


if __name__ == "__main__":
    main()
