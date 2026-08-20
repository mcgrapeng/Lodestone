# Lodestone · 使用手册

> 每日 GitHub AI 热门仓库自动雷达 · 已为 AI 应用工程师分类整理 · 中文友好

---

## 1. 项目简介

**Lodestone** 是一个 Python stdlib 为主的轻量级爬虫 + Vue 3 SPA，专注一件事：

> 每天抓 GitHub 上围绕 **AI 应用开发** 场景最热门、最活跃的仓库（skills / plugins /
> Agent / RAG / IDE / Gateway / 可观测性…），按用途分 12 类，自动翻译成中文，
> 提供终端、JSON API、可视化仪表盘三种消费方式。

底层集成了 `firecrawl` · `crawl4ai` · `playwright` 三个主流爬虫引擎，按 **并行**
方式运行（不只是按顺序降级）— 三个引擎同时开跑，谁先抓到非空 HTML 不再是赢家，
而是按 **"最完整 HTML 胜出"** 的策略挑选结果：firecrawl 抓得快、crawl4ai 抓得干净、
playwright 抓得最完整，三者互补而不是抢先后停止。

适配器代码移植自 `ailibrary/youzi` skill（同样作为 Claude Code / Codex CLI skill），
按 lodestone 的精简需求（只需要 raw HTML，不需要 markdown / screenshot / 抽取）做了
裁剪，整体仍然是 stdlib + 可选依赖，不强制安装即可运行。

---

## 2. 安装

### 2.1 系统要求

| 项 | 要求 |
|----|------|
| 操作系统 | macOS / Linux（Windows 需要 WSL） |
| Python | ≥ 3.10 |
| Node.js | ≥ 18（仅前端需要） |
| `gh` CLI | 已认证（`gh auth login`）— 用于 GitHub Search API |
| 网络 | 可达 `github.com` 与 `translate.googleapis.com` |

### 2.2 安装为 Skill（Claude Code + Codex CLI）

```bash
cd /path/to/lodestone
./install.sh
```

**安装行为**：
- 在 `~/.claude/skills/lodestone` 和 `~/.codex/skills/lodestone` 各创建一个 **symlink**，
  指向本项目目录。两端读同一份代码与数据。
- 如果已存在同名目录（非 symlink），自动备份为 `lodestone.bak.<timestamp>` 后再覆盖。
- symlink 不会复制 `node_modules/`、`data/`、`frontend/dist/`，避免磁盘浪费与数据漂移。

安装完成后，**两边 CLI 都生效**：

| 触发短语 |
|----------|
| 刷一下 AI 雷达 / 看看最新 AI 项目 / 最近有什么火的 AI 项目 / AI radar / GitHub AI 趋势 |

### 2.3 安装可选爬虫引擎

lodestone 默认用 stdlib `urllib` 就能跑（github.com/trending 的非 JS 渲染会拿不到），但
强烈建议至少装一个真实浏览器引擎，三个可以并行互补：

```bash
# (推荐) firecrawl — 远程 API，最快，无需本地浏览器
# 方式 1：API key
echo 'FIRECRAWL_API_KEY=fc-xxxx' >> .env
# 方式 2：firecrawl CLI（已登录用户）
npm install -g firecrawl-cli
# 任选其一即可

# (推荐) crawl4ai — 本地开源 LLM-ready 浏览器
pip install crawl4ai
crawl4ai-setup

# (推荐) playwright — 本地 Chromium，bot-checked 页面最后兜底
pip install playwright
playwright install chromium
```

不装任何爬虫时 `radar.py crawl` 仍能跑，会回退到 urllib + search-API 代理。

### 2.4 配置 Postgres（推荐）

```bash
cp .env.example .env
# 编辑 .env，填入 PG 连接信息
pip install -r requirements.txt   # 仅 pg8000
```

PG 模式的好处：
- 历史快照 + 24h star 增长榜（连续多天 crawl 后 `/api/gain` 自动有数据）
- 服务端分页（`/api/top` 支持 `?page=&size=&sort=`）
- 冷启动后仍能回看

无 PG / pg8000 时自动回退到 `data/latest.json`，所有功能保留，只是没有历史增长数据。

### 2.5 校验安装

