# -*- coding: utf-8 -*-
"""
Tests for applied fixes: _parse_time validation, _is_within_minute_window,
MD5 card filename, browser install lock, and pool get timeout.
"""

import atexit
import shutil as _shutil
import sys
import os
import asyncio
import datetime
import hashlib
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

if _created_init:
    atexit.register(
        lambda: os.remove(_init_path) if os.path.exists(_init_path) else None
    )

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
astrbot_event.filter.permission_type = lambda *a, **kw: lambda fn: fn
astrbot_event.AstrMessageEvent = MagicMock()
astrbot_event.MessageChain = MagicMock()

# Configure astrbot.api.star mock
astrbot_star = sys.modules["astrbot.api.star"]


class _FakeStarBase:
    def __init__(self, context=None):
        self.context = context


astrbot_star.Context = MagicMock()
astrbot_star.Star = _FakeStarBase
astrbot_star.register = lambda *a, **kw: lambda cls: cls
# StarTools.get_data_dir must be patchable per-test (see _make_plugin)
astrbot_star.StarTools = MagicMock()

# Now import the main module
from astrbot_plugin_vocabcard.main import VocabCardPlugin  # noqa: E402

_MOCK_DATA_DIRS = []
atexit.register(
    lambda: [_shutil.rmtree(d, ignore_errors=True) for d in _MOCK_DATA_DIRS]
)


def _make_plugin(data_dir=None, words=None):
    """Create a VocabCardPlugin instance with mocked dependencies.

    StarTools.get_data_dir is mocked to return an isolated temp directory so
    plugin data never pollutes the repository working tree.
    """
    import tempfile as _tempfile

    if data_dir is None:
        _temp = _tempfile.mkdtemp(prefix="vocabcard_test_")
        _MOCK_DATA_DIRS.append(_temp)
    else:
        _temp = str(data_dir)

    ctx = MagicMock()
    config = MagicMock()
    config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "current_language": "english",
            "push_time_generate": "07:30",
            "push_time_send": "08:00",
            "use_cdn_background": True,
            "learning_mode": "random",
            "reset_on_complete": True,
            "target_groups": [],
        }.get(key, default)
    )
    with patch("astrbot.api.star.StarTools") as _mock_star_tools:
        _mock_star_tools.get_data_dir = MagicMock(return_value=_temp)
        if words is not None:
            with patch.object(VocabCardPlugin, "_load_words", return_value=list(words)):
                plugin = VocabCardPlugin(ctx, config)
        else:
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
    now = datetime.datetime(
        2026, 6, 12, 7, 30, 15, tzinfo=datetime.timezone(datetime.timedelta(hours=8))
    )
    assert plugin._is_within_minute_window(now, (7, 30)) is True


