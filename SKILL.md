---
name: yz-ai
description: 当用户想了解 GitHub + HuggingFace + MCP Registry + arXiv 上最新的 AI 工具/Skills/项目（如 superpowers、agent-memory、LangChain、Coze 等）时触发。Lodestone（命令 /lodestone）是发现主流 AI 工具的多源聚合平台 — 自动聚合 GitHub AI 趋势（GraphQL 批量搜索 + 4 引擎分级爬取）+ HuggingFace Trending（Spaces + Models）+ 官方 MCP Server Registry + arXiv 最新论文，按 20 个用途分类（Agent/RAG/代码生成/MCP/Voice/Security/Robotics/论文 等），生成中文友好仪表盘。**2026-09 P3 拆分：/lodestone 只触发「启动 serve + 爬取数据」，5 桶中文介绍改由用户在 Settings 配置好模型地址（Anthropic / OpenAI 兼容 / Ollama）后，在前端点「生成 5 桶分析」按钮手动触发**。这样不污染宿主 LLM 上下文、不烧用户额度、可重复增量跑。「lodestone」（磁石）：航海家用磁石导航 — 这个 skill 把 AI 工程师引到该用的人工工具上。触发短语：「/lodestone」「看看最新AI项目」「AI radar」「GitHub AI趋势」「刷一下AI雷达」「最近有什么火的AI项目」。
allowed-tools: Bash, Read, Write, Edit
---

# Lodestone · GitHub + HuggingFace + MCP Registry 多源 AI 工具发现平台

每日 GitHub AI 热门仓库 + HuggingFace Trending（Spaces + Models）+ 官方 MCP Server Registry 自动聚合 · 已为 AI 应用工程师分类整理 · 中文友好

> **Lodestone**（磁石 / 罗盘石）：古代航海家用天然磁铁矿导航 — 指向正确方向。**这个 skill 是 AI 工程师的"磁石"**：穿过 GitHub / HuggingFace / MCP / arXiv 的数据洋流，把你引到该用的人工工具上。
>
> **跨平台**：本 skill 同时兼容 **Claude Code** (`~/.claude/skills/`)、**Codex CLI** (`~/.codex/skills/`)、**OpenCode** (`~/.config/opencode/skills/`)、**EasyCode** (`~/.easycode/skills/`)。`SKILL.md` 格式两边相同，通过 `./install.sh` 一次安装多端可用。

## 何时使用本 skill

- 用户问"最近 GitHub 上有什么火的 AI 项目？"
- 用户想了解某个 AI 领域（agent / RAG / 微调…）的最新开源工具
- 用户想刷新一次数据
- 用户想看 superpowers 这种 skills 的最新同类项目
- 用户想找最新的 MCP server / 浏览器代理 / 语音 agent 等细分赛道
- 用户想看 HuggingFace 上今天最火的模型权重
- 用户希望每张卡片都有 5 桶详细中文介绍（直接由宿主 LLM 生成，无外部 API key）

## `/lodestone` 命令流程

`/lodestone` 是用户的入口命令。**触发后，宿主 LLM（Claude Code / Codex / OpenCode / EasyCode 调用的模型）**自动执行以下步骤：

1. **检测 serve 是否在跑**：`GET http://127.0.0.1:8765/api/health` → 看 `uptime_seconds` 判断
2. **如在跑 → 杀掉旧进程重启**：`POST http://127.0.0.1:8765/api/restart`
   - 后端独立子进程执行 kill + spawn 新 serve,旧进程安全死掉
   - 返回 `{"ok": true, "status": "restarting"}` 给 skill
   - 新 serve 大约 5s 内 listen 上 `/api/health`
3. **触发爬取**：`POST http://127.0.0.1:8765/api/crawl`
   - 后端后台 spawn `radar.py crawl` 子进程（fire-and-forget,不阻塞 skill）
   - 爬 5 个数据源（GitHub / HF Spaces / HF Models / MCP Registry / arXiv）+ 抓 README 缓存 + 入库到 PG（回退到 `data/latest.json`）
   - 约 5-8 分钟完成；skill 不等,告诉用户后即退出