```bash
cd ~/.claude/skills/lodestone   # 或项目根目录
./radar.py today                # 应打印今日 Top 15 + 分类概览
```

---

## 3. 使用

### 3.1 三个 CLI 子命令

```bash
./radar.py crawl    # 拉 GitHub + 翻译 → 写 PG（或 data/latest.json）耗时 5-8 分钟
./radar.py today    # 终端打印 Top 15 + 分类概览
./radar.py serve [port]    # 起 JSON API，默认 8765，仅绑定 127.0.0.1
```

`crawl` 全程持文件锁（`data/crawl.lock`，>30 分钟视为崩溃残留可抢占），
多次触发只会成功一个，其它直接拒绝 — 保护 GitHub 二级限流（30 req/min）。

### 3.2 全栈启动（Vue 3 SPA + Python API）

```bash
cd frontend
npm install          # 首次
npm run dev          # → http://localhost:5173
```

`npm run dev` 通过 Node stdlib 编排器（`dev.cjs`）**并行**启动两个进程：

1. `python radar.py serve 8765` — JSON API（loopback only）
2. `vite` — 开发服务器（`:5173`），`/api/*` 代理到 `:8765`

`Ctrl-C` 同时关闭。SPA 每 30 秒轮询 `/api/data` 拉新数据。

### 3.3 前端 UI 功能

- **12 分类卡片** — 🤖 Agent · 🧠 RAG/Memory · 💬 LLM · ⚙️ Code Gen · 🔗 Workflow ·
  🎨 Multimodal · 🏋️ Fine-tune · · Eval · 💻 AI IDE · 🌐 Gateway · 🔍 Observability ·
  ⭐ Awesome & Plugins
- **Top 仓库页** — `/api/top`，按 ⭐ 排序，分页 12/页，可切 `recent` 排序
- **24h 增长榜** — `/api/gain`，连续多天 crawl 后自动有数据；冷启动有 UI 提示
- **本机 Skills 面板** — 扫描 `~/.claude/skills` + `~/.codex/skills` + plugins + MCP
- **替代推荐** — 已装 skill 在 PG 索引里找更强的同类，按"vertical anchor"匹配
- **一键安装** — repo 抽屉内"安装为 Skill（Claude + Codex）"，git clone 到
  `~/.cache/lodestone/skills/<owner>__<repo>`，symlink 到两个 skills 目录

### 3.4 API 端点一览

| 方法 | 路径 | 用途 |
|------|------|------|
| GET  | `/api/data` | `{hot_now, categories, fetched_at}` — SPA 主视图 |
| GET  | `/api/local` | 本机已装的 skills / commands / agents / plugins / clis / MCP / 替代推荐 |
| GET  | `/api/top` | 1k+ ⭐ AI repo 分页：`?page=&size=&sort=stars|recent|name` |
| GET  | `/api/gain` | 24h 增长：`?page=&size=&min_delta=` |
| GET  | `/api/workbuddy` | 编辑精选（`data/workbuddy_picks.json`） |
| POST | `/api/crawl` | 后台触发 crawl，文件锁忙时返 409 |
| POST | `/api/install` | 克隆并 symlink 一个 GitHub repo 为 skill |
| POST | `/api/install-cli` | 把任意 CLI 包装成 `~/.claude/commands/<name>.md` slash command |
| POST | `/api/local/origin` | 给 command/agent/plugin 补 GitHub origin URL |
| POST | `/api/local/replace` | 用更强 skill 替换已装 skill（带 rollback） |

**安全策略**：
- API server **仅绑定 127.0.0.1**（`serve()` 内硬编码）— 不可暴露到局域网
- POST 端点校验 `Origin` header，非 localhost 的跨站请求返 403（防 drive-by 安装）
- shell 包装的 CLI 走 allowlist 校验，禁止 `;|&$()<>` 等元字符（防 RCE）

### 3.5 爬虫并行编排（核心特性）

默认行为（`fetch_html(url, strategy="parallel")`，自 2026-08 重构起）：

```
                            ┌── firecrawl (REST / CLI)         ──┐
github.com/trending  ─────→ ├── crawl4ai (本地浏览器引擎)       ──┼──→ 并行调度
                            └── playwright (本地 Chromium)     ──┘
                                    │
                                    ▼  asyncio.wait(timeout=60s)
                                    │
                            ┌──────────────────────┐
                            │ 挑选"最长非空 HTML"  │  ← 引擎优先级 firecrawl > crawl4ai > playwright
                            │ tie-break by 优先级  │
                            └──────────────────────┘
                                    │
                                    ▼
                            html + engine="firecrawl+playwright"
```