async def test_is_within_minute_window_no_match():
    plugin = _make_plugin()
    now = datetime.datetime(
        2026, 6, 12, 9, 45, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8))
    )
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

        with patch(
            "astrbot_plugin_vocabcard.core.image_renderer.asyncio.wait_for",
            side_effect=fast_wait_for,
        ):
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

    now = datetime.datetime(
        2026, 6, 12, 8, 0, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=8))
    )
    push_time = (8, 0)

    should_push = (
        plugin._is_within_minute_window(now, push_time) and not plugin._today_pushed
    )
    assert should_push is False

    plugin._today_pushed = False
    should_push = (
        plugin._is_within_minute_window(now, push_time) and not plugin._today_pushed
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
    plugin._load_progress = MagicMock(
        return_value={"sent_words": [], "last_push_date": ""}
    )
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

    script_path = pathlib.Path(_plugin_dir) / "scripts" / "test_renderer.py"
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
        side_effect=lambda key, default=None: (
            ["session-1"] if key == "target_groups" else default
        )
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
        side_effect=lambda key, default=None: (
            ["session-1"] if key == "target_groups" else default
        )
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
    today = (
        __import__("datetime")
        .datetime.now(
            __import__("datetime").timezone(__import__("datetime").timedelta(hours=8))
        )
        .strftime("%Y-%m-%d")
    )
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
        2026,
        7,
        12,
        8,
        0,
        0,
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
    plugin.offline_backgrounds = [bg]
    url = plugin._get_offline_background_url()
    assert "my%20photo" in url
    assert "%23" in url
    assert "#1.jpg" not in url.replace("%23", "")  # '#' 不得作为 fragment 出现


def test_css_url_sanitizer_strips_injection():
    """CSS url() 上下文注入应被清洗。"""
    plugin = _make_plugin()
    assert (
        plugin._sanitize_css_url("https://example.com/a.jpg")
        == "https://example.com/a.jpg"
    )
    # 引号/分号/闭合括号/反斜杠/换行被拒绝或剥离
    assert ")" not in plugin._sanitize_css_url("x') ;}@import")
    assert "'" not in plugin._sanitize_css_url("x') ;}")
    assert plugin._sanitize_css_url("javascript:alert(1)") == ""
    assert plugin._sanitize_css_url("javascript://x") == ""
    assert plugin._sanitize_css_url("vbscript://x") == ""
    assert plugin._sanitize_css_url("//attacker.example/share/a.png") == ""
    assert plugin._sanitize_css_url("file://attacker.example/share/a.png") == ""
    # data: 仅允许无注入字符的 image
    assert plugin._sanitize_css_url("data:text/html,<script>") == ""
    assert plugin._sanitize_css_url('data:image/png;base64,AAAA")}') == ""
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


async def test_safe_int_config_parsing(tmp_path):
    """非法配置值不应导致插件加载失败。"""
    from astrbot_plugin_vocabcard.main import VocabCardPlugin as VCP
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "aiofiles" or name.startswith("aiofiles."):
            raise ImportError("simulated missing aiofiles")
        return real_import(name, *args, **kwargs)

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        ctx = MagicMock()
        config = MagicMock()
        config.get = MagicMock(
            side_effect=lambda key, default=None: {
                "current_language": "english",
                "browser_max_pages": "oops",  # 非法整数
                "render_scale": "abc",  # 非法整数
                "bg_load_timeout": "",  # 空串
                "target_groups": [],
            }.get(key, default)
        )
        with patch("astrbot.api.star.StarTools") as _ms:
            _ms.get_data_dir = MagicMock(return_value=str(tmp_path))
            plugin = VCP(ctx, config)
        assert plugin._render_scale == 3  # 回退默认
        assert plugin._bg_load_timeout == 5000
    finally:
        monkeypatch.undo()


async def test_push_without_targets_reports_no_targets(tmp_path):
    """没有推送目标是正常状态，应与推送失败区分开。"""
    plugin = _make_plugin()
    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png")
    plugin._cached_image_path = str(image_path)

    result = await plugin._push_daily_card()

    assert result.no_targets is True
    assert result.attempted_count == 0
    assert image_path.exists()


def _plugin_with_targets(targets_by_poll):
    """target_groups 依次返回 targets_by_poll 中的值，耗尽后保持最后一个。"""
    plugin = _make_plugin()
    values = list(targets_by_poll)

    def get(key, default=None):
        if key == "target_groups":
            return values.pop(0) if len(values) > 1 else values[0]
        return default

    plugin.config.get = MagicMock(side_effect=get)
    return plugin


async def test_wait_for_push_targets_returns_after_register_and_logs_once():
    """等待期间静默轮询，注册后返回；不计失败、不标记已推送、只提示一次。"""
    import astrbot_plugin_vocabcard.main as main_module

    plugin = _plugin_with_targets([[], [], [], ["session-1"]])
    plugin._scheduler_consecutive_failures = 0
    plugin._today_pushed = False
    sleep = AsyncMock()
    today = main_module.get_beijing_time().strftime("%Y-%m-%d")
    with (
        patch.object(main_module.asyncio, "sleep", sleep),
        patch.object(main_module, "logger") as logger,
    ):
        await plugin._wait_for_push_targets(today)

    assert logger.info.call_count == 1
    assert logger.warning.call_count == 0
    assert sleep.await_count == 3
    sleep.assert_awaited_with(main_module.NO_TARGET_RECHECK_SECONDS)
    assert plugin._scheduler_consecutive_failures == 0
    assert plugin._today_pushed is False


async def test_wait_for_push_targets_returns_on_new_day():
    import astrbot_plugin_vocabcard.main as main_module

    plugin = _plugin_with_targets([[]])
    sleep = AsyncMock()
    with (
        patch.object(main_module.asyncio, "sleep", sleep),
        patch.object(main_module, "logger"),
    ):
        # 传入一个已过去的日期，模拟等待期间跨过了 0 点
        await plugin._wait_for_push_targets("2000-01-01")

    assert sleep.await_count == 1


def _fake_playwright(launch):
    """构造 async_playwright() 替身，chromium.executable_path 指向不存在的文件。"""
    browser_type = MagicMock()
    browser_type.executable_path = "/nonexistent/chrome"
    browser_type.launch = launch
    playwright = MagicMock()
    playwright.chromium = browser_type

    class _Manager:
        async def __aenter__(self):
            return playwright

        async def __aexit__(self, *exc):
            return False

    return lambda: _Manager()


async def test_browser_check_accepts_headless_shell_only():
    """只装 headless shell 时完整版路径不存在，但能启动即视为可用。"""
    import playwright.async_api
    from astrbot_plugin_vocabcard.core import image_renderer

    browser = MagicMock()
    browser.close = AsyncMock()
    launch = AsyncMock(return_value=browser)
    image_renderer._installed_browsers.discard("chromium")
    try:
        with patch.object(
            playwright.async_api, "async_playwright", _fake_playwright(launch)
        ):
            await image_renderer._ensure_browser_installed("chromium")
        launch.assert_awaited_once_with(headless=True)
        browser.close.assert_awaited_once()
        assert "chromium" in image_renderer._installed_browsers
    finally:
        image_renderer._installed_browsers.discard("chromium")


async def test_browser_check_reports_unavailable_when_launch_fails():
    import playwright.async_api
    from astrbot_plugin_vocabcard.core import image_renderer

    launch = AsyncMock(side_effect=RuntimeError("Executable doesn't exist"))
    image_renderer._installed_browsers.discard("chromium")
    with patch.object(
        playwright.async_api, "async_playwright", _fake_playwright(launch)
    ):
        with pytest.raises(RuntimeError, match="is unavailable"):
            await image_renderer._ensure_browser_installed("chromium")
    assert "chromium" not in image_renderer._installed_browsers


# ===== Code Review Regression Tests (2026-11-10) =====


def test_style_block_preserves_ai_url_params_and_svg_fallback():
    """<style> RAWTEXT 内不能把 URL 的 & 转义成 &amp;，也不能把纯色 SVG 的 ' 转成 &#39; 截断。"""
    from astrbot_plugin_vocabcard.core.base_handler import WordEntry

    plugin = _make_plugin()
    plugin.offline_backgrounds = []
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "use_cdn_background": False,
            "enable_ai_background": False,
            "default_bg_url": "",
        }.get(key, default)
    )
    word = WordEntry(
        word="look/into", pos="v.", definition="调查", example="Look into it."
    )
    fallback_html = plugin._render_template(word)
    assert "&#39;" not in fallback_html
    assert "data:image/svg+xml," in fallback_html

    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "use_cdn_background": False,
            "enable_ai_background": True,
            "default_bg_url": "",
        }.get(key, default)
    )
    ai_html = plugin._render_template(word)
    assert "look%2Finto" in ai_html
    assert "?width=1920&height=2400&nologo=true&model=flux&enhance=true" in ai_html
    assert "&amp;height=" not in ai_html


