# -*- coding: utf-8 -*-
"""
图片渲染器 - 使用 Playwright 将 HTML 转换为图片 (优化版)

支持基于 asyncio.Queue 的浏览器页面复用池 (Page Pool)，防进程崩溃自愈与内存泄露加固。
支持在热重载或事件循环(asyncio loop)改变时的自动重连自愈。
"""

import asyncio
import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_browser_install_locks: dict[str, tuple[object, asyncio.Lock]] = {}
_browser_install_lock = asyncio.Lock()

# 浏览器安装标记
_installed_browsers: set[str] = set()
_browser_installed = False


def _get_install_lock(engine: str) -> asyncio.Lock:
    """Return an install lock bound to the active event loop."""
    loop = asyncio.get_running_loop()
    entry = _browser_install_locks.get(engine)
    if entry is None or entry[0] is not loop:
        lock = asyncio.Lock()
        _browser_install_locks[engine] = (loop, lock)
        return lock
    return entry[1]


async def _run_playwright_install(
    engine: str, launch_failure: Optional[BaseException] = None
) -> None:
    """Install the requested Playwright browser with a bounded timeout."""
    global _browser_installed
    command = [sys.executable, "-m", "playwright", "install", engine]
    if engine == "chromium":
        command.append("--only-shell")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if process.returncode is None:
            try:
                process.kill()
            except Exception:
                pass
        try:
            await process.wait()
        except Exception:
            pass
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.error("安装 Playwright %s 超时（300s），终止安装进程", engine)
        raise RuntimeError(f"安装 Playwright {engine} 超时") from (
            launch_failure or exc
        )
    if process.returncode != 0:
        detail = stderr.decode(errors="replace") or stdout.decode(errors="replace")
        raise RuntimeError(
            f"Cannot install Playwright {engine}: {detail.strip()}"
        ) from launch_failure

    _installed_browsers.add(engine)
    _browser_installed = engine == "chromium" or _browser_installed
    logger.info("Playwright %s browser installed", engine)


async def _ensure_browser_installed(
    engine: str = "chromium",
    *,
    allow_install: bool = False,
):
    """确保所选 Playwright 浏览器已安装。"""
    global _browser_installed
    if engine in _installed_browsers:
        return

    async with _get_install_lock(engine):
        if engine in _installed_browsers:
            return
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await getattr(p, engine).launch(headless=True)
                await browser.close()
            _installed_browsers.add(engine)
            _browser_installed = engine == "chromium" or _browser_installed
            logger.info("Playwright %s browser ready", engine)
            return
        except Exception as exc:
            if not allow_install:
                raise RuntimeError(
                    f"Playwright {engine} is unavailable. "
                    f"Install it during deployment with: {sys.executable} -m playwright install {engine}"
                ) from exc
            launch_failure = exc
            logger.info("Installing Playwright %s browser...", engine)

        await _run_playwright_install(engine, launch_failure)