**对比之前的串行降级**（`strategy="serial"`，仍可用）：

| 模式 | 行为 | 何时用 |
|------|------|--------|
| `parallel`（默认） | 三引擎同时跑，取最长 HTML 胜出，engine 字段列出所有贡献者 | 想要最完整、最鲁棒的抓取 |
| `serial` | 第一个返非空 HTML 的引擎胜出，后面的不跑 | 节省资源 / 严格回退语义 / 测试场景**

如果三个都失败，自动降级到：
1. `urllib` stdlib（无 JS 渲染，可能拿到 bot-check 页）
2. `fetch_recent_active_repos()` — 用 Search API 推 `pushed:>7 days` 的高星 AI repo 作为代理

### 3.6 12 个分类

分类在 `radar.py` 顶部的 `CATEGORIES` 列表，每类一组 GitHub Search 查询（topic + 关键词 +
⭐ 阈值），三层 AI 相关性过滤：
1. HARD topic 白名单（`AI_TOPIC_HARD` — `llm`, `claude-code`, `mcp-server`, `vector-database`…）
2. text-level hints（`AI_TEXT_HINTS` — 描述里出现 `"AI agent"`, `"RAG"` 等）
3. blocklist 黑名单（`AI_TOPIC_BLOCKLIST` — 股票 / 加密 / AI 女友类噪声）

外加 **5k+ 补捞**（90 条广域 topic query）+ **manual seed**（10 个保底 repo，escape
topic search 但人尽皆知的工具）+ **GitHub Trending daily/weekly**（新星捕捉）。

---

## 4. 定时刷新（可选）

### 4.1 macOS launchd