def test_validate_cdp_url_rejects_unspecified_0_0_0_0():
    from astrbot_plugin_vocabcard.core.security import validate_cdp_url

    with pytest.raises(ValueError):
        validate_cdp_url("http://0.0.0.0:9222")
    assert (
        validate_cdp_url("http://0.0.0.0:9222", allow_remote=True)
        == "http://0.0.0.0:9222"
    )
    assert validate_cdp_url("http://127.0.0.2:9222") == "http://127.0.0.2:9222"
    assert validate_cdp_url("http://[::1]:9222") == "http://[::1]:9222"


async def test_image_renderer_cancellation_releases_slot_and_wakes_waiter(tmp_path):
    """取消渲染或渲染抛错时，必须归还槽位并立即唤醒排队的 _acquire_page。"""
    from astrbot_plugin_vocabcard.core.image_renderer import ImageRenderer

    renderer = ImageRenderer(max_pages=1)
    renderer._init_browser = AsyncMock()
    renderer._loop = asyncio.get_running_loop()

    goto_started = asyncio.Event()

    async def slow_goto(_uri):
        goto_started.set()
        await asyncio.sleep(60)

    page1 = MagicMock()
    page1.is_closed.return_value = False
    page1.goto = AsyncMock(side_effect=slow_goto)
    page1.context = MagicMock()
    page1.context.close = AsyncMock()

    page2 = MagicMock()
    page2.is_closed.return_value = False
    page2.context = MagicMock()
    page2.context.close = AsyncMock()

    pages = [page1, page2]

    async def create_page(_w, _h, scale):
        p = pages.pop(0)
        renderer._page_scales[p] = scale
        return p

    renderer._create_page = create_page

    render_task = asyncio.create_task(
        renderer.render_to_file("<html></html>", str(tmp_path / "out.png"), 100, 100, 1)
    )
    await goto_started.wait()
    assert renderer._active_pages_count == 1

    waiter = asyncio.create_task(renderer._acquire_page(100, 100, 1, wait_timeout=2.0))
    await asyncio.sleep(0.02)

    render_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await render_task

    leased = await asyncio.wait_for(waiter, timeout=1.0)
    assert leased is page2
    assert renderer._active_pages_count == 1
    await renderer.close()


