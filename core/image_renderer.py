# -*- coding: utf-8 -*-
"""
图片渲染器 - 使用 Playwright 将 HTML 转换为图片 (优化版)

支持基于 asyncio.Queue 的浏览器页面复用池 (Page Pool)，防进程崩溃自愈与内存泄露加固。
支持在热重载或事件循环(asyncio loop)改变时的自动重连自愈。
"""

import logging
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_browser_install_locks = {
    engine: asyncio.Lock() for engine in ("chromium", "firefox", "webkit")
}
_browser_install_lock = _browser_install_locks["chromium"]

# 浏览器安装标记
_installed_browsers: set[str] = set()
_browser_installed = False


async def _ensure_browser_installed(
    engine: str = "chromium",
    *,
    allow_install: bool = False,
):
    """确保所选 Playwright 浏览器已安装。"""
    global _browser_installed
    if engine in _installed_browsers:
        return

    lock = _browser_install_locks[engine]
    async with lock:
        if engine in _installed_browsers:
            return
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                executable = Path(getattr(p, engine).executable_path)
                if not executable.is_file():
                    raise FileNotFoundError(executable)
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

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "playwright",
            "install",
            engine,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            # 带超时安装，防止网络挂起永久阻塞整个渲染管线
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=300
            )
        except asyncio.TimeoutError:
            logger.error(
                "安装 Playwright %s 超时（300s），终止安装进程", engine
            )
            try:
                process.kill()
            except Exception:
                pass
            try:
                await process.wait()
            except Exception:
                pass
            raise RuntimeError(f"安装 Playwright {engine} 超时") from launch_failure
        if process.returncode != 0:
            detail = stderr.decode(errors="replace") or stdout.decode(errors="replace")
            raise RuntimeError(
                f"Cannot install Playwright {engine}: {detail.strip()}"
            ) from launch_failure

        _installed_browsers.add(engine)
        _browser_installed = engine == "chromium" or _browser_installed
        logger.info("Playwright %s browser installed", engine)


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
        """
        初始化渲染器

        Args:
            max_pages: 最大复用页面数
        """
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
        self._page_scales = {}
        self._active_pages_count = 0
        self._lock = asyncio.Lock()
        self._loop = None  # 记录绑定时的事件循环
        logger.info(
            "ImageRenderer 页面池初始化完成 (引擎: %s, 最大页面上限: %s)",
            engine,
            self.max_pages,
        )

    async def _force_cleanup_loop_resources(self):
        """在事件循环改变时强行清理旧事件循环残留的僵尸连接"""
        logger.info("强行重置已被销毁的事件循环残留的 Playwright 上下文")
        browser = self._browser
        playwright = self._playwright
        owns = self._owns_browser
        self._browser = None
        self._playwright = None
        self._pool = asyncio.Queue()
        self._page_scales = {}
        self._active_pages_count = 0

        # Best-effort close even if the old loop is dead (may fail silently)
        if browser is not None and owns:
            try:
                close_fn = getattr(browser, "close", None)
                if close_fn is not None:
                    result = close_fn()
                    if asyncio.iscoroutine(result):
                        try:
                            await asyncio.wait_for(result, timeout=2.0)
                        except Exception:
                            pass
            except Exception:
                pass
        if playwright is not None:
            try:
                stop_fn = getattr(playwright, "stop", None)
                if stop_fn is not None:
                    result = stop_fn()
                    if asyncio.iscoroutine(result):
                        try:
                            await asyncio.wait_for(result, timeout=2.0)
                        except Exception:
                            pass
            except Exception:
                pass

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
        current_loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = current_loop
        elif self._loop != current_loop:
            # 关键防错：如果当前运行的事件循环改变了，强行重置残留
            await self._force_cleanup_loop_resources()
            self._loop = current_loop

        if self._browser is not None and self._browser.is_connected():
            return

        # 浏览器已断连（崩溃或 CDP 断开），清理旧实例后重新初始化
        if self._browser is not None and not self._browser.is_connected():
            logger.warning("检测到浏览器断连，正在重新初始化...")
            try:
                if self._owns_browser:
                    await self._browser.close()
            except Exception:
                pass
            self._browser = None
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

        from playwright.async_api import async_playwright

        if not self.cdp_url:
            await _ensure_browser_installed(
                self.engine,
                allow_install=self.auto_install_browser,
            )
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
                self._browser = await browser_type.launch(
                    **self._launch_options(self.engine)
                )
                self._owns_browser = True
                logger.info("Playwright %s 浏览器进程启动成功", self.engine)
        except Exception:
            # launch/connect 失败时清理已启动的 Playwright 驱动，
            # 避免下次重试再次 start 覆盖 self._playwright 造成泄漏。
            try:
                await self._playwright.stop()
            except Exception:
                pass
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
        except Exception:
            await context.close()
            raise
        self._page_scales[page] = scale
        return page

    async def _dispose_page(self, page):
        self._page_scales.pop(page, None)
        try:
            await page.context.close()
        except Exception:
            try:
                await page.close()
            except Exception:
                pass

    async def _acquire_page(self, width: int, height: int, scale: int):
        """从页面池中获取一个可用的 Page 实例（自愈机制）"""
        async with self._lock:
            await self._init_browser()

            # 1. 尝试从空闲队列中拿取 page
            while not self._pool.empty():
                page = self._pool.get_nowait()
                try:
                    # 快速检测健康度，若页面已关闭或进程崩溃，则丢弃
                    if page.is_closed():
                        logger.warning("从池中获取到已关闭的页面，予以丢弃")
                        self._active_pages_count = max(0, self._active_pages_count - 1)
                        self._page_scales.pop(page, None)
                        continue
                    if self._page_scales.get(page) != scale:
                        self._active_pages_count = max(0, self._active_pages_count - 1)
                        await self._dispose_page(page)
                        continue
                    # 重新设定 viewport 尺寸，以适配当前卡片规格
                    await page.set_viewport_size({"width": width, "height": height})
                    return page
                except Exception as e:
                    logger.warning(f"获取池中页面失败，自动丢弃自愈: {e}")
                    self._active_pages_count = max(0, self._active_pages_count - 1)
                    try:
                        await self._dispose_page(page)
                    except Exception:
                        pass

            # 2. 如果池中没有空闲页面，且页面总数未达上限，则创建新页面
            if self._active_pages_count < self.max_pages:
                logger.info(
                    f"正在创建新的 Browser Page (当前活动页面数: {self._active_pages_count + 1})"
                )
                try:
                    page = await self._create_page(width, height, scale)
                    self._active_pages_count += 1
                    return page
                except Exception as e:
                    logger.error(f"创建新 Page 失败: {e}")
                    raise

        # 3. 如果已达上限且均忙碌，则阻塞等待空闲页面归还
        logger.debug("浏览器页面池已满且全部忙碌，正在阻塞等待空闲页面...")
        try:
            page = await asyncio.wait_for(self._pool.get(), timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Timed out waiting for available browser page")
        try:
            if page.is_closed():
                # 递归安全自愈拉起
                self._active_pages_count = max(0, self._active_pages_count - 1)
                return await self._acquire_page(width, height, scale)
            if self._page_scales.get(page) != scale:
                self._active_pages_count = max(0, self._active_pages_count - 1)
                await self._dispose_page(page)
                return await self._acquire_page(width, height, scale)
            await page.set_viewport_size({"width": width, "height": height})
            return page
        except Exception:
            self._active_pages_count = max(0, self._active_pages_count - 1)
            try:
                await self._dispose_page(page)
            except Exception:
                pass
            return await self._acquire_page(width, height, scale)

    async def _release_page(self, page):
        """归还或销毁 Page 实例 (DOM 自净化与防泄露)"""
        if page is None:
            return

        try:
            if page.is_closed():
                async with self._lock:
                    self._active_pages_count = max(0, self._active_pages_count - 1)
                return

            # DOM 自净化，清除敏感数据和缓存占用
            await page.goto("about:blank")
            self._pool.put_nowait(page)
            logger.debug("页面已成功清空 DOM 并归还到池中")
        except Exception as e:
            logger.warning(f"归还页面失败，强制销毁: {e}")
            async with self._lock:
                self._active_pages_count = max(0, self._active_pages_count - 1)
            try:
                await self._dispose_page(page)
            except Exception:
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
        """
        将 HTML 渲染为 PNG 图片文件 (基于 Page 复用池)
        """
        import os
        import uuid

        page = None
        idle_ms = max(1000, min(60000, int(network_idle_timeout_ms or 8000)))

        # 写入临时 HTML 文件 (避免 Windows NamedTemporaryFile 独占文件锁)
        temp_dir = tempfile.gettempdir()
        temp_html_path = os.path.join(temp_dir, f"vocab_{uuid.uuid4().hex}.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            page = await self._acquire_page(width, height, scale)

            # 超时限制保护渲染 (60 秒超时，CDN 背景图首次加载可能较慢)
            await asyncio.wait_for(
                page.goto(Path(temp_html_path).as_uri()), timeout=60.0
            )

            # 等待背景图等静止加载
            try:
                await page.wait_for_load_state("networkidle", timeout=idle_ms)
            except Exception as e:
                logger.debug(f"背景图加载网络空闲等待超时: {e}")

            await page.wait_for_timeout(150)

            # 截图保存
            await page.screenshot(path=output_path, type="png", scale="device")
            logger.info(f"卡片图片已生成: {output_path}")

            await self._release_page(page)
            return output_path
        except Exception as e:
            logger.error(f"渲染图片到文件失败: {e}")
            # 异常发生时直接销毁该 page
            if page is not None:
                async with self._lock:
                    self._active_pages_count = max(0, self._active_pages_count - 1)
                try:
                    await self._dispose_page(page)
                except Exception:
                    pass
            raise
        finally:
            try:
                if os.path.exists(temp_html_path):
                    os.remove(temp_html_path)
            except Exception:
                pass

    async def render_to_bytes(
        self,
        html_content: str,
        width: int = 432,
        height: int = 540,
        scale: int = 4,
        network_idle_timeout_ms: int = 8000,
    ) -> bytes:
        """
        将 HTML 渲染为 PNG 图片字节 (基于 Page 复用池)
        """
        import os
        import uuid

        page = None
        idle_ms = max(1000, min(60000, int(network_idle_timeout_ms or 8000)))

        # 写入临时 HTML 文件 (避免 Windows NamedTemporaryFile 独占文件锁)
        temp_dir = tempfile.gettempdir()
        temp_html_path = os.path.join(temp_dir, f"vocab_{uuid.uuid4().hex}.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            page = await self._acquire_page(width, height, scale)

            # 超时限制保护 (60 秒超时，CDN 背景图首次加载可能较慢)
            await asyncio.wait_for(
                page.goto(Path(temp_html_path).as_uri()), timeout=60.0
            )

            try:
                await page.wait_for_load_state("networkidle", timeout=idle_ms)
            except Exception as e:
                logger.debug(f"渲染时等待网络空闲超时: {e}")

            await page.wait_for_timeout(150)

            # 截图字节
            image_bytes = await page.screenshot(type="png", scale="device")

            await self._release_page(page)
            return image_bytes
        except Exception as e:
            logger.error(f"渲染图片为字节失败: {e}")
            if page is not None:
                async with self._lock:
                    self._active_pages_count = max(0, self._active_pages_count - 1)
                try:
                    await self._dispose_page(page)
                except Exception:
                    pass
            raise
        finally:
            try:
                if os.path.exists(temp_html_path):
                    os.remove(temp_html_path)
            except Exception:
                pass

    async def close(self):
        """关闭所有浏览器资源，释放池"""
        async with self._lock:
            # 清空队列中的 page 并关闭
            while not self._pool.empty():
                page = self._pool.get_nowait()
                try:
                    await self._dispose_page(page)
                except Exception:
                    pass

            browser = self._browser
            playwright = self._playwright
            owns = self._owns_browser
            self._browser = None
            self._playwright = None
            self._active_pages_count = 0
            self._page_scales = {}
            self._loop = None

        if browser is not None and owns:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass
        logger.info("ImageRenderer 浏览器资源和池已完全释放")


# 全局单例实例
_renderer_instance: Optional[ImageRenderer] = None


def get_image_renderer() -> ImageRenderer:
    """获取全局图片渲染器单例（延迟初始化）"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = ImageRenderer(max_pages=2)
    return _renderer_instance