```bash
cat > ~/Library/LaunchAgents/com.lodestone.daily.plist <<EOF
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

### 4.2 Linux cron

```cron
0 8 * * * cd /path/to/lodestone && ./radar.py crawl >/dev/null 2>&1
```

> 定时用 `crawl` 只更新数据；SPA 每 30s 自动轮询到新数据。
> 连续多天 crawl 后，`/api/gain`（24h star 增长榜）会自动有数据。

---

## 5. 更新

由于安装方式用 **symlink**（不是 `cp -r`），更新非常轻量：

```bash
cd /path/to/lodestone    # 项目目录本身
git pull                # 或重新 clone
```

symlink 自动指向最新代码，无需重新跑 `install.sh`。

**当 `requirements.txt` 变了**（例如新增可选爬虫依赖）：

```bash
pip install -r requirements.txt
```

**当前 `requirements.txt` 仅包含**：
- `pg8000` — Postgres 驱动（可选，没装就 JSON 回退）

可选爬虫依赖 **不** 在 `requirements.txt` 里 — 按需手动装，避免拖累基础安装：

```bash
pip install crawl4ai playwright     # 可选引擎
crawl4ai-setup                      # 首次需要下载 chromium
playwright install chromium
# firecrawl 不需要 pip — 设 FIRECRAWL_API_KEY 或装 firecrawl CLI
```

更新完跑一遍测试确认没破坏：

```bash
python3 -m tests.test_scrapers
python3 -m tests.test_radar
python3 -m tests.test_db        # 无 PG 自动跳过
```

---

## 6. 卸载

```bash
cd /path/to/lodestone
./uninstall.sh
```

只移除 `~/.claude/skills/lodestone` 和 `~/.codex/skills/lodestone` 两个 symlink，**不动**
`~/.cache/lodestone/skills/` 缓存（你可能已 install 了其他 skill 复用同一份 clone）。

**完全清理**：

```bash
./uninstall.sh
rm -rf ~/.cache/lodestone         # 删除已 install 的 skill 缓存
rm -rf ~/.cache/lodestone/origins.json   # 删除 origin sidecar
```

数据库（`ai_radar` PG database）默认保留 — 它是数据资产，卸载代码不该顺手删。
如果真的想清掉：

```sql
DROP DATABASE ai_radar;
```

---

## 7. 故障排查

### 7.1 `crawl` 退出但没数据

- 看 `data/crawl.log`：是不是 GitHub 二级限流？`queries_failed` 数字 > 0 表示部分 query 失败
- 自适应退避：rate-limit 命中一次后，间隔从 2s 升到 6s（`radar._SEARCH_PACE`）

### 7.2 `/api/gain` 一直空

需要 **连续多天** crawl 积累 stars 快照（`repo_stars_history` 表）。
冷启动首日预期空，UI 有提示："暂无 24h 增长数据：需连续多天定时 crawl 积累"。

### 7.3 三个爬虫都没装

`./radar.py crawl` 会自动回退到 urllib + search-API 代理，**功能不中断**。
只是 github.com/trending 的 JS 渲染拿不到。

### 7.4 想看哪些爬虫已装

```bash
python3 -c "from scrapers import status; import json; print(json.dumps(status(), indent=2))"
```

输出示例：
```json
{
  "firecrawl": true,
  "crawl4ai": true,
  "playwright": true
}
```

### 7.5 firecrawl 报 "empty html"

CLI 模式下 firecrawl 可能输出 "Scrape ID: ..." 前缀行；orchestrator 会自动剥离
`<!DOCTYPE`/`<!doctype`/`<html`/`<HTML` 之前的所有字符。如果仍然空，去 firecrawl 控制台
确认 quota 与权限。

### 7.6 端口 8765 被占用

```bash
./radar.py serve 8888   # 任意端口
# 同时改 frontend/vite.config.js 的 proxy target
```

### 7.7 PG 连接失败

`db/__init__.py` 捕获 ImportError 自动 JSON 回退；但 PG **已装**但**连不上**会打印
`PG read failed`，然后同样回退到 `data/latest.json`。检查 `PGHOST` / `PGPORT` /
`PGUSER` / `PGPASSWORD` 是否正确。

### 7.8 测试报错

```
python3 -m tests.test_db
[test_db] pg8000 unavailable — skipping (JSON-only mode)
```

这是预期的 — `test_db` 需要 PG，无 PG 时干净跳过，不报错。**有 PG 时**会自动创建临时
DB（`ai_radar_test_<uuid>`），测完清理。

---

## 8. 架构与代码地图

```
lodestone/
├── SKILL.md                  # Skill 入口（Claude/Codex 双端通用 frontmatter）
├── radar.py                  # Python 单文件 — 爬取 / 翻译 / 安装 / API server (~2136 行)
├── requirements.txt          # 仅 pg8000（可选）
├── .env.example              # PG 连接模板
├── install.sh / uninstall.sh # symlink 安装/卸载
├── db/
│   ├── connection.py         # pg8000 连接 + .env 加载 + 建库
│   ├── repos.py              # upsert / query / gain 计算
│   └── schema.sql            # 幂等建表（含 ALTER 增量迁移）
├── scrapers/                 # 可选真实浏览器引擎，并行编排
│   ├── __init__.py           # orchestrator: fetch_html(strategy="serial"|"parallel")
│   ├── firecrawl_scraper.py  # 远程 API + CLI
│   ├── crawl4ai_scraper.py   # 本地浏览器引擎
│   └── playwright_scraper.py # 本地 Chromium
├── data/                     # 运行时生成（gitignored）
│   ├── latest.json           # JSON 回退快照
│   ├── zh_cache.json         # 翻译缓存
│   ├── crawl.lock            # crawl 文件锁（30 分钟陈旧可抢占）
│   └── crawl.log             # 后台 crawl 输出
├── tests/
│   ├── test_scrapers.py      # 串行 + 并行编排 + 解析器（11 测试）
│   ├── test_radar.py         # 过滤 / 安装 / 锁（13 测试）
│   └── test_db.py            # PG CRUD（需 PG，无则跳过，7 测试）
├── frontend/                 # Vue 3 SPA
│   ├── dev.cjs               # Node stdlib 编排器：并行起 API + Vite
│   ├── vite.config.js        # /api/* 代理到 :8765
│   └── src/App.vue           # 主组件
└── MANUAL.md                 # 本文件
```

### 关键设计原则

| 原则 | 体现 |
|------|------|
| **零强制依赖** | 仅有 `gh` CLI + stdlib；pg8000、crawl4ai、playwright、firecrawl 全部可选 |
| **安全第一** | API 仅 loopback、POST 校验 Origin、CLI 安装走 allowlist 校验 |
| **优雅降级** | PG 不在 → JSON；爬虫不在 → urllib；JS 拿不到 → search-API 代理 |
| **并行编排** | 三个引擎同时跑，最长 HTML 胜出；engine 字段列出贡献者 |
| **可观测** | 翻译缓存、crawl log、爬虫 status、`queries_failed` 数据质量字段 |
| **文件锁** | crawl 全程持锁防并发触发 GitHub 限流 |
| **不当过度设计** | 没引入 ORM / Web framework / 异步爬虫框架；一个 stdlib `http.server` 就够了 |

---

## 9. 与 youzi skill 的关系

`ailibrary/youzi` 是一个竞品 / 项目深度分析 skill，lodestone 直接复用并裁剪了它的爬虫
适配器代码：

| 维度 | youzi | lodestone |
|------|-------|----------|
| 目标场景 | 抓任意网页做 AI 分析 | 抓 GitHub trending 做 AI 项目发现 |
| 适配器功能 | markdown + html + screenshot + LLM 抽取 | 仅 raw html（够用） |
| 编排方式 | `scrape_smart(strategy="parallel")` 三路并行 + markdown 去重合并 | `fetch_html(strategy="parallel")` 三路并行 + 最长 HTML 胜出 |
| 输出 | markdown（可喂 LLM） | HTML（喂 regex 解析器） |
| 失败回退 | `scrape_with_fallback` 串行版保留 | `strategy="serial"` 串行版保留 |

裁剪理由：lodestone 不需要 markdown（直接 regex 解析 `github.com/trending` 的 HTML），
也不需要 screenshot / LLM 抽取（DB 里存的是 stars + topics + desc，不需要 LLM 介入）。
代码量从 youzi adapter 的 ~600 行降到 lodestone 的 ~175 行（三个适配器 + orchestrator），
但保留了相同的 "并行 + 互补" 设计思路。

---

## 10. 已知限制 & 升级路径

| 限制 | 当前缓解 | 升级路径 |
|------|----------|----------|
| GitHub Search 二级限流 30 req/min | 自适应 sleep 2s→6s，失败数记 `crawl_log.queries_failed` | 多个 `gh` token 轮询 / 申请 GitHub App |
| 翻译质量偶有不顺 | 原始英文描述可查；缓存到 `data/zh_cache.json` 永久复用 | 接入 Claude / GPT 做语义润色 |
| 分类靠 topic 关键词 | 误分类改 `radar.CATEGORIES` 即可 | 接 LLM 读 README 摘要后分类 |
| 24h 增长冷启动 | UI 有提示 | 预填种子数据 / 用 GitHub API 拉历史 |
| 三爬虫结果不 merge markdown | lodestone 不需要 | — |

---

## 11. 快速命令卡片

```bash
# 首次
./install.sh                                                # 安装为 skill
cp .env.example .env && $EDITOR .env                        # 配置 PG（可选）
pip install -r requirements.txt                             # pg8000（可选）
pip install crawl4ai && crawl4ai-setup                      # 推荐爬虫
pip install playwright && playwright install chromium       # 推荐爬虫
echo 'FIRECRAWL_API_KEY=fc-xxx' >> .env                     # 或 firecrawl

# 跑
./radar.py crawl                                            # 5-8 分钟拉数据
./radar.py today                                            # 终端看结果
cd frontend && npm install && npm run dev                   # 全栈启动（API + SPA）

# 维护
python3 -m tests.test_scrapers                              # scraper 测试
python3 -m tests.test_radar                                 # radar 测试
python3 -m tests.test_db                                    # PG 测试（无 PG 跳过）
git pull                                                    # 更新（symlink 自动生效）

# 卸
./uninstall.sh                                              # 移除 skill symlink
rm -rf ~/.cache/lodestone                                    # 清缓存（可选）
```

---

> 任何问题先看 `data/crawl.log` 和 stderr 输出；engine 字段里 `firecrawl+playwright`
> 之类带 `+` 的串行表示两个引擎同时贡献了结果，这是 lodestone 区别于普通爬虫脚本的
> 核心信号。