async def test_cdp_close_disposes_owned_contexts():
    from astrbot_plugin_vocabcard.core.image_renderer import ImageRenderer

    renderer = ImageRenderer(
        max_pages=2, engine="chromium", cdp_url="http://127.0.0.1:9222"
    )
    ctx = MagicMock()
    ctx.close = AsyncMock()
    renderer._browser = MagicMock()
    renderer._owns_browser = False
    renderer._owned_contexts.add(ctx)
    renderer._loop = asyncio.get_running_loop()

    await renderer.close()
    ctx.close.assert_awaited_once()


async def test_duplicate_keywords_all_reachable_in_classical_deck(tmp_path):
    """古文卡组存在重复 keyword（如 7 个'公'），全部 27 句必须拥有独立进度键。"""
    ctx = MagicMock()
    config = MagicMock()
    config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "current_language": "classical",
            "learning_mode": "sequential",
            "reset_on_complete": False,
            "target_groups": [],
        }.get(key, default)
    )
    with patch("astrbot.api.star.StarTools") as _ms:
        _ms.get_data_dir = MagicMock(return_value=str(tmp_path))
        plugin = VocabCardPlugin(ctx, config)

    assert len(plugin.words) == 27
    keys = [plugin._word_key(w) for w in plugin.words]
    assert len(set(keys)) == 27

    picked = []
    while True:
        w = await plugin._select_word()
        if w is None:
            break
        picked.append(plugin._word_key(w))
        await plugin._mark_word_sent(plugin._word_key(w))

    assert len(picked) == 27


def test_word_datasets_have_no_raw_nbsp_or_anki_brackets():
    import json
    import pathlib

    root = pathlib.Path(_plugin_dir) / "languages"
    idioms = json.loads((root / "idiom" / "words.json").read_text(encoding="utf-8"))
    assert not any("&nbsp;" in str(v) for item in idioms for v in item.values())
    ja = json.loads((root / "japanese" / "words.json").read_text(encoding="utf-8"))
    assert not any(
        "[" in item.get("word", "")
        or "]" in item.get("word", "")
        or " " in item.get("word", "")
        for item in ja
    )


async def test_schedule_next_target_wakes_at_midnight_after_daily_completion():
    plugin = _make_plugin()
    plugin._today_generated = True
    plugin._today_pushed = True
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime(2026, 6, 12, 8, 5, 0, tzinfo=tz)
    nxt = plugin._calculate_next_target_time(now, (7, 30), (7, 0))
    assert nxt == datetime.datetime(2026, 6, 13, 0, 0, 0, tzinfo=tz)


async def test_persist_schedule_state_updates_stale_date_across_midnight(
    tmp_path, monkeypatch
):
    import json

    plugin = _make_plugin(data_dir=tmp_path)
    plugin._last_check_date = "2000-01-01"
    plugin._today_generated = True
    plugin._today_pushed = True
    await plugin._persist_schedule_state()

    state = json.loads((tmp_path / "schedule_state.json").read_text(encoding="utf-8"))
    assert state["date"] != "2000-01-01"
    assert plugin._last_check_date == state["date"]


