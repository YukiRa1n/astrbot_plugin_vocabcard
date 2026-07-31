# -*- coding: utf-8 -*-
"""
ImageRenderer 单元测试
"""

import os
import pytest
import asyncio
from playwright.async_api import Error as PlaywrightError

from core.image_renderer import ImageRenderer, get_image_renderer

# 使用 pytest-asyncio 运行异步测试
pytestmark = pytest.mark.asyncio


async def test_image_renderer_singleton():
    """测试渲染器单例属性"""
    renderer1 = get_image_renderer()
    renderer2 = get_image_renderer()
    assert renderer1 is renderer2


async def test_image_renderer_render_lifecycle(tmp_path):
    """测试图片渲染完整生命周期及其自净和复用能力"""
    renderer = get_image_renderer()

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

    # 第一次渲染到文件
    path = await renderer.render_to_file(
        html_content=html_content,
        output_path=str(output_png),
        width=200,
        height=250,
        scale=2,
    )

    assert os.path.exists(path)
    assert os.path.getsize(path) > 0

    # 验证活跃页面数量在归还后是否正确（由于归还进入池中，它应该等于 1）
    assert renderer._active_pages_count == 1
    assert renderer._pool.qsize() == 1

    # 第二次渲染到字节 (验证复用同一页面而不用 launch)
    image_bytes = await renderer.render_to_bytes(
        html_content=html_content, width=200, height=250, scale=2
    )

    assert isinstance(image_bytes, bytes)
    assert len(image_bytes) > 0
    assert renderer._active_pages_count == 1
    assert renderer._pool.qsize() == 1


async def test_renderer_concurrency(tmp_path):
    """测试多并发渲染下，页面池能正常工作并不超过 max_pages 上限"""
    renderer = get_image_renderer()

    html_content = "<html><body>Concurrent Render Test</body></html>"

    # 设置上限为 2
    renderer.max_pages = 2

    # 并发 3 个渲染请求，必然会有 1 个阻塞等待
    tasks = []
    for i in range(3):
        out_path = tmp_path / f"concurrent_{i}.png"
        tasks.append(renderer.render_to_file(html_content, str(out_path), 200, 200, 1))

    results = await asyncio.gather(*tasks)

    for r in results:
        assert os.path.exists(r)

    # 虽然并发了 3 个渲染，但页面总数不能超过 max_pages
    assert renderer._active_pages_count <= 2

    # 清理 pool
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
    except PlaywrightError as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip(f"Playwright {engine} is not installed")
        raise
    finally:
        await renderer.close()

    assert output.exists()
    assert output.stat().st_size > 0