4. **告知用户下一步**（关键变化 — 2026-09 P3）：
   - 「**爬取已触发,请打开仪表盘配置模型地址**」
   - 仪表盘 URL: `http://127.0.0.1:8765`
   - 操作: 右上角齿轮 ⚙️ 打开 Settings → 选 Provider (Anthropic / OpenAI 兼容 / Ollama) → 填 Base URL + API Key + Model → 点「保存」
   - 配置完成后点 Settings 抽屉里的「生成 5 桶分析」按钮（或终端跑 `radar.py summarize`）
5. **skill 退出**,不再做任何 LLM 调用

> **为什么拆开**？原流程让宿主 LLM 实时为每张卡生成 5 桶 — 对 hot_now 60+ 卡就是 60+ 次模型调用,污染上下文、慢、还要重复跑就重头算。改成本地配置的 LLM 后端（Anthropic/OpenAI/Ollama）独立跑批:
> - 跑一次后写回 PG + latest.json,前端永久拿到 analysis_5d
> - 不占宿主 LLM 上下文
> - 用户用便宜模型(haiku / gpt-4o-mini / qwen2.5)按需刷,不烧用户额度
> - 增量分析:cache 命中跳过,二次跑只算新加的卡

> **为什么先检查+重启**？如果旧 serve 跑着旧代码（无 `analysis_5d` / `summary_sections` 字段），前端 UI 显示老数据。重启确保代码与新功能一致。

