---
name: lodestone
description: 当用户想了解 GitHub + HuggingFace 上最新的 AI 工具/Skills/项目（如 superpowers、agent-memory、LangChain、Coze 等）时触发。Lodestone 是专门发现主流 AI 工具的双源聚合平台 — 自动爬取 GitHub AI 趋势与 HuggingFace Trending Spaces，按 16 个用途分类（Agent/RAG/代码生成/MCP/Voice 等），生成中文仪表盘。触发短语：「看看最新AI项目」「AI radar」「GitHub AI趋势」「刷一下AI雷达」「最近有什么火的AI项目」。
allowed-tools: Bash, Read, Write, Edit
---

# Lodestone · GitHub + HuggingFace 双源 AI 工具发现平台

每日 GitHub AI 热门仓库 + HuggingFace Trending Spaces 自动聚合 · 已为 AI 应用工程师分类整理 · 中文友好

> **跨平台**：本 skill 同时兼容 **Claude Code** (`~/.claude/skills/`) 和 **Codex CLI** (`~/.codex/skills/`)。`SKILL.md` 格式两边相同，通过 `./install.sh` 一次安装双端可用。

## 何时使用本 skill

- 用户问"最近 GitHub 上有什么火的 AI 项目？"
- 用户想了解某个 AI 领域（agent/RAG/微调…）的最新开源工具
- 用户想刷新一次雷达数据
- 用户想看 superpowers 这种 skills 的最新同类项目

## 一键执行

```bash
# skill 安装后，从任意 cwd 都可调用
~/.claude/skills/lodestone/radar.py crawl    # 爬取 + 入库（约 5-8 分钟，含限速等待）
~/.claude/skills/lodestone/radar.py today    # 终端直接看 Top 15 + 分类概览
```

> 安装器创建的是 symlink（不是复制），所以两个路径指向同一个源目录，编辑一处即时生效。

## 子命令

| 命令 | 作用 |
|------|------|
| `radar.py crawl` | 拉取 GitHub（分类 + 5k 补捞 + trending + manual seed）→ 翻译 → 写入 Postgres（无 PG 时回退 `data/latest.json`） |
| `radar.py today` | 终端打印 Top 15 + 分类概览（PG 优先，latest.json 回退） |
| `radar.py serve [port]` | 起 JSON API（默认 8765，**仅绑定 127.0.0.1**） |

crawl 全程持文件锁（`data/crawl.lock`），并发触发会自动拒绝，不会互相打爆 GitHub 限流。

## 分类（12 类自动归类）

1. 🤖 **AI Agent & Skills** — agent、claude-code、MCP、autonomous、multi-agent
2. 🧠 **RAG / Memory / Vector** — vector-db、agent-memory、embedding
3. 💬 **LLM Interface & Chat** — LLM SDK、chatbot、prompt-engineering、claude-api
4. ⚙️ **Code Generation & Dev Tools** — copilot、ai-coding、code-agent
5. 🔗 **Workflow & Orchestration** — langgraph、langchain、pipeline
6. 🎨 **Multimodal** — vision、text-to-video、multimodal
7. 🏋️ **Fine-tuning & Training** — LoRA、PEFT、llama-factory
8. 📊 **Eval & Benchmark** — llm-evaluation、benchmark
9. 💻 **AI IDE & 编辑器** — cursor、aider、cline、continue
10. 🌐 **LLM Gateway & Router** — litellm、openrouter、llm-proxy
11. 🔍 **LLM 可观测 & Tracing** — langfuse、helicone、llmops
12. ⭐ **Awesome Lists & Plugins** — awesome-ai/llm/claude、claude-plugins 生态

## 数据存储（Postgres 优先）

- **PG 模式**（`pip install pg8000` + `.env` 配置）：表 `repos` / `repo_categories` / `repo_stars_history` / `crawl_log`（含 `queries_failed` 数据质量字段）。首次 crawl 自动建库建表。
- **JSON 回退**（无 pg8000 或 PG 不可达）：写 `data/latest.json`，`serve`/`today` 自动回退读取。
- 凭据放 `.env`（参照 `.env.example`），**不进 git**。

## 技术栈

- **后端**：`radar.py`（Python 3.10+，stdlib + 可选 pg8000）+ `db/`（PG 数据层）+ `scrapers/`（可选强力爬虫：firecrawl → crawl4ai → playwright 串行降级，移植自 youzi）
- **前端**：Vue 3 + Vite + Element Plus（`cd frontend && npm run dev` 一键起全栈）
- 依赖 `gh` CLI 已认证；翻译走 Google Translate 免费端点（`data/zh_cache.json` 持久缓存）
- 可选爬虫安装：`pip install crawl4ai && crawl4ai-setup` / `pip install playwright && playwright install chromium` / `.env` 设 `FIRECRAWL_API_KEY`——不装则 urllib 兜底

## 已知限制

- GitHub Search secondary rate limit：30 req/min。所有 search 查询间已加 2s 间隔 + 限流自动退避；trending 补全走 core API（5000/hr）不占 search 配额。
- 翻译质量依赖 Google Translate，长 description 偶尔不通顺。原始英文在详情里可查看。
- 分类基于 topic/name 关键词，不读 README 语义判断。
- 24h 增长（`/api/gain`）需要连续多天定时 crawl 积累快照，冷启动首日无数据（UI 有提示）。

## 升级路径

- 接 LLM 做语义解读 + 摘要（每个 repo 一句话）
- 多日数据对比，识别"昨天新冒出的项目"
- 自动 PR / 周报推送（基于 hot_now 增量）
