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
    支持共享词库文件（多卡组共用同一数据源）
    """

    def __init__(self, data_path: Path, shared_words_path: str = None):
        """
        初始化加载器

        Args:
            data_path: 数据文件路径
            shared_words_path: 共享词库文件路径（相对于 languages 目录）
        """
        self.data_path = data_path
        self.shared_words_path = shared_words_path

    def load_json(self) -> List[Dict]:
        """
        加载 JSON 格式词库

        优先使用共享词库路径（如果配置了），否则使用默认路径

        Returns:
            词汇数据列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 数据格式无效
        """
        # 确定实际加载的文件路径
        target_path = self._get_target_path()

        if not target_path.exists():
            raise FileNotFoundError(f"词库文件不存在: {target_path}")

        with open(target_path, 'r', encoding='utf-8') as f:
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

    def _get_target_path(self) -> Path:
        """
        获取实际的词库文件路径

        优先使用共享词库路径，否则使用默认路径

        Returns:
            词库文件路径
        """
        if self.shared_words_path:
            # 共享路径是相对于 languages 目录的
            # data_path 格式: languages/{lang_id}/words.json
            # 所以 data_path.parent.parent 就是 languages 目录
            languages_dir = self.data_path.parent.parent
            shared_path = languages_dir / self.shared_words_path
            if shared_path.exists():
                return shared_path
        return self.data_path

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