class ImageRenderer:
    """
    图片渲染器
    基于 Playwright Chromium 页面池的高效无内存泄漏渲染器。
    """

    def __init__(
        self,
        max_pages: int = 2,
        engine: str = "chromium",
        cdp_url: str = "",
        auto_install_browser: bool = False,
    ):
        if engine not in {"chromium", "firefox", "webkit"}:
            raise ValueError(f"不支持的浏览器引擎: {engine}")
        if cdp_url and engine != "chromium":
            raise ValueError("CDP 后端仅支持 Chromium")
        self.max_pages = max(1, max_pages)
        self.engine = engine
        self.cdp_url = cdp_url.strip()
        self.auto_install_browser = bool(auto_install_browser)
        self._playwright = None
        self._browser = None
        self._owns_browser = True
        self._pool = asyncio.Queue()
        self._page_available = asyncio.Event()
        self._page_scales = {}
        self._owned_contexts = set()
        self._active_pages_count = 0
        self._lock = asyncio.Lock()
        self._loop = None
        logger.info(
            "ImageRenderer 页面池初始化完成 (引擎: %s, 最大页面上限: %s)",
            engine,
            self.max_pages,
        )

    @staticmethod
    async def _best_effort_close(obj, method_name: str) -> None:
        try:
            fn = getattr(obj, method_name, None)
            if fn is not None:
                result = fn()
                if asyncio.iscoroutine(result):
                    try:
                        await asyncio.wait_for(result, timeout=2.0)
                    except Exception:
                        pass
        except Exception:
            pass

    async def _ensure_loop(self) -> None:
        """Reset loop-bound primitives before acquiring locks if the loop changed."""
        current_loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = current_loop
            return
        if self._loop is current_loop:
            return
        self._loop = current_loop
        self._lock = asyncio.Lock()
        await self._force_cleanup_loop_resources()

    async def _force_cleanup_loop_resources(self):
        """在事件循环改变时强行清理旧事件循环残留的僵尸连接"""
        logger.info("强行重置已被销毁的事件循环残留的 Playwright 上下文")
        browser = self._browser
        playwright = self._playwright
        owns = self._owns_browser
        contexts = tuple(self._owned_contexts)
        self._browser = None
        self._playwright = None
        self._pool = asyncio.Queue()
        self._page_available = asyncio.Event()
        self._page_scales = {}
        self._owned_contexts.clear()
        self._active_pages_count = 0

        if browser is not None and owns:
            await self._best_effort_close(browser, "close")
        elif not owns:
            for ctx in contexts:
                await self._best_effort_close(ctx, "close")
        if playwright is not None:
            await self._best_effort_close(playwright, "stop")

    @staticmethod
    def _launch_options(engine: str) -> dict:
        options = {"headless": True}
        if engine == "chromium":
            options["args"] = [
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=512",
            ]
        return options

    async def _init_browser(self):
        """初始化 Playwright 和无头浏览器实例 (支持事件循环改变后的自愈)"""
        global _browser_installed
        current_loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = current_loop
        elif self._loop is not current_loop:
            await self._force_cleanup_loop_resources()
            self._loop = current_loop

        if self._browser is not None and self._browser.is_connected():
            return

        if self._browser is not None and not self._browser.is_connected():
            logger.warning("检测到浏览器断连，正在重新初始化...")
            if self._owns_browser:
                await self._best_effort_close(self._browser, "close")
            else:
                for ctx in tuple(self._owned_contexts):
                    await self._best_effort_close(ctx, "close")
            self._browser = None
            self._pool = asyncio.Queue()
            self._page_scales = {}
            self._owned_contexts.clear()
            self._active_pages_count = 0
            self._page_available.set()
            if self._playwright is not None:
                await self._best_effort_close(self._playwright, "stop")
                self._playwright = None

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        try:
            if self.cdp_url:
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self.cdp_url
                )
                self._owns_browser = False
                logger.info("已连接共享 Chromium CDP: %s", self.cdp_url)
            else:
                browser_type = getattr(self._playwright, self.engine)
                options = self._launch_options(self.engine)
                try:
                    self._browser = await browser_type.launch(**options)
                except Exception as exc:
                    if not self.auto_install_browser:
                        raise RuntimeError(
                            f"Playwright {self.engine} is unavailable. "
                            f"Install it during deployment with: {sys.executable} -m playwright install {self.engine}"
                        ) from exc
                    async with _get_install_lock(self.engine):
                        await _run_playwright_install(self.engine, exc)
                    self._browser = await browser_type.launch(**options)
                self._owns_browser = True
                _installed_browsers.add(self.engine)
                _browser_installed = self.engine == "chromium" or _browser_installed
                logger.info("Playwright %s 浏览器进程启动成功", self.engine)
        except BaseException:
            if self._playwright is not None:
                await self._best_effort_close(self._playwright, "stop")
            self._playwright = None
            self._browser = None
            raise

    async def _create_page(self, width: int, height: int, scale: int):
        context = await self._browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=scale,
        )
        try:
            page = await context.new_page()
        except BaseException:
            await self._best_effort_close(context, "close")
            raise
        self._owned_contexts.add(context)
        self._page_scales[page] = scale
        return page

    async def _dispose_page(self, page):
        self._page_scales.pop(page, None)
        ctx = getattr(page, "context", None)
        if ctx is not None:
            self._owned_contexts.discard(ctx)
        try:
            if ctx is not None:
                await ctx.close()
            else:
                await page.close()
        except Exception:
            try:
                await page.close()
            except Exception:
                pass

    async def _discard_leased_page(self, page) -> None:
        """Dispose a leased page and release its concurrency slot."""
        if page is None:
            return
        try:
            await self._dispose_page(page)
        finally:
            async with self._lock:
                self._active_pages_count = max(0, self._active_pages_count - 1)
                self._page_available.set()

    async def _acquire_page(
        self, width: int, height: int, scale: int, wait_timeout: float = 30.0
    ):
        """从页面池中获取一个可用的 Page 实例（自愈机制）"""
        await self._ensure_loop()
        deadline = asyncio.get_running_loop().time() + max(0.001, wait_timeout)

        while True:
            async with self._lock:
                await self._init_browser()

                while not self._pool.empty():
                    page = self._pool.get_nowait()
                    try:
                        if page.is_closed():
                            logger.warning("从池中获取到已关闭的页面，予以丢弃")
                            self._active_pages_count = max(
                                0, self._active_pages_count - 1
                            )
                            self._page_scales.pop(page, None)
                            continue
                        if self._page_scales.get(page) != scale:
                            self._active_pages_count = max(
                                0, self._active_pages_count - 1
                            )
                            await self._dispose_page(page)
                            continue
                        await page.set_viewport_size({"width": width, "height": height})
                        return page
                    except BaseException as exc:
                        self._active_pages_count = max(0, self._active_pages_count - 1)
                        await self._dispose_page(page)
                        self._page_available.set()
                        if isinstance(exc, asyncio.CancelledError):
                            raise
                        logger.warning(f"获取池中页面失败，自动丢弃自愈: {exc}")

                if self._active_pages_count < self.max_pages:
                    logger.info(
                        f"正在创建新的 Browser Page (当前活动页面数: {self._active_pages_count + 1})"
                    )
                    page = await self._create_page(width, height, scale)
                    self._active_pages_count += 1
                    return page

                self._page_available.clear()

            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise RuntimeError("Timed out waiting for available browser page")
            logger.debug("浏览器页面池已满且全部忙碌，正在阻塞等待空闲页面...")
            try:
                await asyncio.wait_for(self._page_available.wait(), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    "Timed out waiting for available browser page"
                ) from exc

    async def _release_page(self, page):
        """归还或销毁 Page 实例 (DOM 自净化与防泄露)"""
        if page is None:
            return

        try:
            if page.is_closed():
                await self._discard_leased_page(page)
                return

            await page.goto("about:blank")
            async with self._lock:
                self._pool.put_nowait(page)
                self._page_available.set()
            logger.debug("页面已成功清空 DOM 并归还到池中")
        except asyncio.CancelledError:
            await self._discard_leased_page(page)
            raise
        except Exception as e:
            logger.warning(f"归还页面失败，强制销毁: {e}")
            await self._discard_leased_page(page)

    async def _render_html(
        self,
        html_content: str,
        width: int,
        height: int,
        scale: int,
        network_idle_timeout_ms: int,
        output_path: Optional[str] = None,
    ):
        page = None
        idle_ms = max(1000, min(60000, int(network_idle_timeout_ms or 8000)))
        temp_dir = tempfile.gettempdir()
        temp_html_path = os.path.join(temp_dir, f"vocab_{uuid.uuid4().hex}.html")
        fd = os.open(temp_html_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            page = await self._acquire_page(width, height, scale)
            await asyncio.wait_for(
                page.goto(Path(temp_html_path).as_uri()), timeout=60.0
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=idle_ms)
            except Exception as e:
                logger.debug(f"背景图加载网络空闲等待超时: {e}")

            await page.wait_for_timeout(150)

            if output_path is not None:
                await page.screenshot(path=output_path, type="png", scale="device")
                logger.info(f"卡片图片已生成: {output_path}")
                result = output_path
            else:
                result = await page.screenshot(type="png", scale="device")

            released, page = page, None
            await self._release_page(released)
            return result
        except BaseException as e:
            if not isinstance(e, asyncio.CancelledError):
                logger.error(f"渲染图片失败: {e}")
            if page is not None:
                await self._discard_leased_page(page)
            raise
        finally:
            try:
                if os.path.exists(temp_html_path):
                    os.remove(temp_html_path)
            except OSError:
                pass

    async def render_to_file(
        self,
        html_content: str,
        output_path: str,
        width: int = 432,
        height: int = 540,
        scale: int = 4,
        network_idle_timeout_ms: int = 8000,
    ) -> str:
        """将 HTML 渲染为 PNG 图片文件 (基于 Page 复用池)"""
        return await self._render_html(
            html_content=html_content,
            width=width,
            height=height,
            scale=scale,
            network_idle_timeout_ms=network_idle_timeout_ms,
            output_path=output_path,
        )

    async def render_to_bytes(
        self,
        html_content: str,
        width: int = 432,
        height: int = 540,
        scale: int = 4,
        network_idle_timeout_ms: int = 8000,
    ) -> bytes:
        """将 HTML 渲染为 PNG 图片字节 (基于 Page 复用池)"""
        return await self._render_html(
            html_content=html_content,
            width=width,
            height=height,
            scale=scale,
            network_idle_timeout_ms=network_idle_timeout_ms,
            output_path=None,
        )

    async def close(self):
        """关闭所有浏览器资源，释放池"""
        await self._ensure_loop()
        async with self._lock:
            while not self._pool.empty():
                page = self._pool.get_nowait()
                try:
                    await self._dispose_page(page)
                except Exception:
                    pass

            browser = self._browser
            playwright = self._playwright
            owns = self._owns_browser
            contexts = tuple(self._owned_contexts)
            self._browser = None
            self._playwright = None
            self._active_pages_count = 0
            self._page_scales = {}
            self._owned_contexts.clear()
            self._page_available.set()
            self._loop = None

        if browser is not None and owns:
            await self._best_effort_close(browser, "close")
        elif not owns:
            for ctx in contexts:
                await self._best_effort_close(ctx, "close")
        if playwright is not None:
            await self._best_effort_close(playwright, "stop")
        logger.info("ImageRenderer 浏览器资源和池已完全释放")


# 全局单例实例
_renderer_instance: Optional[ImageRenderer] = None


def get_image_renderer() -> ImageRenderer:
    """获取全局图片渲染器单例（延迟初始化）"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = ImageRenderer(max_pages=2)
    return _renderer_instance
