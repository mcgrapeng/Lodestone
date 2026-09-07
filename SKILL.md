---
name: zp
description: 当用户想了解 GitHub + HuggingFace + MCP Registry + arXiv 上最新的 AI 工具/Skills/项目（如 superpowers、agent-memory、LangChain、Coze 等）时触发。Lodestone（命令 /zp）是专门发现主流 AI 工具的多源聚合平台 — 自动聚合 GitHub AI 趋势（GraphQL 批量搜索 + 4 引擎分级爬取）+ HuggingFace Trending（Spaces + Models）+ 官方 MCP Server Registry + arXiv 最新论文，按 20 个用途分类（Agent/RAG/代码生成/MCP/Voice/Security/Robotics/论文 等），生成中文友好仪表盘。触发命令：「/zp」。触发短语：「看看最新AI项目」「AI radar」「GitHub AI趋势」「刷一下AI雷达」「最近有什么火的AI项目」。
allowed-tools: Bash, Read, Write, Edit
---

# Lodestone · GitHub + HuggingFace + MCP Registry 多源 AI 工具发现平台

每日 GitHub AI 热门仓库 + HuggingFace Trending（Spaces + Models）+ 官方 MCP Server Registry 自动聚合 · 已为 AI 应用工程师分类整理 · 中文友好

> **跨平台**：本 skill 同时兼容 **Claude Code** (`~/.claude/skills/`) 和 **Codex CLI** (`~/.codex/skills/`)。`SKILL.md` 格式两边相同，通过 `./install.sh` 一次安装双端可用。

## 何时使用本 skill

- 用户问"最近 GitHub 上有什么火的 AI 项目？"
- 用户想了解某个 AI 领域（agent / RAG / 微调…）的最新开源工具
- 用户想刷新一次雷达数据
- 用户想看 superpowers 这种 skills 的最新同类项目
- 用户想找最新的 MCP server / 浏览器代理 / 语音 agent 等细分赛道
- 用户想看 HuggingFace 上今天最火的模型权重

## 一键执行

```bash
# skill 安装后，从任意 cwd 都可调用
~/.claude/skills/zp/radar.py crawl    # 爬取 + 入库（约 5-8 分钟，含限速等待）
~/.claude/skills/zp/radar.py today    # 终端直接看 Top 15 + 分类概览
```

> 安装器创建的是 symlink（不是复制），所以两个路径指向同一个源目录，编辑一处即时生效。

## 子命令

| 命令 | 作用 |
|------|------|
| `radar.py crawl` | 拉取 GitHub（分类 + 5k 补捞 + trending + manual seed）+ HuggingFace Spaces + HuggingFace Models + MCP Registry → 翻译 → 写入 Postgres（无 PG 时回退 `data/latest.json`） |
| `radar.py today` | 终端打印 Top 15 + 分类概览（PG 优先，latest.json 回退） |
| `radar.py serve [port]` | 起 JSON API（默认 8765，**仅绑定 127.0.0.1**） |

crawl 全程持文件锁（`data/crawl.lock`），并发触发会自动拒绝，不会互相打爆 GitHub 限流。

## 数据源（4 个 — 互补且独立）

| 源 | API | 价值 |
|---|-----|------|
| **GitHub Topics + Search + Trending** | `gh api` + `github.com/trending` HTML | 主流开源 AI 项目主战场 |
| **HuggingFace Spaces Trending** | `api/spaces?sort=trending` | 社区精选 AI 应用 demo |
| **HuggingFace Models Trending** | `api/models?sort=likes7d` | 模型权重排行（Qwen / Llama / DeepSeek） |
| **MCP Server Registry** | `registry.modelcontextprotocol.io/v0/servers` | Model Context Protocol 官方注册表 |

新增源（MCP Registry + HF Models）不依赖 GitHub — 即使 GitHub 抗爬也能完整覆盖 MCP 与模型权重。

## 20 个分类

