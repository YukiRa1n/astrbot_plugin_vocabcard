# -*- coding: utf-8 -*-
"""
ImageRenderer 单元测试
"""

import asyncio
import os

import pytest
from playwright.async_api import Error as PlaywrightError

from core.image_renderer import ImageRenderer, get_image_renderer


async def test_image_renderer_singleton():
    """测试渲染器单例属性"""
    renderer1 = get_image_renderer()
    renderer2 = get_image_renderer()
    assert renderer1 is renderer2


async def test_image_renderer_render_lifecycle(tmp_path):
    """测试图片渲染完整生命周期及其自净和复用能力"""
    renderer = ImageRenderer(max_pages=2)
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                background: #1a1a2e;
                color: #ffffff;
                font-family: sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            h1 { font-size: 24px; }
        </style>
    </head>
    <body>
        <h1>Test Word Card</h1>
    </body>
    </html>
    """
    output_png = tmp_path / "test_card.png"

    try:
        path = await renderer.render_to_file(
            html_content=html_content,
            output_path=str(output_png),
            width=200,
            height=250,
            scale=2,
        )
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
        assert renderer._active_pages_count == 1
        assert renderer._pool.qsize() == 1

        image_bytes = await renderer.render_to_bytes(
            html_content=html_content, width=200, height=250, scale=2
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0
        assert renderer._active_pages_count == 1
        assert renderer._pool.qsize() == 1
    except (PlaywrightError, RuntimeError) as exc:
        if "Executable doesn't exist" in str(exc) or "is unavailable" in str(exc):
            pytest.skip("Playwright chromium is not installed")
        raise
    finally:
        await renderer.close()


async def test_renderer_concurrency(tmp_path):
    """测试多并发渲染下，页面池能正常工作并不超过 max_pages 上限"""
    renderer = ImageRenderer(max_pages=2)
    html_content = "<html><body>Concurrent Render Test</body></html>"

    try:
        tasks = []
        for i in range(3):
            out_path = tmp_path / f"concurrent_{i}.png"
            tasks.append(
                renderer.render_to_file(html_content, str(out_path), 200, 200, 1)
            )

        results = await asyncio.gather(*tasks)
        for r in results:
            assert os.path.exists(r)

        assert renderer._active_pages_count <= 2
    except (PlaywrightError, RuntimeError) as exc:
        if "Executable doesn't exist" in str(exc) or "is unavailable" in str(exc):
            pytest.skip("Playwright chromium is not installed")
        raise
    finally:
        await renderer.close()
        assert renderer._active_pages_count == 0


@pytest.mark.parametrize("engine", ["chromium", "firefox", "webkit"])
async def test_configured_browser_engine_smoke(tmp_path, engine):
    renderer = ImageRenderer(max_pages=1, engine=engine)
    output = tmp_path / f"{engine}.png"
    try:
        await renderer.render_to_file(
            "<html><body style='margin:0;background:#fff'>engine</body></html>",
            str(output),
            width=200,
            height=120,
            scale=1,
        )
    except (PlaywrightError, RuntimeError) as exc:
        if "Executable doesn't exist" in str(exc) or "is unavailable" in str(exc):
            pytest.skip(f"Playwright {engine} is not installed")
        raise
    finally:
        await renderer.close()

    assert output.exists()
    assert output.stat().st_size > 0
