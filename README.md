<div align="center">

# AstrBot 每日学习卡片

为 AstrBot 定时生成并推送英语、日语、成语、古文和无线电法规学习卡片。

[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](metadata.yaml)

</div>

## 功能

- 内置 5 类学习内容和 10 个卡组入口。
- 按北京时间分别执行卡片生成和卡片推送。
- 为每个卡组保存独立学习进度。
- 支持随机学习、顺序学习和完成后重置。
- 使用 Playwright 将 HTML 模板渲染为 PNG。
- 支持 CDN、AI、指定 URL、本地图片和纯色背景。
- 支持 Chromium、Firefox 和 WebKit。
- 支持浏览器页面池和共享 Chromium CDP。
- AstrBot 重启后可恢复当天的生成与推送状态。

插件不需要 LLM Provider。只有启用 AI 背景时，插件才会访问 Pollinations.ai。

## 效果预览

<div align="center">
  <img src="example.png" width="300" alt="学习卡片预览">
</div>

卡片基础尺寸为 `432 × 540`。默认 `render_scale=3`，输出尺寸为 `1296 × 1620`。

## 内置卡组

| 卡组 ID | 内容 | 词条数 | 备注 |
| --- | --- | ---: | --- |
| `english` | 英语六级核心词汇 | 3,722 |  |
| `japanese` | 日语全量词库 | 10,147 | 可用 `japanese_level` 筛选等级 |
| `japanese_n1` | 日语 N1 | 4,084 | 独立学习进度 |
| `japanese_n2` | 日语 N2 | 2,916 | 独立学习进度 |
| `japanese_n3` | 日语 N3 | 1,579 | 独立学习进度 |
| `japanese_n4` | 日语 N4 | 1,568 | 独立学习进度 |
| `japanese_n5` | 日语 N5 | 0 | 已预留配置，当前版本未内置 N5 数据 |
| `idiom` | 常用成语 | 824 |  |
| `classical` | 古文经典句子 | 27 |  |
| `radio` | 无线电法规题库 | 361 |  |

当前日语词库只包含 N1 至 N4。将 `japanese_level` 设为 `N5`，或切换到 `japanese_n5`，不会生成卡片。

## 安装

### 通过 WebUI 安装

1. 打开 AstrBot WebUI。
2. 进入“插件”页面。
3. 点击右下角的 `+`。
4. 选择通过 URL 安装。
5. 输入仓库地址：

```text
https://github.com/YukiRa1n/astrbot_plugin_vocabcard
```

