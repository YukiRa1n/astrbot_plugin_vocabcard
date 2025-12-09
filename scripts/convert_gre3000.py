# -*- coding: utf-8 -*-
"""
将 GRE3000 数据转换为插件所需的 JSON 格式
合并 word_json.txt (考法精析) 和 mnemo_json.txt (助记) 两个数据源
"""

import json
import re
from pathlib import Path


def clean_html(text):
    """移除 HTML 标签和多余空白"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', str(text))
    clean = ' '.join(clean.split())
    return clean


def load_json_file(file_path):
    """加载 JSON 文件（处理单行 JSON 格式）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        return json.loads(content)


def convert_gre3000(gre_dir, output_path):
    """
    转换 GRE3000 数据

    数据结构：
    - word_json.txt: 考法精析，包含 usages (释义、例句、同义词、反义词)
    - mnemo_json.txt: 助记，包含词根分析、助记内容、同根词
    """
    word_file = gre_dir / "input" / "word_json.txt"
    mnemo_file = gre_dir / "input" / "mnemo_json.txt"

    print(f"加载考法精析数据: {word_file}")
    word_data = load_json_file(word_file)

    print(f"加载助记数据: {mnemo_file}")
    mnemo_data = load_json_file(mnemo_file)

    print(f"考法精析词条数: {len(word_data)}")
    print(f"助记词条数: {len(mnemo_data)}")

    words_list = []

    # 以考法精析为主，合并助记数据
    for word_key, word_info in word_data.items():
        # 基本信息
        word = word_key
        phonetic = word_info.get("phon", "")

        # 提取释义（从 usages 中）
        definitions = []
        examples = []
        synonyms = []
        antonyms = []

        usages = word_info.get("usages", [])
        for usage in usages:
            # 提取基本释义
            for basic in usage.get("basic", []):
                exp = basic.get("exp", "")
                if exp:
                    # 清理格式，提取中文释义
                    clean_exp = clean_html(exp)
                    definitions.append(clean_exp)

            # 提取例句
            for ex in usage.get("examples", []):
                if ex:
                    examples.append(clean_html(ex))

            # 提取同义词
            for syn in usage.get("syns", []):
                if syn:
                    synonyms.append(clean_html(syn))

            # 提取反义词
            for ant in usage.get("ants", []):
                if ant:
                    antonyms.append(clean_html(ant))

        # 合并助记数据
        mnemo_info = mnemo_data.get(word, {})
        mnemo_content = mnemo_info.get("content", [])  # 词根分析和助记
        root = mnemo_info.get("root", "")  # 词根
        root_exp = mnemo_info.get("root_exp", [])  # 词根解释
        cognates = mnemo_info.get("cognates", "")  # 同根词

        # 构建词条
        word_entry = {
            "word": word,
            "phonetic": phonetic,
            "definitions": definitions[:3] if definitions else [""],  # 最多3个释义
            "example": examples[0] if examples else "",
            "synonyms": ", ".join(synonyms[:5]) if synonyms else "",  # 最多5个同义词
            "antonyms": ", ".join(antonyms[:3]) if antonyms else "",  # 最多3个反义词
            "mnemo": "\n".join(mnemo_content) if mnemo_content else "",  # 助记内容
            "root": root,
            "root_explanation": root_exp[0] if root_exp else "",
            "cognates": cognates
        }

        # 验证必要字段
        if word and definitions:
            words_list.append(word_entry)

    # 保存为 JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, ensure_ascii=False, indent=2)

    print(f"\n转换完成！")
    print(f"  - 成功转换: {len(words_list)} 条")
    print(f"  - 输出文件: {output_path}")

    # 显示示例
    if words_list:
        print("\n=== 示例数据 ===")
        sample = words_list[0]
        print(f"单词: {sample['word']}")
        print(f"音标: {sample['phonetic']}")
        print(f"释义: {sample['definitions'][0][:80]}...")
        print(f"助记: {sample['mnemo'][:80]}..." if sample['mnemo'] else "助记: 无")
        print(f"同根词: {sample['cognates'][:50]}..." if sample['cognates'] else "同根词: 无")

    return words_list


if __name__ == "__main__":
    project_dir = Path(__file__).parent.parent
    gre_dir = project_dir / "new" / "GRE3000"
    output_path = project_dir / "languages" / "gre" / "words.json"

    if gre_dir.exists():
        convert_gre3000(gre_dir, output_path)
    else:
        print(f"错误: GRE3000 目录不存在: {gre_dir}")
