# -*- coding: utf-8 -*-
"""
AstrBot 每日单词卡片插件
每日定时生成玻璃拟态风格的英语单词卡片并推送到群聊
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import MessageChain

import asyncio
import collections
import datetime
import hashlib
import inspect
import json
import os
import random
import re
import time
import traceback
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

# 导入新架构模块
from .core.language_manager import LanguageManager
from .core.base_handler import WordEntry
from .core.image_renderer import ImageRenderer
from .core.security import validate_cdp_url
from .languages.english.handler import EnglishLanguageHandler
from .languages.japanese.handler import JapaneseLanguageHandler
from .languages.idiom.handler import IdiomLanguageHandler
from .languages.classical.handler import ClassicalLanguageHandler
from .languages.radio.handler import RadioLanguageHandler


def _safe_int(value, default: int) -> int:
    """配置项安全强转 int，非法值回退默认，避免插件加载失败。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value, default: bool = False) -> bool:
    """配置项安全解析 bool，避免 JSON 字符串 ``"false"`` 被 ``bool()`` 误判为 True。

    AstrBot 配置从 JSON 读取，布尔项可能以字符串形式存在；
    ``bool("false")`` 为 True，会导致 allow_remote_cdp 等被误启用。
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


# 敏感命令：测试推送最大延迟（秒）
MAX_TEST_DELAY_SECONDS = 300

# 十六进制颜色正则，用于校验 theme_color（防止 CSS 注入）
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")
# 允许注入 CSS 的 URL scheme（防御 CSS 上下文注入）
_CSS_URL_SCHEMES = frozenset({"http", "https", "file"})
_SAFE_DATA_IMAGE_RE = re.compile(
    r"^data:image/[a-zA-Z0-9.+-]+(?:;base64)?,[A-Za-z0-9+/=%._~:-]+$",
    re.IGNORECASE,
)

# 公共渲染命令限流：每用户 30 秒 1 次（重型浏览器渲染，防止刷屏 DoS）
_RATE_LIMIT_WINDOW = 30
_RATE_LIMIT_MAX_CALLS = 1
_RATE_LIMIT_MSG = f"⏳ 操作太频繁，请 {_RATE_LIMIT_WINDOW} 秒后再试"


# CDN 背景图列表 - 使用阿里云 OSS
CDN_BACKGROUNDS = [
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/alex-he-IGsLkWL4JMM-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/andrei-r-popescu-zHyr6DRoxFo-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/angelina-kusznirewicz--lCQhQ1Ueik-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/cai-fang-B47KcMR2eNY-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/eduard-pretsi-tzxzXecKA-Q-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/eugene-golovesov-TTqfc5TWPcI-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/farnaz-kohankhaki-mAIPCIDOcjk-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/fer-troulik-9EnnPbqiJbk-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/hanvin-cheong-0zr1TG4qRos-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/jisang-jung-HB1kt6cVz2E-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/junel-mujar-Po8CZAwyy6w-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/kristaps-ungurs-aaEwFuzBrDA-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/land-o-lakes-inc-9w6Qb-dqBwE-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/land-o-lakes-inc-TQSvFz7NHuo-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/lcs-_vgt-pZYzbpu_9bk-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/lens-by-benji-_jF2nXuu9AA-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/liana-s-3bPnXCN0ZUs-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/louis-gaudiau-7Z94A-v9kvw-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/magicpattern-87PP9Zd7MNo-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/marek-piwnicki-lm_CeNw9bH4-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/nemo-jDcjw0jCfv0-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/oleksandra-nadtocha-mRcd6AWsX3I-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/pascal-debrunner-ob8DTqyLzME-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/pavel-moiseev-6OyIuRmctNY-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/robert-visual-diary-berlin-4ic17Co0d6k-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/rod-long-liGPSuWK4ek-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/rod-long-o_npS9MnX34-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/roman-0OZK7ciERRM-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/samuel-quek-EBTXvQuVX08-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/samuel-quek-zg9nNEvqytQ-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/spencer-plouzek-ZcQ0g_frEck-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/takashi-s-EG_Yvw7tzV4-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/the-walters-art-museum-gjIIkr9-8qc-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/tobias-reich-BG3PSRcTOik-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/tobias-reich-n36_NSOBLnw-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/tobias-reich-UgiiLFskUCw-unsplash.jpg",
    "https://tuchuang12.oss-cn-hangzhou.aliyuncs.com/photos/wallace-henry--r5wlBxk9NA-unsplash.jpg",
]


def get_beijing_time() -> datetime.datetime:
    """获取北京时间（东八区）- 兼容 Docker 容器 UTC 时间"""
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(beijing_tz)


@dataclass(frozen=True)
class PushResult:
    """一次推送的可判定结果。"""

    attempted_count: int
    success_count: int
    # 尚未注册任何推送目标：属于正常状态，不应计为推送失败
    no_targets: bool = False


# 没有推送目标时重新检查的间隔（秒），当天稍后注册的会话仍能收到卡片
NO_TARGET_RECHECK_SECONDS = 60


@register(
    "astrbot_plugin_vocabcard",
    "YukiRa1n",
    "每日定时推送玻璃拟态风格的多语种学习卡片",
    "2.0.0",
)
class VocabCardPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_dir = Path(__file__).parent
        self.data_dir = self._resolve_data_dir()
        # 离线背景：优先 photos/，兼容旧脚本的 backgrounds/
        self.backgrounds_dir = self.plugin_dir / "photos"
        self._legacy_backgrounds_dir = self.plugin_dir / "backgrounds"

        # 初始化语种管理器
        self.lang_manager = LanguageManager(self.plugin_dir)

        # 注册语种处理器
        self.lang_manager.register_language("english", EnglishLanguageHandler)
        self.lang_manager.register_language("japanese", JapaneseLanguageHandler)
        # 注册日语 JLPT 分级卡组（内置词库收录 N1-N4，独立进度）
        self.lang_manager.register_language("japanese_n1", JapaneseLanguageHandler)
        self.lang_manager.register_language("japanese_n2", JapaneseLanguageHandler)
        self.lang_manager.register_language("japanese_n3", JapaneseLanguageHandler)
        self.lang_manager.register_language("japanese_n4", JapaneseLanguageHandler)
        self.lang_manager.register_language("idiom", IdiomLanguageHandler)
        self.lang_manager.register_language("classical", ClassicalLanguageHandler)
        self.lang_manager.register_language("radio", RadioLanguageHandler)

        # 获取当前语种配置
        self.current_language = self.config.get("current_language", "english")

        # 获取当前语种的处理器
        try:
            self.current_handler = self.lang_manager.get_handler(self.current_language)
        except ValueError as e:
            logger.warning(f"语种 '{self.current_language}' 不可用，回退到英语: {e}")
            self.current_language = "english"
            self.current_handler = self.lang_manager.get_handler("english")

        # 加载词汇数据和进度
        self.words: List[WordEntry] = self._load_words()
        self.progress: Dict = self._load_progress()
        self.offline_backgrounds: List[Path] = self._load_offline_backgrounds()

        # 定时任务相关（会从磁盘恢复）
        self._scheduler_task: Optional[asyncio.Task] = None
        self._schedule_wakeup = asyncio.Event()
        self._cached_image_path: Optional[str] = None
        self._current_word: Optional[WordEntry] = None
        self._today_generated: bool = False
        self._today_pushed: bool = False
        self._last_check_date: str = ""
        self._scheduler_consecutive_failures = 0
        self._no_target_notice_date: str = ""
        # 部分推送失败时记录已成功目标，重试时跳过
        self._push_succeeded_umos: set[str] = set()
        self._restore_schedule_state()

        # 进度文件保存锁（防止并发写入冲突）
        self._progress_lock = asyncio.Lock()
        self._workflow_lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()

        # 公共渲染命令限流状态：{sender_id: deque[timestamp]}
        self._rate_limit: Dict[str, collections.deque] = {}

        # 后台任务集合（延迟推送、图片清理等），terminate 时统一取消
        self._background_tasks: set[asyncio.Task] = set()

        browser_engine = str(self.config.get("browser_engine", "chromium")).strip()
        if browser_engine not in {"chromium", "firefox", "webkit"}:
            logger.warning(
                f"不支持的 browser_engine '{browser_engine}'，回退到 chromium"
            )
            browser_engine = "chromium"
        allow_remote_cdp = _safe_bool(self.config.get("allow_remote_cdp", False))
        try:
            browser_cdp_url = validate_cdp_url(
                self.config.get("browser_cdp_url", ""),
                allow_remote=allow_remote_cdp,
            )
        except ValueError as e:
            logger.warning(f"Invalid browser_cdp_url, ignoring: {e}")
            browser_cdp_url = ""

        browser_max_pages = max(
            1, min(8, _safe_int(self.config.get("browser_max_pages", 2), 2))
        )
        self._render_scale = max(
            1, min(4, _safe_int(self.config.get("render_scale", 3), 3))
        )
        self._bg_load_timeout = max(
            1000, min(60000, _safe_int(self.config.get("bg_load_timeout", 5000), 5000))
        )
        self._image_renderer = ImageRenderer(
            max_pages=browser_max_pages,
            engine=browser_engine,
            cdp_url=browser_cdp_url,
            auto_install_browser=_safe_bool(
                self.config.get("auto_install_browser", False)
            ),
        )

    def _resolve_data_dir(self) -> Path:
        """Prefer AstrBot plugin data dir; fall back to plugin-local data/."""
        try:
            from astrbot.api.star import StarTools

            data_dir = Path(StarTools.get_data_dir("astrbot_plugin_vocabcard"))
            data_dir.mkdir(parents=True, exist_ok=True)
            # Migrate from legacy "vocabcard" plugin_data dir and bundled data/
            legacy_dirs = [
                data_dir.parent / "vocabcard",
                self.plugin_dir / "data",
            ]
            for legacy in legacy_dirs:
                if not legacy.exists() or legacy.resolve() == data_dir.resolve():
                    continue
                candidates = list(legacy.glob("progress_*.json"))
                for name in ("progress.json", "schedule_state.json"):
                    extra = legacy / name
                    if extra.exists():
                        candidates.append(extra)
                for src in candidates:
                    dst = data_dir / src.name
                    if src.is_file() and not dst.exists():
                        try:
                            import shutil

                            shutil.copy2(src, dst)
                            logger.info(f"Migrated {src.name} to plugin data dir")
                        except OSError as e:
                            logger.warning(f"Failed to migrate {src.name}: {e}")
            return data_dir
        except Exception as e:
            logger.debug(f"StarTools.get_data_dir unavailable, using local data/: {e}")
            local = self.plugin_dir / "data"
            local.mkdir(parents=True, exist_ok=True)
            return local

    def _remove_cached_file(self, candidate: Optional[str]) -> None:
        """Delete a plugin-owned cached image inside data_dir."""
        if not candidate or not isinstance(candidate, str):
            return
        if not self._path_within_data_dir(candidate):
            return
        try:
            if os.path.isfile(candidate):
                os.remove(candidate)
        except OSError as e:
            logger.warning(f"清理缓存图片失败: {e}")

    @staticmethod
    def _word_key(word: WordEntry) -> str:
        """Return the unique progress key for a word entry."""
        extra = getattr(word, "extra_fields", None)
        if isinstance(extra, dict):
            key = extra.get("progress_key")
            if isinstance(key, str) and key:
                return key
        return word.word

    def _path_within_data_dir(self, candidate: str) -> bool:
        """检查候选路径是否位于 data_dir 内（防篡改 state 指向任意文件）。

        用 ``is_relative_to`` 做目录边界判断，避免 ``C:/foo`` 前缀误匹配
        ``C:/foobar/secret`` 这类路径。
        """
        try:
            resolved = Path(candidate).resolve()
            data_root = self.data_dir.resolve()
            return resolved.is_relative_to(data_root)
        except (OSError, ValueError):
            return False

    def _schedule_state_path(self) -> Path:
        return self.data_dir / "schedule_state.json"

    def _restore_schedule_state(self) -> None:
        """Restore in-memory daily flags / cache after process restart."""
        path = self._schedule_state_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load schedule state: {e}")
            return

        if not isinstance(state, dict):
            logger.warning(
                f"schedule_state.json 类型错误（期望 dict，得到 {type(state).__name__}），使用默认状态"
            )
            return

        today = get_beijing_time().strftime("%Y-%m-%d")
        cached = state.get("cached_image_path") or ""
        if state.get("date") != today:
            self._remove_cached_file(cached)
            return

        # 持久化的语种与当前配置不一致时（管理员改配置切语种），
        # 放弃恢复当日状态，避免复用旧语种的缓存图片和进度。
        if state.get("language") and state.get("language") != self.current_language:
            self._remove_cached_file(cached)
            logger.info(
                "持久化语种 %s 与当前 %s 不一致，跳过当日状态恢复",
                state.get("language"),
                self.current_language,
            )
            return

        self._last_check_date = today
        self._today_generated = _safe_bool(state.get("today_generated", False))
        self._today_pushed = _safe_bool(state.get("today_pushed", False))
        succeeded_umos = state.get("push_succeeded_umos", [])
        if isinstance(succeeded_umos, list) and all(
            isinstance(umo, str) for umo in succeeded_umos
        ):
            self._push_succeeded_umos = set(succeeded_umos)
        else:
            logger.warning(
                "schedule_state.json 中的 push_succeeded_umos 类型错误，忽略"
            )
        # 安全边界：cached_image_path 来自本地 schedule_state.json，
        # 若被篡改可能指向任意文件；后续推送会读取/发送/删除它。
        # 只信任位于 data_dir 内的常规文件路径。
        if cached and isinstance(cached, str) and self._path_within_data_dir(cached):
            if os.path.isfile(cached):
                self._cached_image_path = cached
            else:
                logger.warning(f"cached_image_path 不存在，忽略: {cached}")
        word_text = state.get("current_word") or ""
        if word_text:
            self._current_word = next(
                (
                    w
                    for w in self.words
                    if self._word_key(w) == word_text or w.word == word_text
                ),
                None,
            )
        logger.info(
            "Restored schedule state: generated=%s pushed=%s cache=%s",
            self._today_generated,
            self._today_pushed,
            bool(self._cached_image_path),
        )

    async def _persist_schedule_state(self) -> None:
        """Write daily schedule flags to disk for restart resilience.

        scheduler、延迟任务和语言切换可能并发调用，用锁保护 + 原子替换，
        避免 tmp 文件交错写入导致状态丢失或 FileNotFound。
        """
        async with self._progress_lock:
            await self._persist_schedule_state_unlocked()

    async def _persist_schedule_state_unlocked(self) -> None:
        """写入逻辑；调用者必须持有 _progress_lock。"""
        path = self._schedule_state_path()
        today = get_beijing_time().strftime("%Y-%m-%d")
        self._last_check_date = today
        state = {
            "date": today,
            "today_generated": self._today_generated,
            "today_pushed": self._today_pushed,
            "cached_image_path": self._cached_image_path or "",
            "current_word": (
                self._word_key(self._current_word) if self._current_word else ""
            ),
            "push_succeeded_umos": sorted(self._push_succeeded_umos),
            "language": self.current_language,
        }
        try:
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.warning(f"Failed to persist schedule state: {e}")

    def _load_offline_backgrounds(self) -> List[Path]:
        """加载离线背景图列表（photos/ 优先，兼容 backgrounds/）"""
        patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]
        backgrounds: List[Path] = []
        for directory in (self.backgrounds_dir, self._legacy_backgrounds_dir):
            if not directory.exists():
                continue
            for pattern in patterns:
                backgrounds.extend(directory.glob(pattern))
                backgrounds.extend(directory.glob(pattern.upper()))
        # 去重
        unique = list({p.resolve(): p for p in backgrounds}.values())
        logger.info(f"已加载 {len(unique)} 张离线背景图")
        return unique

    def _get_background_url(self, word: WordEntry) -> str:
        """获取背景图 URL（优先 CDN，其次 AI 生成，最后本地图片）"""
        # 优先使用 CDN 图片（阿里云 OSS）
        if _safe_bool(self.config.get("use_cdn_background", True)):
            return random.choice(CDN_BACKGROUNDS)

        # 回退到 AI 生成（如果启用）
        use_ai = _safe_bool(self.config.get("enable_ai_background", False))
        if use_ai:
            # 使用 Pollinations.ai 动态生成 - 提高分辨率
            bg_prompt = self._generate_bg_prompt(word)
            # 使用更高分辨率：1920x2400（原来是1080x1350）
            return f"https://image.pollinations.ai/prompt/{bg_prompt}?width=1920&height=2400&nologo=true&model=flux&enhance=true"

        # 配置的默认背景 URL
        default_bg = (self.config.get("default_bg_url", "") or "").strip()
        if default_bg:
            return default_bg

        # 最后回退到本地图片
        return self._get_offline_background_url()

    def _get_offline_background_url(self) -> str:
        """获取一张离线背景图的 file:// URL"""
        if not self.offline_backgrounds:
            # 没有离线图，返回无裸引号/井号截断风险的纯色背景 data URL
            return (
                "data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27"
                "%20width=%271080%27%20height=%271350%27%3E%3Crect%20fill=%27%231a1a2e%27"
                "%20width=%27100%25%27%20height=%27100%25%27/%3E%3C/svg%3E"
            )

        bg_path = random.choice(self.offline_backgrounds)
        # 返回 file:// URL（as_uri 会做百分号编码，正确处理空格/#/% 等字符）
        return bg_path.as_uri()

    def _load_words(self) -> List[WordEntry]:
        """加载词汇数据并为同形/重复关键字词条分配稳定唯一键"""
        try:
            if self.current_language == "japanese":
                level_filter = self.config.get("japanese_level", "all")
                if str(level_filter).strip().upper() == "N5":
                    logger.warning(
                        "内置日语词库暂未收录 N5 词汇，japanese_level 自动回退为 all"
                    )
                    level_filter = "all"
                words = self.current_handler.load_words(level_filter=level_filter)
            else:
                words = self.current_handler.load_words()
        except Exception as e:
            logger.error(f"加载词汇数据失败: {e}")
            return []

        counts = collections.Counter(w.word for w in words)
        seen: Dict[str, int] = collections.defaultdict(int)
        used_keys: set[str] = set()
        for entry in words:
            idx = seen[entry.word]
            seen[entry.word] += 1
            if counts[entry.word] <= 1 or idx == 0:
                used_keys.add(entry.word)
                continue
            extra = entry.extra_fields if isinstance(entry.extra_fields, dict) else {}
            entry.extra_fields = extra
            suffix = str(
                extra.get("sentence_num") or entry.phonetic or (idx + 1)
            ).strip()
            candidate = f"{entry.word}#{suffix}"
            seq = idx + 1
            while candidate in used_keys:
                candidate = f"{entry.word}#{seq}"
                seq += 1
            used_keys.add(candidate)
            extra["progress_key"] = candidate
        return words

    def _load_progress(self) -> Dict:
        """加载学习进度（语种特定，支持旧数据迁移）"""
        progress_file = self.data_dir / f"progress_{self.current_language}.json"

        # 如果语种特定的进度文件不存在，尝试从旧文件迁移
        if not progress_file.exists():
            old_progress_file = self.data_dir / "progress.json"
            if old_progress_file.exists() and self.current_language == "english":
                # 将旧的进度文件重命名为英语进度文件（因为旧版本只支持英语）
                try:
                    import shutil

                    shutil.copy2(old_progress_file, progress_file)
                    os.remove(old_progress_file)
                    logger.info(f"已将旧进度文件迁移到: {progress_file}")
                except Exception as e:
                    logger.warning(f"迁移旧进度文件失败: {e}")

        # 加载进度文件
        if progress_file.exists():
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("sent_words"), list):
                    data["sent_words"] = [str(w) for w in data["sent_words"]]
                    if not isinstance(data.get("last_push_date"), str):
                        data["last_push_date"] = ""
                    return data
                logger.warning(f"进度文件结构异常，使用默认进度: {progress_file}")
            except Exception as e:
                logger.error(f"加载进度数据失败: {e}")

        return {"sent_words": [], "last_push_date": ""}

    async def _save_progress(self):
        """Save progress (language-specific) with lock + atomic write"""
        async with self._progress_lock:
            await self._write_progress_unlocked()

    async def _write_progress_unlocked(self):
        """Write progress file; caller must hold _progress_lock."""
        progress_file = self.data_dir / f"progress_{self.current_language}.json"
        try:
            import aiofiles

            tmp_file = progress_file.with_suffix(".json.tmp")
            async with aiofiles.open(tmp_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.progress, ensure_ascii=False, indent=2))
            os.replace(tmp_file, progress_file)
        except ImportError:
            await asyncio.get_running_loop().run_in_executor(
                None, self._atomic_sync_write, progress_file
            )
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def _atomic_sync_write(self, progress_file: Path):
        """Synchronous atomic write fallback"""
        tmp_file = progress_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, progress_file)

    async def initialize(self):
        """Async initialization"""
        directories_to_create = [
            self.data_dir,
            self.backgrounds_dir,
        ]

        for directory in directories_to_create:
            logger.debug(f"Ensuring directory exists: {directory}")
            directory.mkdir(parents=True, exist_ok=True)

        progress_file = self.data_dir / f"progress_{self.current_language}.json"
        if not progress_file.exists():
            default_progress = {"sent_words": [], "last_push_date": ""}
            async with self._progress_lock:
                try:
                    with open(progress_file, "w", encoding="utf-8") as f:
                        json.dump(default_progress, f, ensure_ascii=False, indent=2)
                    logger.info(f"Created progress file: {progress_file}")
                except Exception as e:
                    logger.error(f"Failed to create progress file: {e}")

        # 清理上次未及时回收的过期临时图片（保留今日待推送缓存图）
        cutoff = time.time() - 3600
        for stale in self.data_dir.glob("card_*.png"):
            try:
                if (
                    self._cached_image_path
                    and stale.resolve() == Path(self._cached_image_path).resolve()
                ):
                    continue
                if stale.is_file() and stale.stat().st_mtime < cutoff:
                    stale.unlink(missing_ok=True)
            except OSError:
                continue

        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info("单词卡片定时任务已启动")

        logger.info(
            f"VocabCard plugin initialized [language: {self.current_language}], loaded {len(self.words)} words"
        )

    async def _sleep_interruptible(self, seconds: float) -> None:
        """Sleep up to ``seconds`` or wake early when schedule configuration changes."""
        if seconds <= 0:
            self._schedule_wakeup.clear()
            return
        try:
            await asyncio.wait_for(self._schedule_wakeup.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
        finally:
            self._schedule_wakeup.clear()

    async def _schedule_loop(self):
        """定时任务主循环 - 智能睡眠，精准触发"""
        while True:
            try:
                now = get_beijing_time()
                today_str = now.strftime("%Y-%m-%d")

                # 解析配置的时间
                gen_time = self._parse_time(
                    self.config.get("push_time_generate", "07:30")
                )
                push_time = self._parse_time(self.config.get("push_time_send", "08:00"))

                # 每天0点重置标记与失败计数，并清理昨日未发出的缓存图
                if self._last_check_date != today_str:
                    async with self._workflow_lock:
                        if self._last_check_date != today_str:
                            self._remove_cached_file(self._cached_image_path)
                            self._today_generated = False
                            self._today_pushed = False
                            self._cached_image_path = None
                            self._current_word = None
                            self._push_succeeded_umos = set()
                            self._last_check_date = today_str
                            self._scheduler_consecutive_failures = 0
                            await self._persist_schedule_state()

                # 计算下一个目标时间
                next_target = self._calculate_next_target_time(now, gen_time, push_time)

                if next_target:
                    sleep_seconds = (next_target - now).total_seconds()

                    # 如果距离目标时间超过 60 秒，先睡到提前 30 秒
                    if sleep_seconds > 60:
                        sleep_until = sleep_seconds - 30
                        logger.debug(
                            f"距离下次任务还有 {sleep_seconds:.0f} 秒，先睡眠 {sleep_until:.0f} 秒"
                        )
                        await self._sleep_interruptible(sleep_until)
                        continue

                    # 距离目标时间很近了，精确等待
                    if sleep_seconds > 0:
                        logger.debug(f"即将执行任务，精确等待 {sleep_seconds:.1f} 秒")
                        await self._sleep_interruptible(sleep_seconds)

                # 重新获取当前时间（睡眠后可能被语种切换唤醒或已跨天）
                now = get_beijing_time()
                if now.strftime("%Y-%m-%d") != today_str:
                    continue

                # 若已过生成时间且今日尚未生成（含重启补跑），立即生成
                gen_passed = self._time_reached(now, gen_time)
                push_passed = self._time_reached(now, push_time)
                gen_failed_this_tick = False

                if not self._today_generated and gen_passed:
                    if not self.words:
                        async with self._workflow_lock:
                            if not self.words and self._last_check_date == today_str:
                                logger.info(
                                    "当前卡组 '%s' 没有可用词条，今日跳过定时推送",
                                    self.current_language,
                                )
                                self._today_generated = True
                                self._today_pushed = True
                                self._scheduler_consecutive_failures = 0
                                await self._persist_schedule_state()
                        continue
                    logger.info("开始生成每日单词卡片...")
                    should_continue = False
                    async with self._workflow_lock:
                        if self._last_check_date != today_str:
                            should_continue = True
                        elif not self._today_generated:
                            exhausted = not _safe_bool(
                                self.config.get("reset_on_complete", True)
                            ) and all(
                                self._word_key(w)
                                in set(self.progress.get("sent_words", []))
                                for w in self.words
                            )
                            if exhausted:
                                logger.info(
                                    "所有词条已推送完毕且未开启自动重置，今日跳过"
                                )
                                self._today_generated = True
                                self._today_pushed = True
                                self._scheduler_consecutive_failures = 0
                                await self._persist_schedule_state()
                                should_continue = True
                            else:
                                self._today_generated = (
                                    await self._generate_daily_card()
                                )
                                if self._today_generated:
                                    self._scheduler_consecutive_failures = 0
                                else:
                                    self._scheduler_consecutive_failures += 1
                                    gen_failed_this_tick = True
                                await self._persist_schedule_state()
                    if should_continue:
                        continue

                # 推送：到达推送时间且尚未推送
                if push_passed and not self._today_pushed:
                    skip_tick = False
                    no_targets = False
                    async with self._workflow_lock:
                        if self._last_check_date != today_str:
                            skip_tick = True
                        elif not self._today_pushed:
                            # 缓存丢失且本轮未刚刚生成失败时才补生成，避免单轮双倍失败计数
                            if (
                                not (
                                    self._cached_image_path
                                    and os.path.exists(self._cached_image_path)
                                )
                                and not gen_failed_this_tick
                            ):
                                if not self.words:
                                    self._today_generated = True
                                    self._today_pushed = True
                                    self._scheduler_consecutive_failures = 0
                                    await self._persist_schedule_state()
                                    skip_tick = True
                                else:
                                    logger.info("缓存卡片缺失，推送前补生成...")
                                    self._today_generated = (
                                        await self._generate_daily_card()
                                    )
                                    if self._today_generated:
                                        self._scheduler_consecutive_failures = 0
                                    else:
                                        self._scheduler_consecutive_failures += 1
                                    await self._persist_schedule_state()

                            if (
                                not skip_tick
                                and self._cached_image_path
                                and os.path.exists(self._cached_image_path)
                            ):
                                logger.info("开始推送每日单词卡片...")
                                result = await self._push_daily_card()
                                if result.no_targets:
                                    no_targets = True
                                else:
                                    all_succeeded = (
                                        result.attempted_count > 0
                                        and result.success_count
                                        == result.attempted_count
                                    )
                                    self._today_pushed = all_succeeded
                                    if self._today_pushed:
                                        self._scheduler_consecutive_failures = 0
                                    else:
                                        self._scheduler_consecutive_failures += 1
                                    await self._persist_schedule_state()
                    if skip_tick:
                        continue
                    if no_targets:
                        await self._wait_for_push_targets(today_str)
                        continue

                # 连续失败时指数退避，避免热循环刷日志/反复渲染
                if self._scheduler_consecutive_failures > 0:
                    backoff = min(
                        300, 10 * (2 ** (self._scheduler_consecutive_failures - 1))
                    )
                    if self._scheduler_consecutive_failures >= 8:
                        logger.warning(
                            "定时任务连续失败 %d 次，当日放弃重试，明日 0 点重置",
                            self._scheduler_consecutive_failures,
                        )
                        async with self._workflow_lock:
                            self._remove_cached_file(self._cached_image_path)
                            self._cached_image_path = None
                            self._current_word = None
                            self._today_generated = True
                            self._today_pushed = True
                            await self._persist_schedule_state()
                        await self._sleep_interruptible(3600)
                        continue
                    logger.warning(
                        "定时任务连续失败 %d 次，退避 %ds 后重试",
                        self._scheduler_consecutive_failures,
                        backoff,
                    )
                    await self._sleep_interruptible(backoff)
                    continue

                # Wait before next check
                await self._sleep_interruptible(10)

            except Exception as e:
                logger.error(f"定时任务出错: {e}")
                self._scheduler_consecutive_failures += 1
                backoff = min(
                    300, 60 * (2 ** (self._scheduler_consecutive_failures - 1))
                )
                await self._sleep_interruptible(backoff)

    def _parse_time(self, time_str) -> tuple:
        """Parse time string HH:MM with validation"""
        if not isinstance(time_str, str):
            logger.warning(
                f"Time format invalid type '{type(time_str).__name__}': {time_str}, using default 08:00"
            )
            return (8, 0)
        try:
            parts = time_str.split(":")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(f"Time out of range: {hour}:{minute}")
            return (hour, minute)
        except (ValueError, IndexError) as e:
            logger.warning(
                f"Time format parse failed '{time_str}': {e}, using default 08:00"
            )
            return (8, 0)

    def _is_within_minute_window(
        self, now: datetime.datetime, target_time: tuple
    ) -> bool:
        """Check if current time is within the target minute window (tolerance: 60s)"""
        target_hour, target_minute = target_time
        return now.hour == target_hour and now.minute == target_minute

    def _time_reached(self, now: datetime.datetime, target_time: tuple) -> bool:
        """True when current clock is at or past HH:MM today."""
        target_hour, target_minute = target_time
        return (now.hour, now.minute) >= (target_hour, target_minute)

    def _calculate_next_target_time(
        self, now: datetime.datetime, gen_time: tuple, push_time: tuple
    ) -> Optional[datetime.datetime]:
        """计算下一个目标时间点（生成时间或推送时间中最近的一个）"""
        today = now.date()
        # 获取时区信息（与 now 保持一致）
        tz = now.tzinfo

        # 构建今天的生成时间和推送时间（带时区）
        gen_datetime = datetime.datetime.combine(
            today, datetime.time(gen_time[0], gen_time[1]), tzinfo=tz
        )
        push_datetime = datetime.datetime.combine(
            today, datetime.time(push_time[0], push_time[1]), tzinfo=tz
        )

        # 重启补跑 / 失败重试：已过设定时间但尚未完成的任务优先立即执行，
        # 避免 push_time 在未来时被未来目标掩盖而延误生成或失败退避重试。
        if not self._today_generated and gen_datetime <= now:
            logger.debug("生成时间已过但未完成，立即执行")
            return now
        if not self._today_pushed and push_datetime <= now:
            logger.debug("推送时间已过但未完成，立即执行")
            return now

        # 找出所有未来的目标时间
        targets = []

        # 如果还没生成过，且生成时间未到
        if not self._today_generated and gen_datetime > now:
            targets.append(gen_datetime)

        # 如果推送尚未完成，且推送时间未到
        if not self._today_pushed and push_datetime > now:
            targets.append(push_datetime)

        # 如果今天的任务都完成了，睡到次日 00:00 触发跨天重置，再计算次日最早任务
        if not targets:
            tomorrow = today + datetime.timedelta(days=1)
            next_midnight = datetime.datetime.combine(
                tomorrow, datetime.time(0, 0), tzinfo=tz
            )
            targets.append(next_midnight)

        # 返回最近的目标时间
        return min(targets) if targets else None

    async def _select_word(self, update_progress: bool = True) -> Optional[WordEntry]:
        """Select an unsent word.

        Args:
            update_progress: Whether an exhausted deck may reset and save progress.
        """
        if not self.words:
            return None

        sent_words = set(self.progress.get("sent_words", []))
        available = [w for w in self.words if self._word_key(w) not in sent_words]

        # 如果全部推送完毕
        if not available:
            if _safe_bool(self.config.get("reset_on_complete", True)):
                if update_progress:
                    current_keys = {self._word_key(w) for w in self.words}
                    if (
                        self.current_language == "japanese"
                        and self.config.get("japanese_level", "all") != "all"
                    ):
                        # 仅清空当前筛选等级的进度，保留其他 JLPT 等级的已学记录
                        remaining = [
                            k
                            for k in self.progress.get("sent_words", [])
                            if k not in current_keys
                        ]
                    else:
                        remaining = []
                    self.progress["sent_words"] = remaining
                    await self._save_progress()
                    logger.info("所有单词已推送完毕，已重置进度")
                available = self.words
            else:
                logger.warning("所有单词已推送完毕，且未开启自动重置")
                return None

        # 选择模式
        mode = self.config.get("learning_mode", "random")
        if mode == "sequential":
            return available[0]
        return random.choice(available)

    async def _mark_word_sent(self, word: str):
        """Mark word as sent"""
        async with self._progress_lock:
            sent = set(self.progress.get("sent_words", []))
            sent.add(word)
            self.progress["sent_words"] = list(sent)
            self.progress["last_push_date"] = get_beijing_time().strftime("%Y-%m-%d")
            await self._write_progress_unlocked()

    def _generate_bg_prompt(self, word: WordEntry) -> str:
        """根据单词生成背景图提示词"""
        word_text = word.word
        pos = (word.pos or "").lower()

        # 基于词性选择主题风格
        if "adj" in pos:
            theme = "abstract gradient aesthetic atmosphere"
        elif "n." in pos:
            theme = "realistic minimalist photography"
        elif "v." in pos:
            theme = "dynamic motion artistic blur"
        else:
            theme = "aesthetic minimalist background"

        # 构建提示词（编码斜杠等全部特殊字符，避免破坏路径层级）
        prompt = f"{word_text} concept, {theme}, high quality, 4k, no text, cinematic lighting"
        return urllib.parse.quote(prompt, safe="")

    @staticmethod
    def _sanitize_css_url(value: str) -> str:
        """校验进入 <style> url("...") 上下文的背景 URL。

        <style> 为 HTML RAWTEXT 元素，浏览器不会解码 HTML 实体，因此模板中
        对已通过本函数校验的 URL 使用 ``| safe`` 输出，并在此处严格要求合法协议、
        禁止协议相对 UNC 路径 ``//``，剥离一切可闭合字符串或逃逸 CSS 的字符。
        """
        value = (value or "").strip()
        if not value:
            return ""
        if value.startswith("//"):
            return ""
        if value.lower().startswith("data:"):
            return value if _SAFE_DATA_IMAGE_RE.fullmatch(value) else ""
        cleaned = "".join(
            ch
            for ch in value
            if ord(ch) >= 0x20
            and ord(ch) != 0x7F
            and ch not in {"'", '"', ";", "(", ")", "{", "}", "\\", "<", ">"}
        )
        parsed = urllib.parse.urlsplit(cleaned)
        scheme = parsed.scheme.lower()
        if scheme not in _CSS_URL_SCHEMES:
            return ""
        if scheme == "file" and parsed.netloc.lower() not in {"", "localhost"}:
            return ""
        if scheme in {"http", "https"} and not parsed.netloc:
            return ""
        return cleaned

    @staticmethod
    def _sanitize_theme_color(value: str) -> str:
        """校验 theme_color 必须为合法的十六进制颜色，否则回退默认色。"""
        value = (value or "").strip()
        if _HEX_COLOR_RE.match(value):
            return value
        return "#2F4F4F"

    def _render_template(self, word: WordEntry) -> str:
        """Render HTML template using Handler"""
        bg_url = self._sanitize_css_url(self._get_background_url(word))
        theme_color = self._sanitize_theme_color(
            random.choice(self.current_handler.get_theme_colors())
        )
        bg_x = random.randint(0, 100)
        bg_y = random.randint(0, 100)
        bg_position = f"{bg_x}% {bg_y}%"
        return self.current_handler.render_card(
            word, bg_url=bg_url, theme_color=theme_color, bg_position=bg_position
        )

    def _prepare_card_render(self, word: WordEntry) -> tuple[str, str, int, int]:
        """准备单词卡片 HTML、输出路径及画布尺寸。"""
        html_content = self._render_template(word)

        safe_name = hashlib.md5(word.word.encode()).hexdigest()[:12]
        output_png = self.data_dir / f"card_{safe_name}_{uuid.uuid4().hex[:8]}.png"

        card_size = getattr(self.current_handler.config, "card_size", (432, 540))
        width = _safe_int(card_size[0], 432) if len(card_size) >= 2 else 432
        height = _safe_int(card_size[1], 540) if len(card_size) >= 2 else 540
        return html_content, str(output_png), width, height

    async def _render_card_file(
        self, html_content: str, output_path: str, width: int, height: int
    ) -> str:
        """将已渲染的卡片 HTML 截图保存为 PNG 文件。"""
        try:
            await self._image_renderer.render_to_file(
                html_content=html_content,
                output_path=output_path,
                width=width,
                height=height,
                scale=self._render_scale,
                network_idle_timeout_ms=self._bg_load_timeout,
            )

            logger.info(f"卡片图片已生成: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"生成卡片图片失败: {e}")
            raise

    async def _generate_card_image(self, word: WordEntry) -> str:
        """Generate word card image"""
        html_content, output_path, width, height = self._prepare_card_render(word)
        return await self._render_card_file(html_content, output_path, width, height)

    def _check_rate_limit(self, event: AstrMessageEvent, record: bool = True) -> bool:
        """公共渲染命令限流：每用户 30 秒 1 次，防止刷屏触发重型浏览器渲染。

        Args:
            event: 当前消息事件。
            record: 为 False 时仅检查当前是否处于冷却窗口，不记录本次调用。

        Returns:
            True 表示允许继续执行；False 表示被限流。
        """
        try:
            sender = str(event.get_sender_id() or event.unified_msg_origin)
        except Exception:
            sender = event.unified_msg_origin
        now = time.monotonic()

        # 全局淘汰：定期清理过期 sender 条目，防止唯一用户字典无界增长
        if len(self._rate_limit) > 1000:
            expired = [
                k
                for k, v in self._rate_limit.items()
                if not v or now - v[-1] > _RATE_LIMIT_WINDOW
            ]
            for k in expired:
                self._rate_limit.pop(k, None)

        stamps = self._rate_limit.get(sender)
        if stamps is None:
            if not record:
                return True
            stamps = collections.deque()
            self._rate_limit[sender] = stamps
        # 清理窗口外的旧时间戳
        while stamps and now - stamps[0] > _RATE_LIMIT_WINDOW:
            stamps.popleft()
        if not stamps:
            # 该 sender 窗口已完全过期，移除条目避免字典无界增长
            self._rate_limit.pop(sender, None)
            if not record:
                return True
            self._rate_limit[sender] = stamps = collections.deque()
        if len(stamps) >= _RATE_LIMIT_MAX_CALLS:
            return False
        if record:
            stamps.append(now)
        return True

    def _schedule_image_cleanup(self, path: str) -> None:
        """在短暂延迟后删除临时图片，避免与平台异步上传产生竞态。

        yield event.image_result(path) 之后，文件读取/上传可能由平台异步
        完成，立即 os.remove 存在发送失败的风险。改为一次性延迟任务，
        延迟 30 秒后清理；若任务因 terminate() 被取消，则刻意保留文件以免
        打断在途上传，遗留文件将在下次 initialize() 启动过期清理时回收。
        """
        if not path:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _cleanup() -> None:
            await asyncio.sleep(30)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                logger.warning(f"清理临时图片失败: {e}")

        try:
            task = loop.create_task(_cleanup())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            # 事件循环关闭时放弃延迟清理
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    async def _generate_daily_card(self) -> bool:
        """生成每日单词卡片"""
        word = await self._select_word()
        if not word:
            logger.warning("没有可用的单词")
            return False

        try:
            image_path = await self._generate_card_image(word)
            old_path = self._cached_image_path
            if old_path and old_path != image_path:
                self._remove_cached_file(old_path)
            self._cached_image_path = image_path
            self._current_word = word
            self._push_succeeded_umos = set()
            await self._persist_schedule_state()
            logger.info(f"已生成每日单词卡片: {word.word}")
            return True
        except Exception as e:
            logger.error(f"生成每日卡片失败: {e}")
            return False

    async def _wait_for_push_targets(self, today_str: str) -> None:
        """没有推送目标时可中断睡眠，直到有会话注册、切换语种或进入新的一天。

        不计入连续失败、不标记今日已推送：避免退避重试刷屏，也保证
        当天稍后用 /vocab_register 注册的会话能立即被唤醒并收到当天的卡片。
        """
        if self._no_target_notice_date != today_str:
            logger.info("尚无已注册的推送目标，卡片已生成，注册后将自动推送")
            self._no_target_notice_date = today_str
        had_cache = bool(self._cached_image_path)
        while not self.config.get("target_groups", []):
            await self._sleep_interruptible(NO_TARGET_RECHECK_SECONDS)
            if get_beijing_time().strftime("%Y-%m-%d") != today_str:
                return
            if had_cache and not self._cached_image_path:
                return

    async def _push_daily_card(
        self, extra_targets: Optional[List[str]] = None
    ) -> PushResult:
        """推送卡片到已注册的群聊"""
        if not self._cached_image_path or not os.path.exists(self._cached_image_path):
            logger.warning("没有已生成的卡片可推送")
            return PushResult(attempted_count=0, success_count=0)

        configured = list(self.config.get("target_groups", []) or [])
        if extra_targets:
            for extra in extra_targets:
                if extra and extra not in configured:
                    configured.append(extra)
        target_groups = list(dict.fromkeys(configured))
        if not target_groups:
            logger.debug("没有已注册的推送目标")
            return PushResult(attempted_count=0, success_count=0, no_targets=True)

        # 部分失败重试时，跳过已成功目标
        skip = self._push_succeeded_umos
        all_previously_succeeded = False
        if skip:
            remaining = [umo for umo in target_groups if umo not in skip]
            if not remaining:
                logger.info("所有当前目标均已成功推送，复用完成流程")
                all_previously_succeeded = True
            else:
                logger.info(
                    f"跳过 {len(skip)} 个已成功目标，重试剩余 {len(remaining)} 个"
                )
                target_groups = remaining

        success_count = len(target_groups) if all_previously_succeeded else 0
        word_text = self._current_word.word if self._current_word else "单词"

        # 记录本次推送成功的目标，用于部分失败时只重试失败目标
        succeeded_umos: set[str] = set()
        for umo in [] if all_previously_succeeded else target_groups:
            try:
                # 构建消息链
                chain = MessageChain()
                chain.message(f"📚 每日单词: {word_text}")
                chain.file_image(self._cached_image_path)

                sent = await self.context.send_message(umo, chain)
                if sent is False:
                    logger.warning(f"推送到 {umo} 失败：平台返回 False")
                    continue
                success_count += 1
                succeeded_umos.add(umo)
                logger.info(f"已推送到: {umo}")
            except Exception as e:
                logger.error(f"推送到 {umo} 失败: {e}")

        logger.info(f"每日单词推送完成: {success_count}/{len(target_groups)}")

        # 仅当全部目标成功才提交进度并删图；部分失败时保留缓存，
        # 且记录已成功目标，后续重试只发送给失败目标。
        if success_count == len(target_groups) and success_count > 0:
            if self._current_word is not None:
                await self._mark_word_sent(self._word_key(self._current_word))
            try:
                if os.path.exists(self._cached_image_path):
                    os.remove(self._cached_image_path)
            except OSError as e:
                logger.warning(f"清理缓存图片失败: {e}")
            self._cached_image_path = None
            self._current_word = None
            self._push_succeeded_umos = set()
            await self._persist_schedule_state()
        elif success_count > 0:
            self._push_succeeded_umos.update(succeeded_umos)
            await self._persist_schedule_state()
            logger.warning(
                f"部分目标推送失败（{success_count}/{len(target_groups)}），"
                "保留缓存供后续重试"
            )

        return PushResult(
            attempted_count=len(target_groups),
            success_count=success_count,
        )

    # ========== 用户命令 ==========

    def _get_config_lock(self) -> asyncio.Lock:
        """Return the config lock, creating one lazily for test stubs without __init__."""
        lock = getattr(self, "_config_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._config_lock = lock
        return lock

    async def _save_plugin_config(self) -> None:
        """优先调用异步配置保存，兼容仅提供同步 save_config 的测试替身。"""
        save_async = getattr(self.config, "save_config_async", None)
        if inspect.iscoroutinefunction(save_async):
            await save_async()
            return
        self.config.save_config()

    @filter.command("vocab")
    async def cmd_vocab(self, event: AstrMessageEvent):
        """手动获取一个单词卡片（不计入学习进度）"""
        if not self._check_rate_limit(event):
            yield event.plain_result(_RATE_LIMIT_MSG)
            return

        try:
            async with self._workflow_lock:
                word = await self._select_word(update_progress=False)
                render_spec = self._prepare_card_render(word) if word else None
            if render_spec is None:
                yield event.plain_result("没有可用的单词数据")
                return
            html_content, image_path, width, height = render_spec
            await self._render_card_file(html_content, image_path, width, height)
            yield event.image_result(image_path)
            self._schedule_image_cleanup(image_path)
        except Exception as e:
            logger.error(f"生成卡片失败: {e}\n{traceback.format_exc()}")
            yield event.plain_result("❌ 生成卡片失败，请查看日志")

    @filter.command("vocab_status")
    async def cmd_status(self, event: AstrMessageEvent):
        """查看学习进度"""
        total = len(self.words)
        sent_set = set(self.progress.get("sent_words", []))
        sent = sum(1 for w in self.words if self._word_key(w) in sent_set)
        percent = sent * 100 // total if total > 0 else 0
        last_date = self.progress.get("last_push_date", "未知")
        push_time = self.config.get("push_time_send", "08:00")

        msg = f"""📊 单词学习进度
━━━━━━━━━━━━━━━━
📌 当前卡组: {self.current_language}
✅ 已学习: {sent} 个
📚 总词汇: {total} 个
📈 完成度: {percent}%
📅 最后推送: {last_date}
⏰ 每日推送: {push_time}
💡 /vocab 即时卡片不计入进度
━━━━━━━━━━━━━━━━"""
        yield event.plain_result(msg)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("vocab_register")
    async def cmd_register(self, event: AstrMessageEvent):
        """在当前会话注册接收每日单词推送（管理员）"""
        umo = event.unified_msg_origin
        async with self._get_config_lock():
            target_groups = list(self.config.get("target_groups", []) or [])
            if umo in target_groups:
                already_registered = True
                push_time = ""
            else:
                already_registered = False
                target_groups.append(umo)
                self.config["target_groups"] = target_groups
                await self._save_plugin_config()
                self._schedule_wakeup.set()
                push_time = self.config.get("push_time_send", "08:00")

        if already_registered:
            yield event.plain_result("当前会话已注册过了 ✅")
            return

        yield event.plain_result(f"注册成功！🎉\n将在每天 {push_time} 推送单词卡片")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("vocab_unregister")
    async def cmd_unregister(self, event: AstrMessageEvent):
        """取消当前会话的每日单词推送（管理员）"""
        umo = event.unified_msg_origin
        async with self._get_config_lock():
            target_groups = list(self.config.get("target_groups", []) or [])
            if umo not in target_groups:
                not_registered = True
            else:
                not_registered = False
                target_groups.remove(umo)
                self.config["target_groups"] = target_groups
                await self._save_plugin_config()

        if not_registered:
            yield event.plain_result("当前会话未注册 ❌")
            return

        yield event.plain_result("已取消注册 👋")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("vocab_test")
    async def cmd_test_push(self, event: AstrMessageEvent, delay_seconds: str = "0"):
        """
        测试推送功能（管理员）

        用法：
        - /vocab_test          # 立即生成并发送到当前会话（快速测试）
        - /vocab_test 60       # 60秒后执行完整定时推送流程（最长 300 秒）
        """
        # 参数解析 + 上限（安全整数转换，兼容 Unicode 数字和 null）
        try:
            delay = (
                int(delay_seconds)
                if isinstance(delay_seconds, (str, int, float))
                else 0
            )
            if delay < 0:
                delay = 0
        except (ValueError, TypeError):
            delay = 0
        if delay > MAX_TEST_DELAY_SECONDS:
            yield event.plain_result(
                f"❌ 延迟过长，最大允许 {MAX_TEST_DELAY_SECONDS} 秒"
            )
            return

        # 快速测试模式（delay=0）：渲染 HTML 准备就绪后释放锁，耗时截图在锁外执行
        if delay == 0:
            try:
                async with self._workflow_lock:
                    word = await self._select_word(update_progress=False)
                    render_spec = self._prepare_card_render(word) if word else None
                if render_spec is None:
                    yield event.plain_result("没有可用的单词")
                    return
                html_content, image_path, width, height = render_spec
                await self._render_card_file(html_content, image_path, width, height)

                # 发送到当前会话
                yield event.plain_result(f"📚 测试单词: {word.word}")
                yield event.image_result(image_path)

                # 延迟清理，避免与平台异步上传产生竞态
                self._schedule_image_cleanup(image_path)

            except Exception as e:
                logger.error(f"测试推送失败: {e}\n{traceback.format_exc()}")
                yield event.plain_result(f"❌ 测试失败: {e}")

        # 完整定时测试模式（delay>0）：只向本次推送传入当前会话作为附加目标，
        # 不原地修改全局 config["target_groups"]，避免与 /vocab_register 竞态。
        else:
            original_targets = list(self.config.get("target_groups", []) or [])
            umo = event.unified_msg_origin
            extra = [] if umo in original_targets else [umo]

            if extra:
                yield event.plain_result("✅ 本次测试将额外推送到当前会话")
            else:
                yield event.plain_result("ℹ️ 当前会话已注册")

            now = get_beijing_time()
            target_time = now + datetime.timedelta(seconds=delay)
            yield event.plain_result(f"⏰ 将在 {delay} 秒后执行推送")
            yield event.plain_result(f"📅 目标时间: {target_time.strftime('%H:%M:%S')}")

            async def _delayed_push():
                try:
                    await asyncio.sleep(delay)

                    async with self._workflow_lock:
                        today_str = get_beijing_time().strftime("%Y-%m-%d")
                        if self._last_check_date != today_str:
                            self._remove_cached_file(self._cached_image_path)
                            self._today_generated = False
                            self._today_pushed = False
                            self._cached_image_path = None
                            self._current_word = None
                            self._push_succeeded_umos = set()
                            self._last_check_date = today_str

                        if self._today_pushed:
                            logger.info("vocab_test 延迟推送：今日已推送，跳过")
                            return

                        logger.info("vocab_test 延迟推送开始...")
                        generated = await self._generate_daily_card()
                        if not generated or not self._cached_image_path:
                            logger.error("vocab_test 延迟推送：卡片生成失败")
                            return
                        self._today_generated = True

                        result = await self._push_daily_card(extra_targets=extra)
                        self._today_pushed = (
                            result.attempted_count > 0
                            and result.success_count == result.attempted_count
                        )
                        await self._persist_schedule_state()
                    logger.info(
                        f"vocab_test 延迟推送完成：{result.success_count}/{result.attempted_count}"
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error(f"vocab_test 延迟推送失败:\n{traceback.format_exc()}")

            task = asyncio.get_running_loop().create_task(_delayed_push())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            yield event.plain_result(f"✅ 已安排 {delay} 秒后的延迟推送")

    @filter.command("vocab_preview")
    async def cmd_preview(self, event: AstrMessageEvent, word_input: str = ""):
        """
        预览单词卡片效果（调试用，不计入进度）
        用法: /vocab_preview [单词]
        不带参数则随机选一个单词
        """
        custom_rate_limiter = "_check_rate_limit" in self.__dict__
        if custom_rate_limiter:
            if not self._check_rate_limit(event):
                yield event.plain_result(_RATE_LIMIT_MSG)
                return
        elif not self._check_rate_limit(event, record=False):
            yield event.plain_result(_RATE_LIMIT_MSG)
            return

        raw_msg = ""
        try:
            full_str = event.get_message_str()
            if isinstance(full_str, str):
                m = re.search(
                    r"(?:^|\s)\S*vocab_preview(?:@\S+)?(?:\s+(.*))?$",
                    full_str.strip(),
                )
                if m and m.group(1):
                    raw_msg = m.group(1).strip()
        except Exception:
            raw_msg = ""
        query = (raw_msg or word_input or "").strip()

        error_msg = None
        info_msg = ""
        render_spec = None
        async with self._workflow_lock:
            if query:
                lowered = query.lower()
                matches = [
                    w
                    for w in self.words
                    if self._word_key(w).lower() == lowered
                    or w.word.lower() == lowered
                    or (w.phonetic and w.phonetic.lower() == lowered)
                ]
                if not matches:
                    error_msg = f"未找到单词: {query}"
                else:
                    sent_set = set(self.progress.get("sent_words", []))
                    word = next(
                        (w for w in matches if self._word_key(w) not in sent_set),
                        matches[0],
                    )
                    render_spec = self._prepare_card_render(word)
            else:
                word = await self._select_word(update_progress=False)
                if not word:
                    error_msg = "没有可用的单词数据"
                else:
                    render_spec = self._prepare_card_render(word)

            if render_spec is not None and not custom_rate_limiter:
                if not self._check_rate_limit(event, record=True):
                    error_msg = _RATE_LIMIT_MSG
                    render_spec = None

            if render_spec is not None:
                example_preview = (word.example or "")[:50]
                info_msg = f"""🔍 单词预览
━━━━━━━━━━━━━━━━━━━━
📝 单词: {word.word}
🔊 音标: {word.phonetic or ""}
📚 词性: {word.pos or ""}
📖 释义: {word.definition}
💬 例句: {example_preview}...
━━━━━━━━━━━━━━━━━━━━
⏳ 正在生成卡片图片..."""

        if error_msg is not None:
            yield event.plain_result(error_msg)
            return

        yield event.plain_result(info_msg)

        html_content, image_path, width, height = render_spec
        try:
            await self._render_card_file(html_content, image_path, width, height)
        except Exception as e:
            logger.error(f"Preview failed: {traceback.format_exc()}")
            yield event.plain_result(f"❌ 生成失败: {e}")
            return

        yield event.plain_result("✅ 图片生成成功！")
        yield event.image_result(image_path)
        self._schedule_image_cleanup(image_path)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("vocab_now")
    async def cmd_push_now(self, event: AstrMessageEvent):
        """立即执行一次完整的生成+推送流程（管理员）"""
        yield event.plain_result("🚀 开始执行完整推送流程...")

        # 检查是否有注册的群
        target_groups = self.config.get("target_groups", [])
        if not target_groups:
            yield event.plain_result(
                "⚠️ 没有已注册的推送目标，请先使用 /vocab_register 注册"
            )
            return

        yield event.plain_result(f"📋 已注册 {len(target_groups)} 个推送目标")

        try:
            yield event.plain_result("⏳ 步骤1: 生成单词卡片...")
            async with self._workflow_lock:
                today_str = get_beijing_time().strftime("%Y-%m-%d")
                if self._last_check_date != today_str:
                    self._remove_cached_file(self._cached_image_path)
                    self._today_generated = False
                    self._today_pushed = False
                    self._cached_image_path = None
                    self._current_word = None
                    self._push_succeeded_umos = set()
                    self._last_check_date = today_str

                generated = await self._generate_daily_card()
                if generated and self._cached_image_path:
                    self._today_generated = True
                    self._today_pushed = False
                    await self._persist_schedule_state()
                word_label = self._current_word.word if self._current_word else "?"

            if not generated or not self._cached_image_path:
                yield event.plain_result("❌ 卡片生成失败")
                return

            yield event.plain_result(f"✅ 卡片已生成: {word_label}")
            yield event.plain_result("⏳ 步骤2: 推送到所有已注册群聊...")

            async with self._workflow_lock:
                result = await self._push_daily_card()
                self._today_pushed = (
                    result.attempted_count > 0
                    and result.success_count == result.attempted_count
                )
                await self._persist_schedule_state()

            yield event.plain_result(
                f"✅ 推送完成：{result.success_count}/{result.attempted_count}"
            )

        except Exception as e:
            logger.error(f"Push now failed: {traceback.format_exc()}")
            yield event.plain_result(f"❌ 推送失败: {e}")

    @filter.command("vocab_lang")
    async def cmd_switch_language(self, event: AstrMessageEvent, lang_id: str = ""):
        """
        切换语种
        用法: /vocab_lang [语种ID]
        不带参数则显示当前语种和可用语种列表
        切换需管理员权限
        """
        if not lang_id:
            # 显示当前语种和可用语种（公开）
            available = self.lang_manager.list_languages()
            current = self.current_language

            msg = f"""🌐 语种管理
━━━━━━━━━━━━━━━━
📌 当前语种: {current}
━━━━━━━━━━━━━━━━
可用语种:
"""
            for lang in available:
                marker = "✅" if lang["id"] == current else "  "
                msg += f"{marker} {lang['id']} - {lang['name']}\n"

            msg += "━━━━━━━━━━━━━━━━\n"
            msg += "用法: /vocab_lang <语种ID>（切换需管理员）"
            yield event.plain_result(msg)
            return

        # 切换语种需要管理员（失败时默认拒绝，避免权限绕过）
        is_admin = False
        try:
            is_admin = bool(event.is_admin())
        except Exception as e:
            logger.warning(f"is_admin 检查失败，拒绝切换语种: {e}")
            is_admin = False
        if not is_admin:
            yield event.plain_result("❌ 切换语种需要管理员权限")
            return

        # 切换语种
        try:
            # 检查语种是否已注册
            if not self.lang_manager.is_registered(lang_id):
                yield event.plain_result(
                    f"❌ 语种 '{lang_id}' 未注册\n请使用 /vocab_lang 查看可用语种"
                )
                return

            async with self._get_config_lock():
                async with self._workflow_lock:
                    new_handler = self.lang_manager.get_handler(lang_id)
                    self.current_language = lang_id
                    self.current_handler = new_handler
                    self.words = self._load_words()
                    self.progress = self._load_progress()

                    self._remove_cached_file(self._cached_image_path)
                    self._cached_image_path = None
                    self._current_word = None
                    self._today_generated = False
                    self._today_pushed = False
                    self._push_succeeded_umos = set()
                    self._scheduler_consecutive_failures = 0
                    await self._persist_schedule_state()
                    loaded_count = len(self.words)

                # 保存配置并唤醒调度器（与状态切换同受配置锁串行保护）
                self.config["current_language"] = lang_id
                await self._save_plugin_config()
                self._schedule_wakeup.set()

            yield event.plain_result(
                f"✅ 已切换到语种: {lang_id}\n📚 已加载 {loaded_count} 个单词"
            )

        except Exception as e:
            logger.error(f"切换语种失败: {e}")
            yield event.plain_result(f"❌ 切换失败: {e}")

    @filter.command("vocab_help")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        push_time = self.config.get("push_time_send", "08:00")
        help_msg = f"""📚 每日单词卡片插件帮助
━━━━━━━━━━━━━━━━━━━━
/vocab - 立即获取卡片（不计入进度）
/vocab_preview [单词] - 预览卡片效果
/vocab_status - 查看学习进度
/vocab_lang - 查看当前与可用卡组
/vocab_help - 显示此帮助
━━━━━━━━━━━━━━━━━━━━
管理员命令:
/vocab_register - 注册每日推送
/vocab_unregister - 取消每日推送
/vocab_now - 立即执行推送流程
/vocab_test [秒] - 测试推送（最长 {MAX_TEST_DELAY_SECONDS}s）
/vocab_lang <语种ID> - 切换卡组
━━━━━━━━━━━━━━━━━━━━
💡 注册后每天 {push_time} 自动推送
📌 当前卡组: {self.current_language}"""
        yield event.plain_result(help_msg)

    async def terminate(self):
        """Cancel scheduler and release browser resources on plugin unload"""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        # 取消所有后台任务（延迟推送、图片清理等）
        for t in self._background_tasks:
            if not t.done():
                t.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        try:
            await self._image_renderer.close()
        except Exception as e:
            logger.warning(f"Failed to close ImageRenderer: {e}")
        logger.info("VocabCard plugin unloaded")