| 编号 | 分类 |
|---|---|
| 1 | 🤖 AI Agent & Skills（agent / claude-code / MCP / autonomous / multi-agent） |
| 2 | 🧠 RAG / Memory / Vector（vector-db / agent-memory / embedding） |
| 3 | 💬 LLM Interface & Chat（LLM SDK / chatbot / prompt-engineering / claude-api） |
| 4 | ⚙️ Code Generation & Dev Tools（copilot / ai-coding / code-agent） |
| 5 | 🔗 Workflow & Orchestration（langgraph / langchain / pipeline） |
| 6 | 🎨 Multimodal（vision / text-to-video / vision-language-model） |
| 7 | 🏋️ Fine-tuning & Training（LoRA / PEFT / llama-factory） |
| 8 | 📊 Eval & Benchmark（llm-evaluation / benchmark） |
| 9 | 💻 AI IDE & 编辑器（cursor / aider / cline / continue） |
| 10 | 🌐 LLM Gateway & Router（litellm / openrouter / llm-proxy） |
| 11 | 🔍 LLM 可观测 & Tracing（langfuse / helicone / llmops） |
| 12 | ⭐ Awesome Lists & Plugins（awesome-ai / claude-plugins 生态） |
| 13 | 🔌 MCP Servers & Clients（Model Context Protocol 服务端/客户端） |
| 14 | 🎙 Voice AI / Realtime（LiveKit / Pipecat / Vocode） |
| 15 | 🖥 Browser Use / Computer Use（browser-automation / computer-use agent） |
| 16 | 🤗 HuggingFace 热门 Spaces（trendingScore 排行） |
| 17 | 🤗 HuggingFace 热门 Models（7 天 likes 排行） |
| 18 | 🛡 AI 安全 & 隐私（prompt injection 防御 / 红队 / 水印） |
| 19 | 🤖 机器人 / Embodied AI（具身智能 / sim-to-real / 机器人学习） |
| 20 | 📄 arXiv 论文（cs.AI / cs.CL / cs.LG 最新提交，官方 Atom API） |

## 4 精选爬虫引擎 · 分级 fallback

httpx → cloudscraper → playwright_stealth → jina（本地轻 → 本地重 → 云端），
每级结果过质量门（长度 + bot 特征 + 页面结构标记），不过才升级更重的引擎 —
日常爬取不启动浏览器。引擎清单见 `config.toml [orchestrator].priority`（唯一
白名单，其余 10 个适配器停用但保留）。详细策略见 [使用手册 § 4](使用手册.md#4-爬虫引擎4-精选分级-fallback)。

## 数据存储（Postgres 优先）

- **PG 模式**（`pip install pg8000` + `.env` 配置）：表 `repos` / `repo_categories` / `repo_stars_history` / `crawl_log`（含 `queries_zh` 字段、`scrapers_failed` 数据质量字段）。首次 crawl 自动建库建表。
- **JSON 回退**（无 pg8000 或 PG 不可达）：写 `data/latest.json`，`serve`/`today` 自动回退读取。
- 凭据放 `.env`（参照 `.env.example`），**不进 git**。

## 已知限制

- GitHub Search secondary rate limit：30 req/min。所有 search 查询间已加 2s 间隔 + 限流自动退避；MCP / HF 源不占 Search 配额。
- 翻译质量依赖 Google Translate（无 LLM 介入），是字面翻译不是 AI 总结；`summary_zh` 字段提取首句作为一句话中文。
- 分类基于 topic/name 关键词 + AI hints 兜底，不读 README 语义判断。
- 24h 增长（`/api/gain`）需要连续多天定时 crawl 积累快照，冷启动首日无数据（UI 有提示）。

## 升级路径

- 接 LLM 做语义解读 + 摘要（每个 repo 一句话）—— 需要接 Claude/GPT API
- 多日数据对比，识别"昨天新冒出的项目项目"
- 自动 PR / 周报推送（基于 hot_now 增量）
- 跨源信号融合：同一 repo 在 GitHub + MCP Registry + HF 都出现时加权
- 实时监控 daemon（分钟分钟级发现，而非每日）