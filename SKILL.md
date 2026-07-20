---
name: lodestone
description: 当用户想了解 GitHub 上最新的 AI 热门项目/工具/Skills（如 superpowers、agent-memory、LangChain 等）时触发。自动爬取 GitHub AI 趋势，按用途分类（Agent/RAG/代码生成/微调等），生成中文仪表盘。触发短语：「看看最新AI项目」「AI radar」「GitHub AI趋势」「刷一下AI雷达」「最近有什么火的AI项目」。
allowed-tools: Bash, Read, Write, Edit
---

# Lodestone · GitHub AI 趋势雷达

每日 GitHub AI 热门仓库自动雷达 · 已为 AI 应用工程师分类整理 · 中文友好

> **跨平台**：本 skill 同时兼容 **Claude Code** (`~/.claude/skills/`) 和 **Codex CLI** (`~/.codex/skills/`)。`SKILL.md` 格式两边相同，通过 `./install.sh` 一次安装双端可用。

## 何时使用本 skill

- 用户问"最近 GitHub 上有什么火的 AI 项目？"
- 用户想了解某个 AI 领域（agent/RAG/微调…）的最新开源工具
- 用户想刷新一次雷达数据并生成仪表盘
- 用户想看 superpowers 这种 skills 的最新同类项目

## 一键执行

```bash
# skill 安装后，从任意 cwd 都可调用
~/.claude/skills/lodestone/radar.py all      # Claude Code 用户
~/.codex/skills/lodestone/radar.py all      # Codex CLI 用户
# 或通过 symlink 解析后的绝对路径调用
```

> 安装器创建的是 symlink（不是复制），所以两个路径指向同一个源目录，编辑一处即时生效。

## 子命令

| 命令 | 作用 |
|------|------|
| `radar.py crawl` | 拉取 GitHub Search API → 翻译 → 写入 `data/YYYY-MM-DD.json` + `data/latest.json` |
| `radar.py render` | 从 `data/latest.json` 重新生成 `out/index.html` |
| `radar.py serve [port]` | 起静态服务器（默认 8765） |
| `radar.py today` | 终端打印今日 Top 15 + 分类概览 |
| `radar.py all` | crawl + render + 浏览器打开 |

## 分类（9 类自动归类）

1. 🤖 **AI Agent & Skills** — agent、claude-code、MCP、autonomous、multi-agent
2. 🧠 **RAG / Memory / Vector** — vector-db、agent-memory、embedding
3. 💬 **LLM Interface & Chat** — LLM SDK、chatbot、prompt-engineering、claude-api
4. ⚙️ **Code Generation & Dev Tools** — copilot、ai-coding、code-agent
5. 🔗 **Workflow & Orchestration** — langgraph、langchain、pipeline
6. 🎨 **Multimodal** — vision、text-to-video、multimodal
7. 🏋️ **Fine-tuning & Training** — LoRA、PEFT、llama-factory
8. 📊 **Eval & Benchmark** — llm-evaluation、benchmark
9. ⭐ **Awesome Lists** — awesome-ai、awesome-llm、awesome-claude

## 数据 schema（`data/latest.json`）

```json
{
  "date": "2026-07-19",
  "fetched_at": "2026-07-19T17:58:20",
  "total_unique": 224,
  "categories": [{
    "id": "agent", "name": "...", "desc": "...",
    "repos": [{
      "name": "owner/repo", "desc": "英文原描述", "desc_zh": "中文翻译",
      "plain": "人话解读（topic 驱动）", "url": "...",
      "stars": 12345, "lang": "Python", "topics": [...]
    }]
  }],
  "hot_now": [ /* top 40 全站去重 */ ]
}
```

## 技术栈（两种 UI 模式）

### 模式 A：极简静态 HTML（默认，零构建）

- **Tailwind CDN** + **DaisyUI**（最主流 Tailwind 组件库）+ **Lucide**（图标）
- 单文件 HTML 输出，无构建步骤
- 翻译走 Google Translate 免费端点（`data/zh_cache.json` 持久化缓存）

### 模式 B：Vue 3 SPA（`frontend/`）

- **Vue 3** + **Vite** + **Element Plus**（最主流 Vue 3 组件库）+ **lucide-vue-next**
- 读 `data/latest.json`，组件化渲染
- 启动：`cd frontend && npm install && npm run dev`

## 依赖

- Python 3.10+（仅用 stdlib + urllib）
- `gh` CLI 已认证（`gh auth status`）
- 网络可达 github.com + translate.googleapis.com

## 已知限制

- GitHub Search secondary rate limit：30 req/min。`crawl` 跑完约 30 查询，踩线。冷却几分钟重试。
- 翻译质量依赖 Google Translate，长 description 偶尔不通顺。原始英文在 modal 里可折叠查看。
- 分类基于 topic/name 关键词，不读 README 语义判断。

## 升级路径

- 接 LLM 做语义解读 + 摘要（每个 repo 一句话）
- 接入 GitHub Trending HTML 抓取作补充数据源
- 多日数据对比，识别"昨天新冒出的项目"
- 自动 PR / 周报推送（基于 hot_now 增量）