AstrBot 通常会根据 `requirements.txt` 安装 Python 依赖。详细操作参见 [AstrBot WebUI 文档](https://docs.astrbot.app/use/webui.html#插件)。

### 从源码安装

在 AstrBot 工作目录中执行：

```bash
cd data/plugins
git clone https://github.com/YukiRa1n/astrbot_plugin_vocabcard.git
```

然后重启 AstrBot，或在 WebUI 中重载插件。

### 安装 Playwright 浏览器

Python 包和浏览器程序是两个不同的依赖。默认配置不会在运行时下载浏览器。

在 AstrBot 使用的同一个 Python 环境中执行：

```bash
python -m playwright install chromium
```

如果 AstrBot 运行在容器中，请在容器内执行该命令。

如果 Python 依赖没有自动安装，再执行：

```bash
pip install -r requirements.txt
```

## 快速开始

1. 管理员在需要接收卡片的会话中发送 `/vocab_register`。
2. 管理员发送 `/vocab_test`，确认卡片可以生成和发送。
3. 发送 `/vocab_status` 查看当前卡组和学习进度。

默认在北京时间 `07:30` 生成卡片，在 `08:00` 推送卡片。插件使用固定的 UTC+8 时间，不依赖系统时区。

## 命令

| 命令 | 权限 | 说明 |
| --- | --- | --- |
| `/vocab` | 所有人 | 随机或顺序生成一张卡片，不记录进度 |
| `/vocab_preview [词条]` | 所有人 | 预览指定词条；不传参数时选择一个词条 |
| `/vocab_status` | 所有人 | 查看当前卡组、进度和推送时间 |
| `/vocab_help` | 所有人 | 显示插件帮助 |
| `/vocab_lang` | 所有人 | 查看当前卡组和全部卡组 |
| `/vocab_lang <卡组 ID>` | 管理员 | 切换全局卡组 |
| `/vocab_register` | 管理员 | 为当前会话启用每日推送 |
| `/vocab_unregister` | 管理员 | 取消当前会话的每日推送 |
| `/vocab_now` | 管理员 | 立即生成卡片并推送到全部已注册会话 |
| `/vocab_test` | 管理员 | 立即在当前会话测试卡片生成 |
| `/vocab_test <秒数>` | 管理员 | 延迟执行完整推送流程，最大值为 300 秒 |

`/vocab_lang <卡组 ID>` 修改全局卡组。所有已注册会话共享这个设置。

## 配置

在 AstrBot WebUI 的插件配置页面中修改以下项目。

### 学习与推送

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `current_language` | `english` | 当前卡组 ID |
| `japanese_level` | `all` | `japanese` 卡组的等级筛选 |
| `push_time_generate` | `07:30` | 每日生成时间，格式为 `HH:MM` |
| `push_time_send` | `08:00` | 每日推送时间，格式为 `HH:MM` |
| `learning_mode` | `random` | `random` 随机学习，`sequential` 顺序学习 |
| `reset_on_complete` | `true` | 学完全部内容后是否重置进度 |

`target_groups` 由 `/vocab_register` 和 `/vocab_unregister` 管理，不需要手动编辑。

### 背景

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `use_cdn_background` | `true` | 使用插件内置的阿里云 OSS 背景列表 |
| `enable_ai_background` | `false` | 使用 Pollinations.ai 生成背景 |
| `default_bg_url` | 空 | 使用指定的背景图片 URL |
| `bg_load_timeout` | `5000` | 等待背景网络请求完成的毫秒数，范围为 1000–60000 |

背景选择顺序如下：

1. CDN 背景。
2. AI 背景。
3. `default_bg_url`。
4. `photos/` 或兼容目录 `backgrounds/` 中的本地图片。
5. 纯色背景。

如果需要使用 AI、指定 URL 或本地背景，请先关闭 `use_cdn_background`。如果同时启用 AI 背景并设置 `default_bg_url`，插件优先使用 AI 背景。

本地背景支持 `.jpg`、`.jpeg`、`.png`、`.webp` 和 `.bmp`。

### 浏览器与渲染

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `browser_engine` | `chromium` | 可选 `chromium`、`firefox`、`webkit` |
| `browser_cdp_url` | 空 | 共享 Chromium 的 CDP 地址 |
| `allow_remote_cdp` | `false` | 是否允许连接非本机 CDP 地址 |
| `browser_max_pages` | `2` | 最大并发渲染页面数，最小值为 1 |
| `auto_install_browser` | `false` | 浏览器缺失时是否允许运行时下载 |
| `render_scale` | `3` | 渲染倍率，范围为 1–4 |

不同渲染倍率对应以下图片尺寸：

| `render_scale` | 输出尺寸 |
| ---: | ---: |
| 1 | 432 × 540 |
| 2 | 864 × 1080 |
| 3 | 1296 × 1620 |
| 4 | 1728 × 2160 |

更高倍率会增加内存占用和渲染时间。Firefox 和 WebKit 是实验选项，使用前需安装对应浏览器：

```bash
python -m playwright install firefox
python -m playwright install webkit
```

## 共享 Chromium

多个插件需要截图时，可以共享一个外部 Chromium，减少浏览器进程数量。

启动 Chromium：

```bash
chromium \
  --headless \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/astrbot-chromium
```

将 `browser_cdp_url` 设置为：

```text
http://127.0.0.1:9222
```

CDP 模式只支持 Chromium。插件默认只接受本机 CDP 地址。

CDP 没有内置鉴权。不要将端口暴露到公网。只有在可信内网中才应开启 `allow_remote_cdp`。

## 学习进度与定时状态

插件将持久化文件保存到：

```text
data/plugin_data/vocabcard/
```

主要文件如下：

```text
progress_<卡组 ID>.json
schedule_state.json
```

- 每个卡组使用独立的进度文件。
- 成功推送到至少一个会话后，插件才记录学习进度。
- `/vocab`、`/vocab_preview` 和即时 `/vocab_test` 不记录进度。
- 插件会保存当天的生成状态、推送状态和缓存卡片。
- 当 AstrBot 在计划时间之后重启时，插件会补做尚未完成的任务。

如需清空一个卡组的进度，请停用插件，删除对应的 `progress_<卡组 ID>.json`，然后重新启用插件。

## 常见问题

### 提示 Playwright 浏览器不可用

在 AstrBot 使用的 Python 环境中安装当前配置的浏览器：

```bash
python -m playwright install chromium
```

如果使用 Firefox 或 WebKit，请将命令末尾替换为对应引擎名称。

### 插件加载失败并提示缺少 Python 模块

在插件目录执行：

```bash
pip install -r requirements.txt
```

也可以通过 AstrBot WebUI 的 Pip 安装功能补装依赖。

### 每日推送没有执行

依次检查：

1. 当前会话是否执行过 `/vocab_register`。
2. 执行命令的用户是否具有 AstrBot 管理员权限。
3. `push_time_generate` 和 `push_time_send` 是否为有效的 `HH:MM`。
4. 当前时间是否按北京时间计算。
5. AstrBot 平台日志中是否有卡片生成或消息发送错误。

### `/vocab` 没有增加学习进度

这是预期行为。即时卡片与每日学习进度相互独立。

使用 `/vocab_now` 或定时推送。只要至少一个会话接收成功，插件就会记录该词条。

### 背景加载慢

- 关闭 `use_cdn_background` 和 `enable_ai_background`。
- 将本地图片放入插件的 `photos/` 目录。
- 根据网络状况调整 `bg_load_timeout`。

### `japanese_n5` 没有可用词条

当前版本只内置 N1 至 N4 数据。`japanese_n5` 是预留入口。

## 开发与测试

安装测试依赖：

```bash
pip install pytest pytest-asyncio
```

运行测试。测试代码使用项目根目录中的顶层模块，因此需要设置 `PYTHONPATH`。

Linux 或 macOS：

```bash
PYTHONPATH=. pytest -q
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest -q
```

生成示例图片：

```bash
python scripts/generate_example.py
```

## 许可证

本项目使用 [GNU AGPL-3.0](LICENSE) 许可证。
