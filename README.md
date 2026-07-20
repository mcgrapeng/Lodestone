# ⚡ Lodestone

每日 GitHub AI 热门仓库自动雷达 · 已为 AI 应用工程师分类整理 · 中文友好

> **跨平台 Skill + 双 UI 模式**：一份 Python 数据 → 静态 HTML 或 Vue 3 SPA；同时集成 **Claude Code** 和 **Codex CLI**。

---

## 🎯 一键安装为 Skill（同时支持 Claude Code 和 Codex CLI）

```bash
cd /Users/zhangpeng/workspace/liaohe/lodestone
./install.sh
```

→ 自动在 `~/.claude/skills/lodestone` 和 `~/.codex/skills/lodestone` 各创建一个 **symlink**（不是复制，单一真实源）。

之后：

- **Claude Code**：说"刷一下 AI 雷达" → 自动触发
- **Codex CLI**：说"刷一下 AI 雷达" → 自动触发
- 两个 CLI 都直接读同一个 `radar.py` / `data/`，0 维护成本

卸载：`./uninstall.sh`

> **为什么 symlink 而不是复制**：项目含 `node_modules/` 175MB，复制两遍浪费 350MB 且改一处忘了同步。symlink 单一真实源，编辑一处两边即时生效。

---

## 🏃 直接启动（不用 Skill）

### 一条命令全栈启动（Vue 3 + Python API）

```bash
cd /Users/zhangpeng/workspace/liaohe/lodestone/frontend
npm install       # 首次需安装 (~80MB)
npm run dev       # → http://localhost:5173
```

`npm run dev` 自动：
1. 启动 Python API 服务器（`:8765`）— `/api/data` `/api/local` `/api/install` `/api/crawl`
2. 启动 Vite 开发服务器（`:5173`）— 代理 `/api/*` 到 Python
3. UI 自动每 30s 轮询新数据；点 "🔄 刷新" 立即拉；点 "⬇ 重新爬取 GitHub" 触发后台 crawl

UI 内嵌三个新能力：
- **本机 Skills 面板** — 实时扫描 `~/.claude/skills` + `~/.codex/skills`
- **未安装推荐** — 智能筛选未装但值得装的 skills，一键安装
- **抽屉里的一键安装** — 任何 repo 详情页 → "一键安装为 Skill（Claude + Codex）"

### 只跑数据层（不需要 UI）

```bash
cd /Users/zhangpeng/workspace/liaohe/lodestone
./radar.py crawl      # 拉 GitHub + 翻译 + 写 data/latest.json
./radar.py today      # 终端打印 Top 15 + 分类
./radar.py serve 8765 # 单跑 API（前端用 vite preview / 别的工具连）
```

---

## 🤔 这是 Skills 还是项目？

**两者都是，且跨两个 CLI 平台。**

| 平台 | Skill 路径 | 安装方式 |
|------|----------|---------|
| Claude Code | `~/.claude/skills/lodestone/` | `./install.sh`（symlink） |
| Codex CLI | `~/.codex/skills/lodestone/` | `./install.sh`（symlink） |
| 独立项目 | `npm run dev` | 不需要安装 |
| Cron/launchd | `radar.py crawl` + UI 自动轮询 | 不需要安装 |

`SKILL.md` frontmatter 格式两边相同（`name` + `description`），`./install.sh` 一行命令双端可用。

---

## 🛠️ 技术栈

### 后端（数据 + API）
- **Python 3.10+ stdlib** — 零依赖（仅 urllib 调 Google Translate）
- **`gh` CLI** — GitHub API 走认证通道（5000 req/hr）
- **Google Translate 免费端点** — 描述中文翻译，结果缓存到 `data/zh_cache.json`
- **`http.server.ThreadingTCPServer`** — 零依赖 API server，端点：`/api/{data,local,install,crawl}`

### 前端（Vue 3 SPA）
- **Vue 3** + **Vite** — 最主流前端栈
- **Element Plus** — 最主流 Vue 3 组件库（el-tag / el-drawer / el-button / el-message）
- **lucide-vue-next** — Vue 3 图标组件
- **Tailwind CSS** + PostCSS — 原子化样式
- **Aurora 动画背景** — CSS-only 三层径向渐变 + 56px 网格 overlay

