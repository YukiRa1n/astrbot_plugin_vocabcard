# -*- coding: utf-8 -*-
"""
词库加载器
"""

import json
from pathlib import Path
from typing import List, Dict


class WordLoader:
    """
    统一的词汇数据加载接口

    支持多种数据格式的加载和验证
    """

    def __init__(self, data_path: Path):
        """
        初始化加载器

        Args:
            data_path: 数据文件路径
        """
        self.data_path = data_path

    def load_json(self) -> List[Dict]:
        """
        加载 JSON 格式词库

        Returns:
            词汇数据列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 数据格式无效
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"词库文件不存在: {self.data_path}")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 数据验证
        if not self.validate_data(data):
            raise ValueError(f"词库数据格式无效: {self.data_path}")

        return data

    def validate_data(self, data: List[Dict]) -> bool:
        """
        验证数据格式

        Args:
            data: 待验证的数据

        Returns:
            True 如果数据格式有效
        """
        if not isinstance(data, list) or len(data) == 0:
            return False

        # 抽样验证前 10 条数据
        # 抽样验证前 10 条数据
        # required_fields = {"word"}  # 移除硬编码字段检查，由 Handler 自行处理
        for item in data[:min(10, len(data))]:
            if not isinstance(item, dict):
                return False
            # if not required_fields.issubset(item.keys()):
            #     return False

        return True

    def load_csv(self, delimiter: str = ',') -> List[Dict]:
        """
        加载 CSV 格式词库（预留接口）

        Args:
            delimiter: 分隔符

        Returns:
            词汇数据列表
        """
        # TODO: 实现 CSV 加载逻辑
        raise NotImplementedError("CSV 加载功能尚未实现")
