# ⚡ Lodestone

**GitHub + HuggingFace 双源 AI 工具发现平台** — 围绕 AI 应用开发生态
（Skills / Plugins / Agent / RAG / IDE / Gateway / 可观测…），按 16 个用途分类，
每日自动聚合主流与新兴的 AI 项目，自动翻译为中文。

Python 数据层（`radar.py` + `db/`）+ Vue 3 SPA 前端。可作为 **Claude Code** 与
**Codex CLI** 的 skill 安装。

---

## 安装为 Skill（Claude Code + Codex CLI）

```bash
cd lodestone        # 项目根目录
./install.sh
```

`install.sh` 在 `~/.claude/skills/lodestone` 和 `~/.codex/skills/lodestone` 各创建一个指向本项目的 **symlink**（非复制），两端读同一份 `radar.py` / `data/`。

安装后在任一 CLI 里说「刷一下 AI 雷达」即可触发（触发短语见 `SKILL.md`）。

卸载：`./uninstall.sh`。

> symlink 而非复制：项目含 `node_modules/`，复制到两处会重复占用磁盘，且改一处需手动同步。

---

## 配置

```bash
cp .env.example .env     # 填入你的 Postgres 连接信息（.env 已 gitignore）
pip install -r requirements.txt   # 仅 pg8000，可选 —— 没有它自动降级为 JSON 模式
```

- **Postgres 模式**（推荐）：历史快照 + 24h star 增长 + 分页查询。首次 crawl 自动建库建表。
- **JSON 回退模式**：无 pg8000 / PG 不可达时，写 `data/latest.json`，功能不中断。

**可选强力爬虫**（github.com/trending 抓取更稳，任意子集即可，自动探测）：

```bash
pip install crawl4ai && crawl4ai-setup        # 本地浏览器引擎
pip install playwright && playwright install chromium   # 本地 Chromium 兜底
# firecrawl：无需 pip —— .env 里设 FIRECRAWL_API_KEY，或已装 firecrawl CLI 即可
```

**所有爬虫的配置（timeouts / User-Agent / 优先级 / 选择策略）都在
`config.toml` 里** —— 改完重启即生效，不需要碰代码。Secret (API key)
仍然放 `.env`。

```toml
[orchestrator]
wall_clock_timeout = 60     # 一次 fetch 的整体超时（秒）
selection_strategy = "longest"  # "longest" | "first"

[timeouts]   # 每个 engine 的超时（秒）
firecrawl = 120
playwright = 60
trafilatura = 60
...

[user_agents] # 每个 engine 的 HTTP User-Agent
```

不装任何爬虫时自动回退 stdlib urllib，功能不中断。

依赖：Python 3.10+、`gh` CLI 已认证（`gh auth status`）、网络可达 github.com + translate.googleapis.com。

---

## 直接启动（不装 skill）

### 全栈：Vue 3 SPA + Python API

```bash
cd frontend
npm install        # 首次
npm run dev        # → http://localhost:5173
```

`npm run dev` 运行 `dev.cjs`（Node stdlib，48 行），并行做两件事：

1. `python radar.py serve 8765` —— API 服务器（**仅绑定 127.0.0.1**）
2. 本地 `vite` —— 开发服务器（`:5173`），`/api/*` 代理到 `:8765`（见 `vite.config.js`）

`Ctrl-C` 同时关闭两个进程。

前端（`src/App.vue`）行为：

- 每 30s 轮询 `/api/data`
- 「刷新」按钮 —— 立即重新拉取
- 「重新爬取」按钮 —— 触发后台 `crawl`（服务端文件锁防并发，进行中返回 409）
- 本机 Skills 面板 —— 扫描 `~/.claude/skills` + `~/.codex/skills` + plugins + MCP（`/api/local`）
- repo 抽屉内「一键安装为 Skill（Claude + Codex）」
- 替代推荐 —— 基于 vertical topic 锚点为已装 skill 找更强的同类

### 只跑数据层

```bash
./radar.py crawl        # 拉 GitHub + 翻译 → 写 PG（无 PG 时写 data/latest.json）
./radar.py today        # 终端打印 Top 15 + 分类（PG 优先，JSON 回退）
./radar.py serve 8765   # 单跑 API
```

---

## 命令一览

| 命令 | 作用 |
|------|------|
| `cd frontend && npm run dev` | 全栈启动（Python API + Vite） |
| `cd frontend && npm run vite-only` | 只启动 Vite |
| `cd frontend && npm run build` | 打包到 `frontend/dist/` |
| `./radar.py crawl` | GitHub 分类查询 + 5k 补捞 + trending + manual seed → 翻译 → 入库 |
| `./radar.py today` | 终端打印今日 Top 15 + 分类概览 |
| `./radar.py serve [port]` | 单跑 API server（默认 8765，loopback only） |

测试：`python3 -m tests.test_radar`（无依赖）· `python3 -m tests.test_db`（需 PG，无则自动跳过）· `python3 -m tests.test_scrapers`（无依赖）

---

## 技术栈

**后端（`radar.py` + `db/`，Python 3.10+）**

- 依赖 `gh` CLI 调 GitHub API（走认证通道）
  - Search API 查询间 sleep 2s（限流命中后自适应升到 6s）+ 403 自动退避重试，失败数记入 `crawl_log.queries_failed`
  - trending 补全走 core API（5000/hr），不占 Search 配额
- **trending 页面抓取三级引擎**（`scrapers/`，移植自 youzi skill 的 adapter 架构）：
  firecrawl（远程 API/CLI）→ crawl4ai（本地浏览器）→ playwright（本地 Chromium）→ urllib（stdlib 兜底）——串行降级，第一个返回可解析 HTML 的引擎胜出；全部失败再回退 search-API 代理
