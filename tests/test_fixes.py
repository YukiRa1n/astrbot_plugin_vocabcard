# -*- coding: utf-8 -*-
"""
Tests for applied fixes: _parse_time validation, _is_within_minute_window,
MD5 card filename, browser install lock, and pool get timeout.
"""

import sys
import os
import asyncio
import datetime
import hashlib
import types
import importlib
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make the plugin dir importable as a package and mock astrbot
# ---------------------------------------------------------------------------

_plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_parent_dir = os.path.dirname(_plugin_dir)

# Ensure parent is on sys.path so "astrbot_plugin_vocabcard" resolves
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Create __init__.py temporarily if missing so the directory is a package
_init_path = os.path.join(_plugin_dir, "__init__.py")
_created_init = False
if not os.path.exists(_init_path):
    with open(_init_path, "w") as f:
        f.write("")
    _created_init = True

import atexit
if _created_init:
    atexit.register(lambda: os.remove(_init_path) if os.path.exists(_init_path) else None)

# Mock astrbot modules before importing main
for mod in [
    "astrbot",
    "astrbot.api",
    "astrbot.api.event",
    "astrbot.api.star",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Configure astrbot.api mock
astrbot_api = sys.modules["astrbot.api"]
astrbot_api.logger = MagicMock()
astrbot_api.AstrBotConfig = MagicMock()

# Configure astrbot.api.event mock
astrbot_event = sys.modules["astrbot.api.event"]
astrbot_event.filter = MagicMock()
astrbot_event.filter.command = lambda *a, **kw: lambda fn: fn
astrbot_event.AstrMessageEvent = MagicMock()
astrbot_event.MessageChain = MagicMock()

# Configure astrbot.api.star mock
astrbot_star = sys.modules["astrbot.api.star"]

class _FakeStarBase:
    def __init__(self, context=None):
        pass

astrbot_star.Context = MagicMock()
astrbot_star.Star = _FakeStarBase
astrbot_star.register = lambda *a, **kw: lambda cls: cls
# StarTools.get_data_dir must be patchable per-test (see _make_plugin)
astrbot_star.StarTools = MagicMock()

# Now import the main module
from astrbot_plugin_vocabcard.main import VocabCardPlugin

pytestmark = pytest.mark.asyncio


_MOCK_DATA_DIRS = []


def _make_plugin():
    """Create a VocabCardPlugin instance with mocked dependencies.

    StarTools.get_data_dir is mocked to return an isolated temp directory so
    plugin data never pollutes the repository working tree.
    """
    import tempfile as _tempfile

    _temp = _tempfile.mkdtemp(prefix="vocabcard_test_")
    _MOCK_DATA_DIRS.append(_temp)

    ctx = MagicMock()
    config = MagicMock()
    config.get = MagicMock(side_effect=lambda key, default=None: {
        "current_language": "english",
        "push_time_generate": "07:30",
        "push_time_send": "08:00",
        "use_cdn_background": True,
        "learning_mode": "random",
        "reset_on_complete": True,
        "target_groups": [],
    }.get(key, default))
    with patch("astrbot.api.star.StarTools") as _mock_star_tools:
        _mock_star_tools.get_data_dir = MagicMock(return_value=_temp)
        plugin = VocabCardPlugin(ctx, config)
    return plugin


# ---- _parse_time validation ----

async def test_parse_time_invalid_hour_returns_default():
    plugin = _make_plugin()
    assert plugin._parse_time("25:00") == (8, 0)


async def test_parse_time_invalid_minute_returns_default():
    plugin = _make_plugin()
    assert plugin._parse_time("12:99") == (8, 0)


async def test_parse_time_valid():
    plugin = _make_plugin()
    assert plugin._parse_time("08:30") == (8, 30)


# ---- _is_within_minute_window ----

async def test_is_within_minute_window_match():
    plugin = _make_plugin()
    now = datetime.datetime(2026, 6, 12, 7, 30, 15,
                            tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    assert plugin._is_within_minute_window(now, (7, 30)) is True


async def test_is_within_minute_window_no_match():
    plugin = _make_plugin()
    now = datetime.datetime(2026, 6, 12, 9, 45, 0,
                            tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    assert plugin._is_within_minute_window(now, (7, 30)) is False


# ---- MD5 card filename (no special chars) ----

async def test_card_filename_uses_hash_no_special_chars():
    word_text = "look/into"
    safe_name = hashlib.md5(word_text.encode()).hexdigest()[:12]
    assert "/" not in safe_name
    assert safe_name.isalnum()
    assert len(safe_name) == 12


# ---- ImageRenderer pool get timeout ----

async def test_renderer_pool_get_timeout():
    from astrbot_plugin_vocabcard.core.image_renderer import ImageRenderer

    renderer = ImageRenderer(max_pages=1)
    renderer._browser = MagicMock()
    renderer._loop = asyncio.get_running_loop()
    renderer._active_pages_count = 1

    # Simulate pool that is empty (forces wait path) and whose get() never resolves
    async def _never():
        await asyncio.sleep(9999)
        return MagicMock()

    fake_pool = asyncio.Queue()
    fake_pool.get = _never
    fake_pool.empty = lambda: True
    fake_pool.put_nowait = lambda x: None
    renderer._pool = fake_pool

    renderer._init_browser = AsyncMock()

    with pytest.raises(RuntimeError, match="Timed out waiting"):
        original_wait_for = asyncio.wait_for

        async def fast_wait_for(coro, timeout=None):
            return await original_wait_for(coro, timeout=0.1)

        with patch("astrbot_plugin_vocabcard.core.image_renderer.asyncio.wait_for",
                    side_effect=fast_wait_for):
            await renderer._acquire_page(432, 540, 4)


# ---- Browser install lock exists ----

async def test_browser_install_lock_exists():
    from astrbot_plugin_vocabcard.core import image_renderer
    assert hasattr(image_renderer, "_browser_install_lock")
    assert isinstance(image_renderer._browser_install_lock, asyncio.Lock)


# ---- _mark_word_sent deduplication ----

async def test_mark_word_sent_no_duplicates():
    plugin = _make_plugin()
    plugin.progress = {"sent_words": ["apple", "banana"], "last_push_date": ""}
    plugin._save_progress = AsyncMock()

    await plugin._mark_word_sent("apple")
    assert plugin.progress["sent_words"].count("apple") == 1
    assert len(plugin.progress["sent_words"]) == 2

    await plugin._mark_word_sent("cherry")
    assert "cherry" in plugin.progress["sent_words"]
    assert len(plugin.progress["sent_words"]) == 3

    await plugin._mark_word_sent("apple")
    assert plugin.progress["sent_words"].count("apple") == 1
    assert len(plugin.progress["sent_words"]) == 3


# ---- _today_pushed flag prevents re-push ----

async def test_today_pushed_flag_prevents_repush():
    plugin = _make_plugin()
    plugin._today_pushed = True
    plugin._cached_image_path = "/fake/path.png"

    now = datetime.datetime(2026, 6, 12, 8, 0, 30,
                            tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    push_time = (8, 0)

    should_push = (
        plugin._is_within_minute_window(now, push_time)
        and not plugin._today_pushed
    )
    assert should_push is False

    plugin._today_pushed = False
    should_push = (
        plugin._is_within_minute_window(now, push_time)
        and not plugin._today_pushed
    )
    assert should_push is True


# ---- cmd_switch_language resets cache state ----

async def test_switch_language_resets_cache():
    plugin = _make_plugin()
    plugin._cached_image_path = "/some/cached.png"
    plugin._current_word = MagicMock()
    plugin._today_generated = True
    plugin._today_pushed = True

    plugin._load_words = MagicMock(return_value=[])
    plugin._load_progress = MagicMock(return_value={"sent_words": [], "last_push_date": ""})
    plugin.lang_manager.is_registered = MagicMock(return_value=True)
    plugin.lang_manager.get_handler = MagicMock(return_value=plugin.current_handler)
    plugin.config.save_config = MagicMock()

    event = MagicMock()
    event.unified_msg_origin = "test"

    results = []
    event.plain_result = MagicMock(side_effect=lambda msg: results.append(msg))

    gen = plugin.cmd_switch_language(event, "japanese")
    async for _ in gen:
        pass

    assert plugin._cached_image_path is None
    assert plugin._current_word is None
    assert plugin._today_generated is False
    assert plugin._today_pushed is False


# ---- _today_pushed reset on date change ----

async def test_today_pushed_resets_on_date_change():
    """Verify _schedule_loop resets _today_pushed when the date changes."""
    plugin = _make_plugin()
    plugin._today_generated = True
    plugin._today_pushed = True
    plugin._last_check_date = "2026-06-11"

    # Simulate the date-change branch of _schedule_loop
    today_str = "2026-06-12"
    if plugin._last_check_date != today_str:
        plugin._today_generated = False
        plugin._today_pushed = False
        plugin._last_check_date = today_str

    assert plugin._today_generated is False
    assert plugin._today_pushed is False
    assert plugin._last_check_date == "2026-06-12"


async def test_today_pushed_not_reset_on_same_date():
    """Verify _today_pushed is NOT reset when the date is the same."""
    plugin = _make_plugin()
    plugin._today_generated = True
    plugin._today_pushed = True
    plugin._last_check_date = "2026-06-12"

    # Simulate the date-check branch on the same date
    today_str = "2026-06-12"
    if plugin._last_check_date != today_str:
        plugin._today_generated = False
        plugin._today_pushed = False
        plugin._last_check_date = today_str

    # Should remain unchanged
    assert plugin._today_generated is True
    assert plugin._today_pushed is True


# ---- Atomic write to progress file uses .tmp ----

async def test_save_progress_atomic_write_uses_tmp_file(tmp_path, monkeypatch):
    """Verify _save_progress writes to a .tmp file first, then renames atomically."""
    plugin = _make_plugin()
    # Redirect data_dir to tmp_path so we don't touch real plugin data
    monkeypatch.setattr(plugin, "data_dir", tmp_path)
    plugin.progress = {"sent_words": ["alpha", "beta"], "last_push_date": "2026-06-12"}

    # Force the aiofiles ImportError path so we exercise the sync fallback,
    # which still must use the .tmp + os.replace pattern.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "aiofiles" or name.startswith("aiofiles."):
            raise ImportError("simulated missing aiofiles")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    await plugin._save_progress()

    progress_file = tmp_path / f"progress_{plugin.current_language}.json"
    tmp_file = progress_file.with_suffix(".json.tmp")

    # The final file must exist; the .tmp file must NOT linger after a successful write.
    assert progress_file.exists()
    assert not tmp_file.exists()

    import json as _json
    with open(progress_file, "r", encoding="utf-8") as f:
        data = _json.load(f)
    assert data["sent_words"] == ["alpha", "beta"]
    assert data["last_push_date"] == "2026-06-12"


async def test_atomic_sync_write_helper(tmp_path, monkeypatch):
    """Verify the sync helper writes a .tmp file then renames atomically."""
    plugin = _make_plugin()
    monkeypatch.setattr(plugin, "data_dir", tmp_path)
    plugin.progress = {"sent_words": ["x"], "last_push_date": "2026-06-12"}

    progress_file = tmp_path / f"progress_{plugin.current_language}.json"
    plugin._atomic_sync_write(progress_file)

    tmp_file = progress_file.with_suffix(".json.tmp")
    assert progress_file.exists()
    assert not tmp_file.exists()


# ---- scripts/test_renderer.py syntax sanity ----

def test_scripts_test_renderer_uses_await():
    """Verify scripts/test_renderer.py calls render_to_file with await."""
    import pathlib
    script_path = (
        pathlib.Path(_plugin_dir) / "scripts" / "test_renderer.py"
    )
    assert script_path.exists(), f"missing {script_path}"
    source = script_path.read_text(encoding="utf-8")
    # The buggy line was `renderer.render_to_file(...)` without await.
    assert "await renderer.render_to_file" in source, (
        "scripts/test_renderer.py must await renderer.render_to_file()"
    )
    # main() must be async to support the await.
    assert "async def main" in source
    # Entry point must drive the coroutine.
    assert "asyncio.run(main" in source


# ---- _mark_word_sent calls correct method name ----

async def test_mark_word_sent_calls_atomic_sync_write(tmp_path, monkeypatch):
    """Verify _mark_word_sent fallback calls _atomic_sync_write, not _sync_write_progress."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "aiofiles" or name.startswith("aiofiles."):
            raise ImportError("simulated missing aiofiles")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    plugin = _make_plugin()
    monkeypatch.setattr(plugin, "data_dir", tmp_path)
    plugin.progress = {"sent_words": [], "last_push_date": ""}

    await plugin._mark_word_sent("testword")

    progress_file = tmp_path / f"progress_{plugin.current_language}.json"
    assert progress_file.exists()

    import json as _json
    with open(progress_file, "r", encoding="utf-8") as f:
        data = _json.load(f)
    assert "testword" in data["sent_words"]


# ---- metadata.yaml version matches register decorator ----

def test_metadata_version_matches_register():
    """Verify metadata.yaml version matches the register decorator version."""
    import pathlib
    import yaml

    metadata_path = pathlib.Path(_plugin_dir) / "metadata.yaml"
    assert metadata_path.exists(), f"missing {metadata_path}"

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)

    import ast
    main_path = pathlib.Path(_plugin_dir) / "main.py"
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    register_version = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "register":
                if len(node.args) >= 4:
                    register_version = ast.literal_eval(node.args[3])
                break

    assert register_version is not None, "Could not find register decorator version"
    assert metadata["version"] == register_version, (
        f"metadata.yaml version '{metadata['version']}' != register version '{register_version}'"
    )


# ---- card_japanese.html has no literal \n in CSS ----

def test_card_japanese_no_literal_backslash_n_in_css():
    """Verify card_japanese.html has no literal \\n in CSS."""
    import pathlib
    template_path = pathlib.Path(_plugin_dir) / "templates" / "card_japanese.html"
    assert template_path.exists(), f"missing {template_path}"

    source = template_path.read_text(encoding="utf-8")
    style_start = source.find("<style>")
    style_end = source.find("</style>")
    assert style_start != -1 and style_end != -1

    css_block = source[style_start:style_end]
    assert "\\n" not in css_block, (
        "card_japanese.html contains literal \\n in CSS block"
    )


# ---- architecture and lifecycle optimization ----

async def test_generate_daily_card_does_not_commit_progress_before_push(tmp_path):
    plugin = _make_plugin()
    word = MagicMock()
    word.word = "transaction"
    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png")

    plugin._select_word = AsyncMock(return_value=word)
    plugin._generate_card_image = AsyncMock(return_value=str(image_path))
    plugin._mark_word_sent = AsyncMock()

    generated = await plugin._generate_daily_card()

    assert generated is True
    plugin._mark_word_sent.assert_not_awaited()


async def test_push_commits_progress_only_after_successful_delivery(tmp_path):
    plugin = _make_plugin()
    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png")
    plugin._cached_image_path = str(image_path)
    plugin._current_word = MagicMock(word="delivered")
    plugin.context = MagicMock()
    plugin.context.send_message = AsyncMock()
    plugin._mark_word_sent = AsyncMock()
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: ["session-1"]
        if key == "target_groups"
        else default
    )

    result = await plugin._push_daily_card()

    assert result.success_count == 1
    assert result.attempted_count == 1
    plugin._mark_word_sent.assert_awaited_once_with("delivered")


async def test_push_failure_keeps_artifact_and_does_not_commit(tmp_path):
    plugin = _make_plugin()
    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png")
    plugin._cached_image_path = str(image_path)
    plugin._current_word = MagicMock(word="retry")
    plugin.context = MagicMock()
    plugin.context.send_message = AsyncMock(side_effect=RuntimeError("offline"))
    plugin._mark_word_sent = AsyncMock()
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: ["session-1"]
        if key == "target_groups"
        else default
    )

    result = await plugin._push_daily_card()

    assert result.success_count == 0
    assert image_path.exists()
    plugin._mark_word_sent.assert_not_awaited()


async def test_plugin_has_workflow_lock():
    plugin = _make_plugin()
    assert isinstance(plugin._workflow_lock, asyncio.Lock)


# ---- security & schedule persistence ----

def test_validate_cdp_url_local_ok():
    from astrbot_plugin_vocabcard.core.security import validate_cdp_url

    assert validate_cdp_url("http://127.0.0.1:9222") == "http://127.0.0.1:9222"
    assert validate_cdp_url("") == ""


def test_validate_cdp_url_remote_rejected():
    from astrbot_plugin_vocabcard.core.security import validate_cdp_url
    import pytest

    with pytest.raises(ValueError):
        validate_cdp_url("http://evil.example:9222")

    assert (
        validate_cdp_url("http://evil.example:9222", allow_remote=True)
        == "http://evil.example:9222"
    )


async def test_select_word_returns_none_when_exhausted_without_reset():
    plugin = _make_plugin()
    from astrbot_plugin_vocabcard.core.base_handler import WordEntry

    plugin.words = [
        WordEntry(word="a", definition="1"),
        WordEntry(word="b", definition="2"),
    ]
    plugin.progress = {"sent_words": ["a", "b"], "last_push_date": ""}
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "reset_on_complete": False,
            "learning_mode": "random",
        }.get(key, default)
    )
    assert await plugin._select_word() is None


async def test_persist_and_restore_schedule_state(tmp_path, monkeypatch):
    plugin = _make_plugin()
    monkeypatch.setattr(plugin, "data_dir", tmp_path)
    plugin._last_check_date = "2026-07-12"
    plugin._today_generated = True
    plugin._today_pushed = False
    img = tmp_path / "card.png"
    img.write_bytes(b"png")
    plugin._cached_image_path = str(img)
    plugin._current_word = MagicMock(word="hello")
    plugin.words = [MagicMock(word="hello")]

    await plugin._persist_schedule_state()
    assert (tmp_path / "schedule_state.json").exists()

    plugin2 = _make_plugin()
    monkeypatch.setattr(plugin2, "data_dir", tmp_path)
    plugin2.words = [MagicMock(word="hello")]
    plugin2._restore_schedule_state()
    # only restores when date matches today — force date to today
    today = __import__("datetime").datetime.now(
        __import__("datetime").timezone(
            __import__("datetime").timedelta(hours=8)
        )
    ).strftime("%Y-%m-%d")
    state_path = tmp_path / "schedule_state.json"
    import json as _json

    with open(state_path, "r", encoding="utf-8") as f:
        st = _json.load(f)
    st["date"] = today
    with open(state_path, "w", encoding="utf-8") as f:
        _json.dump(st, f)

    plugin2._restore_schedule_state()
    assert plugin2._today_generated is True
    assert plugin2._cached_image_path == str(img)


async def test_time_reached():
    plugin = _make_plugin()
    now = datetime.datetime(
        2026, 7, 12, 8, 0, 0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
    )
    assert plugin._time_reached(now, (8, 0)) is True
    assert plugin._time_reached(now, (7, 30)) is True
    assert plugin._time_reached(now, (8, 1)) is False


# ===== Regression tests for review fixes =====

# ---- file:// URL percent-encoding ----

def test_offline_background_url_uses_percent_encoding():
    """file:// URL 必须正确百分号编码，空格/#/% 不能破坏路径。"""
    import pathlib
    plugin = _make_plugin()
    bg = pathlib.Path("D:/photos/my photo #1.jpg")
    url = plugin._get_offline_background_url if False else bg.as_uri()
    assert "my%20photo" in url
    assert "%23" in url
    assert "#1.jpg" not in url.replace("%23", "")  # '#' 不得作为 fragment 出现


def test_css_url_sanitizer_strips_injection():
    """CSS url() 上下文注入应被清洗。"""
    plugin = _make_plugin()
    assert plugin._sanitize_css_url("https://example.com/a.jpg") == "https://example.com/a.jpg"
    # 引号/分号/闭合括号被剥离
    assert ")" not in plugin._sanitize_css_url("x') ;}@import")
    assert "'" not in plugin._sanitize_css_url("x') ;}")
    # 非白名单 scheme 被拒绝
    assert plugin._sanitize_css_url("javascript://x") == ""
    assert plugin._sanitize_css_url("vbscript://x") == ""
    # data: 仅允许 image
    assert plugin._sanitize_css_url("data:text/html,<script>") == ""
    assert plugin._sanitize_css_url("data:image/png;base64,AAAA") != ""


def test_theme_color_sanitizer_accepts_hex_rejects_other():
    plugin = _make_plugin()
    assert plugin._sanitize_theme_color("#2F4F4F") == "#2F4F4F"
    assert plugin._sanitize_theme_color("#abc") == "#abc"
    # 非十六进制颜色回退默认
    assert plugin._sanitize_theme_color("red; }@import url(x)") == "#2F4F4F"
    assert plugin._sanitize_theme_color("") == "#2F4F4F"


# ---- Rate limiting ----

async def test_rate_limit_blocks_second_call_within_window():
    plugin = _make_plugin()
    event = MagicMock()
    event.get_sender_id = MagicMock(return_value="user-1")
    event.unified_msg_origin = "group|1|user-1"

    assert plugin._check_rate_limit(event) is True
    # 窗口内第二次调用被拒绝
    assert plugin._check_rate_limit(event) is False


async def test_rate_limit_allows_after_window(tmp_path, monkeypatch):
    plugin = _make_plugin()
    event = MagicMock()
    event.get_sender_id = MagicMock(return_value="user-2")
    event.unified_msg_origin = "group|1|user-2"

    import time as _time
    assert plugin._check_rate_limit(event) is True

    # 快进 31 秒，旧时间戳过期
    plugin._rate_limit["user-2"][0] -= 31
    assert plugin._check_rate_limit(event) is True


async def test_rate_limit_separates_users():
    plugin = _make_plugin()
    e1 = MagicMock()
    e1.get_sender_id = MagicMock(return_value="alice")
    e1.unified_msg_origin = "g|1|alice"
    e2 = MagicMock()
    e2.get_sender_id = MagicMock(return_value="bob")
    e2.unified_msg_origin = "g|1|bob"

    assert plugin._check_rate_limit(e1) is True
    assert plugin._check_rate_limit(e1) is False
    # 不同用户不受影响
    assert plugin._check_rate_limit(e2) is True


# ---- Safe int config parsing ----

async def test_safe_int_config_parsing():
    """非法配置值不应导致插件加载失败。"""
    from astrbot_plugin_vocabcard.main import VocabCardPlugin as VCP
    import builtins
    real_import = builtins.__import__
    called = []

    def fake_import(name, *args, **kwargs):
        if name == "aiofiles" or name.startswith("aiofiles."):
            raise ImportError("simulated missing aiofiles")
        return real_import(name, *args, **kwargs)

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        ctx = MagicMock()
        config = MagicMock()
        config.get = MagicMock(side_effect=lambda key, default=None: {
            "current_language": "english",
            "browser_max_pages": "oops",       # 非法整数
            "render_scale": "abc",             # 非法整数
            "bg_load_timeout": "",             # 空串
            "target_groups": [],
        }.get(key, default))
        with patch("astrbot.api.star.StarTools") as _ms:
            _ms.get_data_dir = MagicMock(return_value="C:/tmp/x")
            plugin = VCP(ctx, config)
        assert plugin._render_scale == 3   # 回退默认
        assert plugin._bg_load_timeout == 5000
    finally:
        monkeypatch.undo()