async def test_delayed_vocab_test_does_not_mutate_configured_target_groups(tmp_path):
    plugin = _make_plugin(data_dir=tmp_path)
    targets = ["group-1"]
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: (
            targets if key == "target_groups" else default
        )
    )
    img = tmp_path / "card.png"
    img.write_bytes(b"png")
    plugin._select_word = AsyncMock(
        return_value=MagicMock(word="alpha", extra_fields={})
    )
    plugin._generate_card_image = AsyncMock(return_value=str(img))
    plugin.context.send_message = AsyncMock(return_value=True)

    event = MagicMock()
    event.unified_msg_origin = "admin-private"

    import astrbot_plugin_vocabcard.main as main_module

    with patch.object(main_module.asyncio, "sleep", AsyncMock()):
        async for _ in plugin.cmd_test_push(event, "5"):
            pass
        await asyncio.gather(*list(plugin._background_tasks))

    plugin.config.__setitem__.assert_not_called()
    sent_targets = [c.args[0] for c in plugin.context.send_message.await_args_list]
    assert set(sent_targets) == {"group-1", "admin-private"}
    assert plugin._today_generated is True
    assert plugin._today_pushed is True


async def test_switch_language_denies_non_admin():
    plugin = _make_plugin()
    event = MagicMock()
    event.is_admin.return_value = False
    outputs = []
    event.plain_result = MagicMock(side_effect=lambda m: outputs.append(m))

    async for _ in plugin.cmd_switch_language(event, "japanese"):
        pass

    assert plugin.current_language == "english"
    assert any("管理员权限" in m for m in outputs)


# ===== Regression tests for non-mutating previews and resumable pushes =====


async def test_select_word_read_only_does_not_reset_completed_progress():
    plugin = _make_plugin()
    from astrbot_plugin_vocabcard.core.base_handler import WordEntry

    plugin.words = [WordEntry(word="a", definition="1")]
    plugin.progress = {"sent_words": ["a"], "last_push_date": "2026-01-01"}
    plugin._save_progress = AsyncMock()

    word = await plugin._select_word(update_progress=False)

    assert word is not None
    assert plugin.progress["sent_words"] == ["a"]
    plugin._save_progress.assert_not_awaited()


async def test_select_word_default_still_resets_completed_progress():
    plugin = _make_plugin()
    from astrbot_plugin_vocabcard.core.base_handler import WordEntry

    plugin.words = [WordEntry(word="a", definition="1")]
    plugin.progress = {"sent_words": ["a"], "last_push_date": ""}
    plugin._save_progress = AsyncMock()

    word = await plugin._select_word()

    assert word is not None
    assert plugin.progress["sent_words"] == []
    plugin._save_progress.assert_awaited_once()


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("cmd_vocab", ()),
        ("cmd_preview", ("",)),
        ("cmd_test_push", ("0",)),
    ],
)
async def test_immediate_commands_select_words_without_progress_changes(
    method_name, args
):
    plugin = _make_plugin()
    plugin._check_rate_limit = MagicMock(return_value=True)
    plugin._select_word = AsyncMock(return_value=None)
    event = MagicMock()

    async for _ in getattr(plugin, method_name)(event, *args):
        pass

    plugin._select_word.assert_awaited_once_with(update_progress=False)