- 描述经 Google Translate 免费端点翻译，缓存到 `data/zh_cache.json`
- 存储：Postgres（pg8000）优先，`data/latest.json` 自动回退
- API server 基于 `http.server.ThreadingHTTPServer`：
  - **仅绑定 127.0.0.1**（API 可 git-clone 安装 skill，不可暴露局域网）
  - **POST 端点校验 Origin**（非 localhost 的跨站请求 403，防 drive-by 安装）
  - 端点：`/api/data`、`/api/local`、`/api/top`、`/api/gain`、`/api/workbuddy`、`/api/install`、`/api/install-cli`、`/api/crawl`、`/api/local/origin`、`/api/local/replace`
- `crawl` 全程文件锁（`data/crawl.lock`，30 分钟陈旧自动抢占）

**前端（`frontend/`）**

- Vue 3 + Vite
- Element Plus（`el-tag` / `el-drawer` / `el-button` / `el-message`）
- `lucide-vue-next` 图标
- Tailwind CSS + PostCSS
- CSS-only aurora 背景（径向渐变 blob + 网格 overlay）

---

## 16 个分类

分类在 `radar.py` 顶部的 `CATEGORIES` 列表中定义，每类对应一组 GitHub 查询（`huggingface` 例外，走 HF 公共 API）：

1. 🤖 AI Agent & Skills
2. 🧠 RAG / Memory / Vector
3. 💬 LLM Interface & Chat
4. ⚙️ Code Generation & Dev Tools
5. 🔗 Workflow & Orchestration
6. 🎨 Multimodal (Vision / Audio / Video)
7. 🏋️ Fine-tuning & Training
8. 📊 Eval & Benchmark
9. 💻 AI IDE & 编辑器
10. 🌐 LLM Gateway & Router
11. 🔍 LLM 可观测 & Tracing
12. ⭐ Awesome Lists & Plugins（含 Claude 插件市场生态）
13. 🔌 MCP Servers & Clients（Model Context Protocol 生态）
14. 🎙 Voice AI / Realtime（LiveKit / Pipecat / Vocode 系）
15. 🖥 Browser Use / Computer Use（浏览器自动化 + Computer-Use agent）
16. 🤗 🤗 HuggingFace 热门（社区精选 trendingScore 排行）

另有 `TOP_5K_QUERIES`（90 条广域补捞）+ `MANUAL_SEED_REPOS`（人工保底）+ GitHub Trending daily/weekly（新星捕捉），三层 AI 相关性过滤（HARD topic / 文本提示 / 噪音黑名单）。**双数据源**：GitHub Topics + HuggingFace Spaces Trending。

---

## 定时刷新

### macOS launchd

将 `PROJECT_DIR` 替换为项目绝对路径：

```bash
cat > ~/Library/LaunchAgents/com.lodestone.daily.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.lodestone.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>PROJECT_DIR/radar.py</string>
    <string>crawl</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>WorkingDirectory</key><string>PROJECT_DIR</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.lodestone.daily.plist
```

### Linux cron

```cron
0 8 * * * cd /path/to/lodestone && ./radar.py crawl >/dev/null 2>&1
```

> 定时用 `crawl` 只更新数据；SPA 每 30s 自动轮询到新数据。连续多天 crawl 后，`/api/gain`（24h star 增长榜）会自动有数据。

---

## 目录结构

```
lodestone/
├── SKILL.md              # skill 入口（frontmatter: name + description）
├── radar.py              # Python 爬取/API/安装逻辑（stdlib）
├── requirements.txt      # pg8000（可选，PG 模式）
├── .env.example          # PG 连接模板（cp 到 .env 填写，gitignored）
├── install.sh            # 创建 ~/.claude/skills + ~/.codex/skills symlink
├── uninstall.sh          # 移除 symlink
├── db/
│   ├── connection.py     # pg8000 连接 + .env 加载 + 建库
│   ├── repos.py          # upsert / 查询 / gain 计算等数据访问
│   └── schema.sql        # 幂等建表 SQL
├── scrapers/             # 可选强力爬虫（移植自 youzi，串行降级链）
│   ├── __init__.py       # fetch_html(url) → (html, engine)
│   ├── firecrawl_scraper.py
│   ├── crawl4ai_scraper.py
│   └── playwright_scraper.py
├── data/
│   ├── latest.json       # JSON 回退模式快照（PG 不可用时）
│   ├── zh_cache.json     # 翻译缓存
│   ├── crawl.lock        # crawl 文件锁（运行时存在）
│   └── crawl.log         # 后台 crawl 输出
├── tests/
│   ├── test_radar.py     # 爬取/过滤/安装/锁（stdlib-only）
│   └── test_db.py        # db 层（需 PG，无则跳过）
└── frontend/             # Vue 3 SPA
    ├── package.json
    ├── dev.cjs           # Node stdlib 编排器 — 并行起 Python + Vite
    ├── vite.config.js    # /api/* → :8765 代理
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue       # 主组件 — fetch + 30s 轮询 + 本机 Skills + 一键安装
        └── style.css
```

---

## 已知限制

- **GitHub Search 二级限流**：约 30 req/min。查询间已加 2s 间隔 + 403 退避重试；偶发失败会记入 `crawl_log.queries_failed`，下轮 crawl 自然补齐。
- **翻译质量**：长 description 偶尔不通顺；原始英文可在详情里查看。
- **分类粒度**：基于 topic / name 关键词匹配，不读 README 语义。误分类时改 `radar.py` 的 `CATEGORIES`。
- **24h 增长榜冷启动**：依赖连续多天的 stars 快照积累，第一天为空（UI 有提示）。
