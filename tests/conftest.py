# -*- coding: utf-8 -*-
"""
vocabcard 插件测试配置
将插件根目录加入 sys.path 以便 core 等绝对导入可用
"""

import sys
from pathlib import Path

_plugin_root = Path(__file__).resolve().parent.parent
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))
