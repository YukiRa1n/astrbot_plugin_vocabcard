# AstrBot 每日学习卡片

每日定时生成并推送玻璃拟态风格学习卡片的 AstrBot 插件，内置英语、日语、成语、古文与无线电法规题库，无需接入大模型。

[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](metadata.yaml)

[核心特性](#核心特性) · [预览与卡组](#预览与卡组) · [安装与快速开始](#安装与快速开始) · [命令](#命令) · [配置](#配置)

## 核心特性

- **多领域内置词库**：涵盖英语六级、日语 JLPT（N1–N4）、常用成语、古文名句与无线电法规共 15,000+ 词条，各卡组独立保存学习进度。
- **玻璃拟态高清渲染**：基于 Playwright 渲染各题库专属模板（基础尺寸 `432 × 540`，默认 `3x` 输出 `1296 × 1620`），支持 CDN、Pollinations AI、自定义 URL、本地图库与纯色背景。
- **双阶段定时与断点续推**：按固定北京时间（UTC+8）分离预生成与定时推送，持久化当日状态与已送达目标，重启补跑或部分失败重试不会重复刷屏。
- **即时抽卡与进度隔离**：所有人可随时抽卡（`/vocab`）或查词预览（`/vocab_preview`），内置每用户 30 秒频控，不影响每日学习进度。
- **页面池与共享浏览器**：内置受控并发页面池，支持接入外部共享 Chromium CDP 以降低多插件进程开销。

## 预览与卡组

<div align="center">
  <img src="example.png" width="280" alt="学习卡片预览">
</div>

| 卡组 ID | 内容 | 词条数 | 说明 |
| --- | --- | ---: | --- |
| `english` | 英语六级核心词汇 | 3,722 | 默认卡组 |
| `japanese` | 日语全量词库（N1–N4） | 10,147 | 可配合 `japanese_level` 按等级筛选 |
| `japanese_n1` ~ `japanese_n4` | 日语 JLPT 分级卡组 | 4,084 / 2,916 / 1,579 / 1,568 | 各等级独立记录进度（`japanese_n5` 为预留空卡组，暂无词条） |
| `idiom` | 常用成语 | 824 | 含拼音、释义、出处与例句 |
| `classical` | 古文经典名句 | 27 | 古诗文名篇佳句 |
| `radio` | 无线电法规题库 | 361 | 业余无线电操作证题库 |

## 安装与快速开始

1. **安装插件**：在 AstrBot WebUI 插件页通过仓库地址 `https://github.com/YukiRa1n/astrbot_plugin_vocabcard` 安装；或克隆至 `data/plugins/` 后手动安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. **安装浏览器内核**（在 AstrBot 同一 Python 环境中执行，容器部署需进入容器内执行）：
   ```bash
   python -m playwright install chromium
   ```
3. **开启推送**：管理员在目标群聊或私聊发送 `/vocab_register` 启用每日推送（默认北京时间 `07:30` 预生成、`08:00` 推送），发送 `/vocab_test` 验证出图。

## 命令

| 命令 | 权限 | 说明 |
| --- | --- | --- |
| `/vocab` | 所有人 | 随机或顺序抽取一张卡片（不计入进度，30 秒冷却） |
| `/vocab_preview [词条]` | 所有人 | 按词条或音标/假名预览卡片；留空则抽取一条（不计入进度，30 秒冷却） |
| `/vocab_status` | 所有人 | 查看当前卡组、已学数量、完成度与推送时间 |
| `/vocab_lang` | 所有人 | 查看当前卡组及全部可用卡组列表 |
| `/vocab_help` | 所有人 | 显示插件命令帮助 |
| `/vocab_lang <卡组ID>` | 管理员 | 切换全局卡组（所有已注册会话共享）并重置当日待推缓存 |
| `/vocab_register` / `/vocab_unregister` | 管理员 | 为当前会话开启或取消每日定时推送 |
| `/vocab_now` | 管理员 | 立即生成卡片并推送至全部已注册会话（计入进度） |
| `/vocab_test [秒数]` | 管理员 | 不传参时在当前会话即时测试出图；传入 `1–300` 秒时延迟执行完整推送流程 |

## 配置

在 AstrBot WebUI 插件配置页修改并保存（已注册会话列表 `target_groups` 由命令自动维护，无需手动编辑）。

### 学习与定时

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `current_language` | `english` | 当前全局卡组 ID |
| `japanese_level` | `all` | `japanese` 全量卡组的等级筛选（`all` / `N1`–`N4`） |
| `push_time_generate` / `push_time_send` | `07:30` / `08:00` | 每日预生成与推送时间（`HH:MM`，固定 UTC+8 北京时间） |
| `learning_mode` | `random` | 选词模式：`random` 随机学习，`sequential` 顺序学习 |
| `reset_on_complete` | `true` | 学完全部词条后是否自动重置进度 |

> 进度与调度状态保存在 `data/plugin_data/astrbot_plugin_vocabcard/`（`progress_<卡组ID>.json` 与 `schedule_state.json`），仅当全部已注册目标会话发送成功后才提交当日词条进度。

### 卡片背景

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `use_cdn_background` | `true` | 使用内置阿里云 OSS 背景图（最高优先级） |
| `enable_ai_background` | `false` | 使用 Pollinations.ai 根据词义动态生成背景 |
| `default_bg_url` | 空 | 自定义固定背景图片 URL |
| `bg_load_timeout` | `5000` | 等待背景网络请求完成的超时毫秒数（范围 `1000–60000`） |

> **背景优先级**：`use_cdn_background` → `enable_ai_background` → `default_bg_url` → 插件目录 `photos/` 本地图片（支持 `.jpg` / `.png` / `.webp` / `.bmp`）→ 纯色背景。使用 AI、自定义 URL 或本地离线背景前请先关闭 `use_cdn_background`。

### 浏览器与渲染

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `render_scale` | `3` | 渲染倍率（范围 `1–4`，基础尺寸 `432 × 540`，`3` 倍输出 `1296 × 1620`） |
| `browser_engine` | `chromium` | 浏览器内核（`chromium` / 实验性 `firefox`、`webkit`，切换前需安装对应内核） |
| `browser_max_pages` | `2` | 最大并发渲染页面数（范围 `1–8`） |
| `browser_cdp_url` / `allow_remote_cdp` | 空 / `false` | 外部共享 Chromium CDP 地址（默认仅允许本机回环地址） |
| `auto_install_browser` | `false` | 浏览器缺失时是否允许运行时自动下载 |

<details>
<summary>可选：共享外部 Chromium（CDP）</summary>

多插件都需要浏览器截图时，可复用同一个无头 Chromium 进程：

```bash
chromium --headless --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir=/tmp/astrbot-chromium
```

随后将 `browser_cdp_url` 设为 `http://127.0.0.1:9222`（仅 `chromium` 引擎生效）。CDP 协议无内置鉴权，切勿暴露公网；仅在受信任容器网络内按需开启 `allow_remote_cdp`。

</details>

<details>
<summary>开发与测试</summary>

```bash
pip install pytest pytest-asyncio
pytest -q
python scripts/generate_example.py
```

</details>

## 许可证

本项目基于 [GNU AGPL-3.0](LICENSE) 许可证开源。