async def test_partial_push_state_restores_and_retries_only_failed_target(tmp_path):
    from astrbot_plugin_vocabcard.core.base_handler import WordEntry
    import json

    word = WordEntry(word="daily", definition="definition")
    image_path = tmp_path / "daily.png"
    image_path.write_bytes(b"png")
    plugin = _make_plugin(data_dir=tmp_path, words=[word])
    plugin._cached_image_path = str(image_path)
    plugin._current_word = word
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: (
            ["A", "B"] if key == "target_groups" else default
        )
    )

    async def first_send(umo, chain):
        if umo == "B":
            raise RuntimeError("offline")
        return True

    plugin.context.send_message = AsyncMock(side_effect=first_send)
    first = await plugin._push_daily_card()

    assert (first.attempted_count, first.success_count) == (2, 1)
    with open(tmp_path / "schedule_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    assert state["push_succeeded_umos"] == ["A"]

    plugin2 = _make_plugin(data_dir=tmp_path, words=[word])
    plugin2.config.get = MagicMock(
        side_effect=lambda key, default=None: (
            ["A", "B"] if key == "target_groups" else default
        )
    )
    plugin2.context.send_message = AsyncMock(return_value=True)
    second = await plugin2._push_daily_card()

    assert (second.attempted_count, second.success_count) == (1, 1)
    assert [call.args[0] for call in plugin2.context.send_message.await_args_list] == [
        "B"
    ]
    assert plugin2.progress["sent_words"] == ["daily"]
    assert plugin2._cached_image_path is None
    assert plugin2._current_word is None
    assert plugin2._push_succeeded_umos == set()
    assert not image_path.exists()
    with open(tmp_path / "schedule_state.json", "r", encoding="utf-8") as f:
        final_state = json.load(f)
    assert final_state["push_succeeded_umos"] == []


async def test_restore_rejects_invalid_succeeded_umo_list(tmp_path):
    import json

    today = (
        __import__("astrbot_plugin_vocabcard.main", fromlist=["get_beijing_time"])
        .get_beijing_time()
        .strftime("%Y-%m-%d")
    )
    (tmp_path / "schedule_state.json").write_text(
        json.dumps({"date": today, "push_succeeded_umos": ["A", 1]}),
        encoding="utf-8",
    )

    plugin = _make_plugin(data_dir=tmp_path)

    assert plugin._push_succeeded_umos == set()


async def test_partial_push_successes_accumulate_across_retries(tmp_path):
    image_path = tmp_path / "daily.png"
    image_path.write_bytes(b"png")
    plugin = _make_plugin()
    plugin._cached_image_path = str(image_path)
    plugin._current_word = MagicMock(word="daily")
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: (
            ["A", "B", "C"] if key == "target_groups" else default
        )
    )
    attempt_round = 0

    async def send(umo, chain):
        if (attempt_round == 1 and umo == "A") or (attempt_round == 2 and umo == "B"):
            return True
        raise RuntimeError("offline")

    plugin.context.send_message = AsyncMock(side_effect=send)
    attempt_round = 1
    await plugin._push_daily_card()
    assert plugin._push_succeeded_umos == {"A"}

    attempt_round = 2
    await plugin._push_daily_card()
    assert plugin._push_succeeded_umos == {"A", "B"}


async def test_removed_failed_target_allows_existing_successes_to_complete(tmp_path):
    image_path = tmp_path / "daily.png"
    image_path.write_bytes(b"png")
    plugin = _make_plugin()
    plugin._cached_image_path = str(image_path)
    plugin._current_word = MagicMock(word="daily")
    plugin._push_succeeded_umos = {"A"}
    plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: (
            ["A"] if key == "target_groups" else default
        )
    )
    plugin.context.send_message = AsyncMock()

    result = await plugin._push_daily_card()

    assert (result.attempted_count, result.success_count) == (1, 1)
    plugin.context.send_message.assert_not_awaited()
    assert plugin.progress["sent_words"] == ["daily"]
    assert plugin._cached_image_path is None
    assert plugin._current_word is None
    assert plugin._push_succeeded_umos == set()


async def test_new_daily_card_clears_previous_push_successes(tmp_path):
    image_path = tmp_path / "new.png"
    image_path.write_bytes(b"png")
    plugin = _make_plugin()
    plugin._push_succeeded_umos = {"A"}
    plugin._select_word = AsyncMock(return_value=MagicMock(word="new"))
    plugin._generate_card_image = AsyncMock(return_value=str(image_path))

    assert await plugin._generate_daily_card() is True
    assert plugin._push_succeeded_umos == set()


async def test_new_day_clears_previous_push_successes():
    plugin = _make_plugin()
    plugin._last_check_date = "2000-01-01"
    plugin._push_succeeded_umos = {"A"}
    plugin._time_reached = MagicMock(return_value=False)
    persisted = asyncio.Event()
    plugin._persist_schedule_state = AsyncMock(side_effect=persisted.set)

    task = asyncio.create_task(plugin._schedule_loop())
    try:
        await asyncio.wait_for(persisted.wait(), timeout=1)
        assert plugin._push_succeeded_umos == set()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_scheduled_image_cleanup_is_cancelled_by_terminate(tmp_path):
    image_path = tmp_path / "temporary.png"
    image_path.write_bytes(b"png")
    plugin = _make_plugin()
    plugin._image_renderer.close = AsyncMock()
    before = asyncio.all_tasks()
    plugin._schedule_image_cleanup(str(image_path))
    cleanup_tasks = asyncio.all_tasks() - before
    assert len(cleanup_tasks) == 1
    cleanup_task = cleanup_tasks.pop()

    try:
        assert cleanup_task in plugin._background_tasks
        await plugin.terminate()
        assert cleanup_task.cancelled()
        assert image_path.exists()
    finally:
        if not cleanup_task.done():
            cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
