# -*- coding: utf-8 -*-
"""
图片渲染器 - 使用 Playwright 将 HTML 转换为图片

纯 pip 依赖，首次运行自动安装 Chromium 浏览器。
"""

import subprocess
import tempfile
import logging
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 浏览器安装标记
_browser_installed = False


async def _ensure_browser_installed():
    """确保 Chromium 浏览器已安装"""
    global _browser_installed
    if _browser_installed:
        return

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        _browser_installed = True
        logger.info("Chromium 浏览器已就绪")
    except Exception:
        logger.info("首次运行，正在安装 Chromium 浏览器...")
        try:
            process = await asyncio.create_subprocess_exec(
                "playwright", "install", "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            _browser_installed = True
            logger.info("Chromium 浏览器安装完成")
        except Exception as e:
            logger.error(f"安装 Chromium 失败: {e}")
            raise RuntimeError(
                "无法安装 Chromium 浏览器，请手动运行: playwright install chromium"
            )


class ImageRenderer:
    """
    图片渲染器

    使用 Playwright (Chromium) 将 HTML 渲染为 PNG 图片。
    纯 pip 依赖，首次运行自动安装浏览器。
    """

    def __init__(self):
        """初始化渲染器"""
        logger.info("ImageRenderer 初始化完成 (Playwright Async)")

    async def render_to_file(
        self,
        html_content: str,
        output_path: str,
        width: int = 432,
        height: int = 540,
        scale: int = 4
    ) -> str:
        """
        将 HTML 渲染为 PNG 图片文件

        Args:
            html_content: HTML 内容字符串
            output_path: 输出图片路径
            width: 卡片宽度 (像素)
            height: 卡片高度 (像素)
            scale: 缩放倍数 (4 = 4K 清晰度)

        Returns:
            输出图片的绝对路径
        """
        await _ensure_browser_installed()
        from playwright.async_api import async_playwright

        # 写入临时 HTML 文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False, encoding='utf-8'
        ) as f:
            f.write(html_content)
            temp_html = Path(f.name)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale
                )
                await page.goto(temp_html.as_uri())

                # 等待背景图加载
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass
                await page.wait_for_timeout(2000)

                # 截图
                await page.screenshot(path=output_path, type="png", scale="device")
                await browser.close()

            logger.info(f"图片已生成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"渲染图片失败: {e}")
            raise
        finally:
            if temp_html.exists():
                temp_html.unlink()

    async def render_to_bytes(
        self,
        html_content: str,
        width: int = 432,
        height: int = 540,
        scale: int = 4
    ) -> bytes:
        """
        将 HTML 渲染为 PNG 图片字节

        Args:
            html_content: HTML 内容字符串
            width: 卡片宽度 (像素)
            height: 卡片高度 (像素)
            scale: 缩放倍数 (4 = 4K 清晰度)

        Returns:
            PNG 图片字节数据
        """
        await _ensure_browser_installed()
        from playwright.async_api import async_playwright

        # 写入临时 HTML 文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False, encoding='utf-8'
        ) as f:
            f.write(html_content)
            temp_html = Path(f.name)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale
                )
                await page.goto(temp_html.as_uri())

                # 等待背景图加载
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass
                await page.wait_for_timeout(2000)

                # 截图返回字节
                image_bytes = await page.screenshot(type="png", scale="device")
                await browser.close()

            return image_bytes
        except Exception as e:
            logger.error(f"渲染图片失败: {e}")
            raise
        finally:
            if temp_html.exists():
                temp_html.unlink()


# 全局单例实例（延迟初始化）
_renderer_instance: Optional[ImageRenderer] = None


def get_image_renderer() -> ImageRenderer:
    """获取全局图片渲染器实例（单例模式）"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = ImageRenderer()
    return _renderer_instance