> **5 桶由谁填**？默认流程走**用户配置的 LLM 后端**（Anthropic / OpenAI 兼容 / Ollama）。后端检测:
> 1. settings.json 有 `provider` + 必填字段 → 用该 provider
> 2. 否则环境变量 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST` → 自动选
> 3. 都没配 → summarize 报 `no provider configured` 错,前端按钮变灰 + 引导去 Settings
>
> 老的 `/api/save_summary_batch` 端点保留 — 如果用户想用宿主 LLM 现场填,可以 POST items 手动写回,与新的 summarize 路径不冲突。

## 一键执行（手动命令）

```bash
# skill 安装后，从任意 cwd 都可调用
~/.claude/skills/lodestone/radar.py web         # 一键仪表盘：后台起 serve + 自动打开浏览器（已在跑则直接打开）
~/.claude/skills/lodestone/radar.py crawl       # 爬取 + 入库（约 5-8 分钟，含限速等待）。**2026-09 P3:不再自动跑 LLM**
~/.claude/skills/lodestone/radar.py summarize   # 单独跑 LLM 5 桶分析（读已爬数据 + 用已配 provider + 写回 PG/JSON）
~/.claude/skills/lodestone/radar.py today       # 终端直接看 Top 15 + 分类概览
```

> 安装器创建的是 symlink（不是复制），所以两个路径指向同一个源目录，编辑一处即时生效。

## 子命令

| 命令 | 作用 |
|------|------|
| `radar.py web [port]` | 一键仪表盘：检测到 serve 已在跑就直接开浏览器，否则后台拉起（detached）再开。幂等，重复执行无副作用 |
| `radar.py crawl` | 拉取 GitHub（分类 + 5k 补捞 + trending + manual seed）+ HuggingFace Spaces + HuggingFace Models + MCP Registry → 抓 README → 写 Postgres（无 PG 时回退 `data/latest.json`）。**2026-09 P3:不再自动跑 LLM**，需要走 `--with-llm` |
| `radar.py crawl --with-llm` | 同上 + 顺带跑 5 桶分析（旧行为兼容） |
| `radar.py summarize` | 单独跑 LLM 5 桶分析（读 PG/JSON 已有 repos,用 settings.json 的 provider）。前端 Settings 抽屉按钮和 `/api/llm/summarize` 都调它 |
| `radar.py today` | 终端打印 Top 15 + 分类概览（PG 优先，latest.json 回退） |
| `radar.py serve [port]` | 起 JSON API + 静态托管 `frontend/dist`（默认 8765，**RADAR_HOST 控制绑定地址**；默认 127.0.0.1 安全） |
| `radar.py restart [port]` | **杀掉端口上的旧 serve + 启动新 detached serve + 等就绪**。`/lodestone` skill 自动调此（或通过 `POST /api/restart` HTTP endpoint） |

crawl / summarize 各持独立文件锁（`data/crawl.lock` / `data/summarize.lock`），并发触发会自动拒绝，不互相打爆 GitHub 限流或 LLM 配额。

## LLM 5 桶相关端点

| 端点 | 方法 | 作用 |
|---|---|---|
| `/api/settings` | GET/POST | 读写 settings.json（provider + 各 provider 字段） |
| `/api/llm/test` | POST | 用 provider + 临时字段测试连通性（不落盘） |
| `/api/llm/status` | GET | 当前 provider 是否配置 + 上次生成于何时 + 跑了多少张卡 |
| `/api/llm/summarize` | POST | 后台 spawn `radar.py summarize`,立即返 200 |
| `/api/save_summary_batch` | POST | 老的宿主 LLM 路径 — items 数组一次写多张卡（与新 summarize 不冲突,作为可选手动路径保留） |

## 数据源（5 个 — 互补且独立）

| 源 | API | 价值 |
|---|-----|------|
| **GitHub Topics + Search + Trending** | `gh api` + `github.com/trending` HTML | 主流开源 AI 项目主战场 |
| **HuggingFace Spaces Trending** | `api/spaces?sort=trending` | 社区精选 AI 应用 demo |
| **HuggingFace Models Trending** | `api/models?sort=likes7d` | 模型权重排行（Qwen / Llama / DeepSeek） |
| **MCP Server Registry** | `registry.modelcontextprotocol.io/v0/servers` | Model Context Protocol 官方注册表 |
| **arXiv 论文** | `export.arxiv.org/api/query` | cs.AI / cs.CL / cs.LG 最新提交 |

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
| 20 | 📄 arXiv 论文（cs.AI / cs.CL / cs.LG 最新提交） |

## 4 精选爬虫引擎 · 分级 fallback

httpx → cloudscraper → playwright_stealth → jina（本地轻 → 本地重 → 云端），
每级结果过质量门（长度 + bot 特征 + 页面结构标记），不过才升级更重的引擎 —
日常爬取不启动浏览器。引擎清单见 `config.toml [orchestrator].priority`（唯一
白名单，其余 10 个适配器停用但保留）。详细策略见 [使用手册 § 4](使用手册.md#4-爬虫引擎4-精选分级-fallback)。

可选适配器（在 `scrapers/` 里有统一 `is_available()` + `scrape()` 接口，装上即
可加入白名单启动）：

- **firecrawl** — REST API（远程云端渲染），无需本地浏览器，最快
- **crawl4ai** — 开源本地浏览器爬虫，`pip install crawl4ai && crawl4ai-setup`
- **playwright** — Chromium 真浏览器，`pip install playwright && playwright install chromium`

## 数据存储（Postgres 优先）

- **PG 模式**（`pip install pg8000` + `.env` 配置）：表 `repos` / `repo_categories` / `repo_stars_history` / `crawl_log`（含 `queries_zh` 字段、`scrapers_failed` 数据质量字段）。首次 crawl 自动建库建表。
- **JSON 回退**（无 pg8000 或 PG 不可达）：写 `data/latest.json`，`serve`/`today` 自动回退读取。
- 凭据放 `.env`（参照 `.env.example`），**不进 git**。

## 部署到任意服务器

- 默认绑 `127.0.0.1`（安全：API 能 `git clone` 你的 skill 目录，不暴露到内网）
- 服务器部署：`.env` 里设 `RADAR_HOST=0.0.0.0`，前面套 nginx 做 TLS
- skill 缓存重定向：`AI_RADAR_HOME=/var/lib/lodestone`（多用户服务器）
- PG 部署：`PGHOST=10.0.0.5` 等标准 PG* 环境变量
- `gh` CLI 必须已认证（服务器部署前 `gh auth login`）

## 已知限制

- GitHub Search secondary rate limit：30 req/min。所有 search 查询间已加 2s 间隔 + 限流自动退避；MCP / HF 源不占 Search 配额。
- 5 桶中文介绍（2026-09 P3）由用户在 Settings 配置的 LLM 后端生成 — 需要 API key + 可达 base_url。未配置时 summarize 报 `no provider configured`,前端按钮自动禁用 + 引导。
- 24h 增长（`/api/gain`）需要连续多天定时 crawl 积累快照，冷启动首日无数据（UI 有提示）。