### 启动编排
- **`frontend/dev.cjs`** — Node stdlib 写的小编排器（30 行），并行启动 Python + Vite，Ctrl-C 优雅关闭

---

## 📋 命令一览

| 命令 | 作用 |
|------|------|
| `cd frontend && npm run dev` | 一条命令全栈启动（Vue 3 + Python API） |
| `cd frontend && npm run vite-only` | 只启动 Vite（API 单独跑） |
| `cd frontend && npm run build` | 打包到 `frontend/dist/` |
| `./radar.py crawl` | 拉取 GitHub Search API → 翻译 → 写 `data/latest.json` |
| `./radar.py today` | 终端打印今日 Top 15 + 分类概览 |
| `./radar.py serve [port]` | 单跑 API server（默认 8765） |

> 历史命令 `./radar.py all` / `./radar.py render` 已移除 — Vue 3 模式下数据由 Python crawl 写 `latest.json`，UI 自动 30s 轮询拉取。

---

## 🗂 9 个自动分类

1. 🤖 **AI Agent & Skills** — agent / claude-code / MCP / autonomous / multi-agent
2. 🧠 **RAG / Memory / Vector** — vector-db / agent-memory / embedding
3. 💬 **LLM Interface & Chat** — LLM SDK / chatbot / prompt-engineering / claude-api
4. ⚙️ **Code Generation & Dev Tools** — copilot / ai-coding / code-agent
5. 🔗 **Workflow & Orchestration** — langgraph / langchain / pipeline
6. 🎨 **Multimodal** — vision / text-to-video / multimodal
7. 🏋️ **Fine-tuning & Training** — LoRA / PEFT / llama-factory
8. 📊 **Eval & Benchmark** — llm-evaluation / benchmark
9. ⭐ **Awesome Lists** — awesome-ai / awesome-llm / awesome-claude

---

## 🕐 定时刷新

### macOS launchd

```bash
cat > ~/Library/LaunchAgents/com.lodestone.daily.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.lodestone.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/zhangpeng/workspace/liaohe/lodestone/radar.py</string>
    <string>all</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>WorkingDirectory</key><string>/Users/zhangpeng/workspace/liaohe/lodestone</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.lodestone.daily.plist
```

### Linux cron

```cron
0 8 * * * cd /path/to/lodestone && ./radar.py all >/dev/null 2>&1
```

---

## 📁 目录结构

```
lodestone/
├── SKILL.md              # Claude Skill 入口（放进 ~/.claude/skills/ 让 Claude 自动触发）
├── radar.py              # 全部 Python 逻辑（单文件 ~1100 行，stdlib only）— crawl + API + install
├── install.sh            # 创建 ~/.claude/skills/ + ~/.codex/skills/ symlink
├── uninstall.sh          # 移除 symlink
├── README.md             # 本文件
├── data/
│   ├── latest.json       # 最新一次快照（前端通过 /api/data 读这个）
│   ├── YYYY-MM-DD.json   # 历史归档
│   ├── zh_cache.json     # 翻译缓存（持久化，再跑 0 翻译开销）
│   └── crawl.log         # 后台 crawl 输出
└── frontend/             # Vue 3 SPA（npm run dev 启动）
    ├── package.json
    ├── dev.cjs           # Node stdlib 启动编排器（25 行）— 并行拉 Python + Vite
    ├── vite.config.js    # 含 /api/* → :8765 代理
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue       # 单文件组件（fetch API + auto-poll + 本机 Skills + 一键安装）
        └── style.css
```

---

## ⚠️ 已知限制

- **GitHub Search secondary rate limit**：30 req/min。`crawl` 一次约 30 个查询，踩线。冷却几分钟重试。
- **翻译质量**：Google Translate 长 description 偶尔不通顺；原始英文在 modal 里可折叠查看。
- **分类粒度**：基于 topic/name 关键词，不读 README 语义判断；误分类时改 `radar.py` 顶部 `CATEGORIES` 字典即可。

---

## 🚀 升级路径

- 接 LLM 做语义解读（每个 repo 一句话，cache 到 JSON）
- 接入 GitHub Trending HTML 抓取作补充数据源
- 多日数据对比，识别"昨天新冒出的项目"
- 自动 PR / 周报推送（基于 hot_now 增量）
- WebSocket 推送替换 30s 轮询（数据变更即时反映）
- install 加进度条（前端订阅 /api/install/<job_id> SSE）