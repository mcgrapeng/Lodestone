<div align="center">

# ⚡ Lodestone · AI 工具发现平台

**给 AI 应用工程师：每日 GitHub + HuggingFace + MCP Registry 三源聚合**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)
![Engines](https://img.shields.io/badge/4_Engines-Tiered_Fallback-blue.svg)
![Skills](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet.svg)

[📖 使用手册](使用手册.md) · [📦 安装说明](安装说明.md) · [🤖 SKILL 源码](SKILL.md)

</div>

---

## 🚀 30 秒上手

```bash
# 1. 装为 Claude Code / Codex CLI 的 skill
./install.sh install

# 2. 完全退出 Claude Code（Cmd+Q）再重开

# 3. 在 Claude Code 里说
"刷一下 AI 雷达"
```

或者直接跑：

```bash
./radar.py crawl   # 爬取 + 翻译 + 入库（约 5-8 分钟）
./radar.py today   # 终端看 Top 15 + 分类
```

打开 **http://localhost:5173**（前端）—— 19 分类卡片 / 325 个 AI 工具 / 中文一句话总结。

---

## 🤔 这是什么？

**AI 工具发现助手** —— 每日自动从 GitHub / HuggingFace / 官方 MCP Registry 抓取主流 AI 应用开发工具（skills / plugins / agents / RAG / IDE / MCP / Voice / ...），按 19 个用途分类，中文友好展示。

```
触发："刷一下 AI 雷达"
        │
        ▼
radar.py crawl:
  🔍  GitHub Topics + Search API →  主流仓库
  🔍  HuggingFace Spaces API    →  社区 demo
  🔍  HuggingFace Models API    →  模型权重
  🔍  MCP Registry API          →  MCP servers
        │
        ▼
14 → 4 精选爬虫引擎分级 fallback（httpx → cloudscraper →
  playwright_stealth → jina，本地轻 → 本地重 → 云端，质量门把关）
        │
        ▼
  🌐 中文翻译（Google Translate）+ 一句话总结
  🏷  best_category 推断 / local_installed 检测
        │
        ▼
data/latest.json（327 个 AI 工具）：
  ├── 19 分类卡片（Agent / RAG / MCP / HF / Voice / ...）
  ├── 🔥 Top 24 全网最热
  ├── 🚀 今日星增（24h trending）
  └── 🌍 生态分布（15 语言 + 30 主题）
```

---

## 🎯 三大数据源

| 源 | API | 价值 |
|---|---|------|
| **GitHub Topics + Search + Trending** | `gh api` + `github.com/trending` HTML | 主流开源 AI 项目主战场 |
| **HuggingFace Spaces + Models** | `api/spaces?sort=trending` + `api/models?sort=likes7d` | 社区精选 AI demo + 模型权重 |
| **MCP Server Registry** | `registry.modelcontextprotocol.io/v0/servers` | Model Context Protocol 官方注册表 |

**GitHub 抗爬时仍能完整工作**（MCP / HF 源不依赖 GitHub）。

---

## 🧰 4 精选爬虫引擎（2026-09 从 14 精简）

引擎不在多，在精、互补、开源、主流 — 每级解决一种别的级解决不了的失败模式，
分级 fallback：轻引擎过质量门即停，不过才升级更重的，日常爬取不启动浏览器：

| 层级 | 引擎 | 解决的失败模式 |
|------|------|---------------|
| 1 · 本地纯 HTTP | httpx | 最快路径 — trending 是 SSR，多数直接命中 |
| 2 · 本地 HTTP + 挑战破解 | cloudscraper | bot-check 中间页（Cloudflare challenge），无需浏览器 |
| 3 · 本地真浏览器 | playwright_stealth | JS 渲染 / 严格指纹检测（Chromium + stealth 补丁） |
| 4 · 云端渲染 | jina | 本地 IP 被封时逃生（r.jina.ai 免费层，换出口 IP） |

- **质量门**：每级结果须通过「长度 + bot-check 特征 + 已知页面结构标记」（如 trending 须 ≥5 个 `Box-row`）才算数，bot 页自动升级下一级
- **白名单**：`config.toml [orchestrator].priority` 是唯一引擎清单，其余 10 个适配器（firecrawl / crawl4ai / playwright / nodriver / crawlee / scrapy / agent_reach / trafilatura / beautifulsoup / drissionpage）已停用但保留，加回列表即可重启
- **URL 调度**：`scrapers/url_dispatcher.py` 按 host 模式调整每类 URL 的引擎顺序
- **旧行为**：`selection_strategy = "longest"` 可切回全引擎并行竞赛（调试用）

---

## 📚 19 个分类

| | 分类 | 来源 | query 数 |
|---|---|---|---:|
| 🤖 | AI Agent & Skills | GitHub | 4 |
| 🧠 | RAG / Memory / Vector | GitHub | 4 |
| 💬 | LLM Interface & Chat | GitHub | 4 |
| ⚙️ | Code Generation & Dev Tools | GitHub | 4 |
| 🔗 | Workflow & Orchestration | GitHub | 4 |
| 🎨 | Multimodal (Vision / Audio / Video) | GitHub | 3 |
| 🏋️ | Fine-tuning & Training | GitHub | 4 |
| 📊 | Eval & Benchmark | GitHub | 3 |
| 💻 | AI IDE & 编辑器 | GitHub | 7 |
| 🌐 | LLM Gateway & Router | GitHub | 6 |
| 🔍 | LLM 可观测 & Tracing | GitHub | 6 |
| ⭐ | Awesome Lists & Plugins | GitHub | 7 |
| 🔌 | MCP Servers & Clients | **MCP Registry + GitHub** | 9 |
| 🎙 | Voice AI / Realtime | GitHub | 16 |
| 🖥 | Browser Use / Computer | GitHub | 11 |
| 🤗 | 🤗 HuggingFace 热门 Spaces | **HF API** | 0 |
| 🤗 | 🤗 HuggingFace 热门 Models | **HF API** | 0 |
| 🛡 | AI 安全 & 隐私 | GitHub | 14 |
| 🤖 | 机器人 / Embodied AI | GitHub | 13 |

---

## ✨ 数据快照长这样

```
data/latest.json（327 个 AI 工具）:
  hot:  50（全字段完整，含 desc_zh / summary_zh / lang / topics）
  cats: 19 × ~17 平均 = 291 unique
  stars_today: 18 个 trending 仓库（已 gh API 二次 enrich）
```

每个 repo 字段：
- `name` / `url` / `desc` / `desc_zh` / `summary_zh`（一句话中文）
- `stars` / `forks` / `lang` / `topics`
- `best_category`（基于关键词推断）/ `local_installed`（基于本机检测）
- `trending` / `is_fresh`（14 天内 push）
- `facts`（📚 lang · 🏷 topics · ⭐ stars）

---

## 🆕 v0.2 · 前端重写 (2026-09)

UI 已从 Vue 3 + Element Plus **全部替换**为 **React 19 + [Appica UI](https://github.com/appica-dev/appica-ui)** (Tailwind v4 + Base UI + Motion)。后端 `radar.py` + 4 个精选爬虫引擎（分级 fallback）,数据接口保持兼容 (`/api/data` · `/api/stats` · `/api/gain` · `/api/top` · `/api/repo/<name>/readme`)。

**重写后保留的能力**
- 🔥 GitHub Trending 横向卡片墙 + 入场 stagger 动画
- 🗂 19 个分类总览卡 + 锚点跳转 + 单分类网格
- 🚀 24h 星增(`/api/gain` 分页 + 缺失数据空态)
- 📊 生态分布(`/api/stats` 编程语言 / 主题分布)
- 📚 中文 README(`/api/repo/<name>/readme` 自动翻译)
- 🔍 全局搜索(name / desc_zh / topic 跨全部仓库)
- 🔄 30s 自动轮询 + 「刷新雷达」按钮触发后台 crawl

**安装**
```bash
cd frontend
npm install --no-audit --no-fund    # 拉 @appica/ui-react
npm run dev                          # 同时拉起 radar.py serve (8765) + Vite (5173)
```
打开 http://localhost:5173 即可。

## 📚 文档导航

| 你想了解什么 | 看这里 |
|---|---|
| 🆕 第一次装 skill | | [📦 安装说明.md](安装说明.md) |
| 🚀 装好后怎么用 / 命令清单 | | [📖 使用手册.md](使用手册.md) |
| 🤖 skill 触发入口 | | [SKILL.md](SKILL.md) |
| ❌ 出错了 | | [使用手册 § 6 FAQ](使用手册.md#6-faq--故障排查) |

---

## 🔧 技术栈一览

| 层 | 技术 |
|---|---|
| 🐍 后端 | Python 3.10+（stdlib + 可选 pgpg8000） |
| 📊 数据库 | PostgreSQL（JSON 回退） |
| 🕷️ 爬虫 | 4 引擎分级 fallback（httpx → cloudscraper → playwright_stealth → jina） |
| 🌐 数据源 | GitHub + HuggingFace + MCP Registry |
| 🎨 前端 | React 19 + Vite 6 + Appica UI + Tailwind v4 |
| 🔄 依赖 | `gh` CLI 已认证；翻译走 Google Translate |

---

## 📄 License

MIT