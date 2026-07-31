# -*- coding: utf-8 -*-
"""
卡片渲染器
"""

import html as _html
from pathlib import Path
from typing import Dict

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class CardRenderer:
    """
    卡片渲染器

    使用 Jinja2 模板引擎渲染卡片 HTML
    如果 Jinja2 不可用，回退到简单的字符串替换
    """

    def __init__(self, templates_dir: Path):
        """
        初始化渲染器

        Args:
            templates_dir: 模板目录路径
        """
        self.templates_dir = templates_dir
        self.use_jinja2 = JINJA2_AVAILABLE

        if self.use_jinja2:
            self.env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            self._register_filters()

    def render(self, template_name: str, variables: Dict) -> str:
        """
        渲染模板

        Args:
            template_name: 模板文件名
            variables: 模板变量字典

        Returns:
            渲染后的 HTML 字符串
        """
        if self.use_jinja2:
            return self._render_jinja2(template_name, variables)
        else:
            return self._render_simple(template_name, variables)

    def _render_jinja2(self, template_name: str, variables: Dict) -> str:
        """使用 Jinja2 渲染"""
        template = self.env.get_template(template_name)
        return template.render(**variables)

    def _render_simple(self, template_name: str, variables: Dict) -> str:
        """简单字符串替换渲染（回退方案）"""
        import re as _re

        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        # 简单处理 {% if var %}...{% endif %}：var 为真时保留块内容
        def _if_block(match: _re.Match) -> str:
            var_name = match.group(1).strip()
            content = match.group(2)
            if variables.get(var_name):
                return content
            return ""

        html = _re.sub(
            r"{%\s*if\s+(\w+)\s*%}(.*?){%\s*endif\s*%}",
            _if_block,
            template,
            flags=_re.DOTALL,
        )

        # 简单的占位符替换
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            html = html.replace(placeholder, _html.escape(str(value)))

        return html

    def _register_filters(self):
        """注册自定义 Jinja2 过滤器"""
        if not self.use_jinja2:
            return

        self.env.filters["upper"] = lambda x: x.upper() if x else ""
        self.env.filters["truncate"] = lambda x, n=255: (x[:n] + "..." if x and len(x) > n else (x or ""))
        self.env.filters["default"] = lambda x, d: x if x else d
