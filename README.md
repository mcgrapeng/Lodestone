# ⚡ Lodestone

爬取 GitHub AI 热门仓库，按用途分成 9 类。

一份 Python 数据层（`radar.py`），两种前端：`render` 生成的静态 HTML（`out/index.html`）或 Vite 起的 Vue 3 SPA。可作为 **Claude Code** 与 **Codex CLI** 的 skill 安装。

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

## 直接启动（不装 skill）

### 全栈：Vue 3 SPA + Python API

```bash
cd frontend
npm install        # 首次
npm run dev        # → http://localhost:5173
```

`npm run dev` 运行 `dev.cjs`（Node stdlib，48 行），并行做两件事：

1. `python radar.py serve 8765` —— API 服务器
2. 本地 `vite` —— 开发服务器（`:5173`），`/api/*` 代理到 `:8765`（见 `vite.config.js`）

`Ctrl-C` 同时关闭两个进程。

前端（`src/App.vue`）行为：

- 每 30s 轮询 `/api/data`
- 「刷新」按钮 —— 立即重新拉取
- 「重新爬取」按钮 —— 触发后台 `crawl`
- 本机 Skills 面板 —— 扫描 `~/.claude/skills` + `~/.codex/skills`（`/api/local`）
- repo 抽屉内「一键安装为 Skill（Claude + Codex）」

### 静态 HTML（无需 Node）

```bash
./radar.py all     # crawl → 生成 out/index.html → 打开浏览器
```

### 只跑数据层

```bash
./radar.py crawl        # 拉 GitHub + 翻译 → 写 data/latest.json
./radar.py today        # 终端打印 Top 15 + 分类
./radar.py serve 8765   # 单跑 API
```

---

## 命令一览

| 命令 | 作用 |
|------|------|
| `cd frontend && npm run dev` | 全栈启动（Python API + Vite）|
| `cd frontend && npm run vite-only` | 只启动 Vite |
| `cd frontend && npm run build` | 打包到 `frontend/dist/` |
| `./radar.py crawl` | 拉 GitHub Search API → 翻译 → 写 `data/latest.json` |
| `./radar.py render` | 从 `latest.json` 生成 `out/index.html` |
| `./radar.py all` | `crawl` → `render` → 打开浏览器 → 继续 serve |
| `./radar.py today` | 终端打印今日 Top 15 + 分类概览 |
| `./radar.py serve [port]` | 单跑 API server（默认 8765）|

---

## 技术栈

**后端（`radar.py`，单文件 ~1470 行，Python 3.10+ stdlib）**

- 依赖 `gh` CLI 调 GitHub Search API（走认证通道）
- 描述经 Google Translate 免费端点翻译，缓存到 `data/zh_cache.json`
- API server 基于 `http.server.ThreadingHTTPServer`，端点：
  `/api/data`、`/api/local`、`/api/top`、`/api/install`、`/api/install-cli`、`/api/crawl`

**前端（`frontend/`）**

- Vue 3 + Vite
- Element Plus（`el-tag` / `el-drawer` / `el-button` / `el-message`）
- `lucide-vue-next` 图标
- Tailwind CSS + PostCSS
- CSS-only aurora 背景（径向渐变 blob + 网格 overlay）

---

## 9 个分类

分类在 `radar.py` 顶部的 `CATEGORIES` 列表中定义，每类对应一组 GitHub 查询：

1. 🤖 AI Agent & Skills
2. 🧠 RAG / Memory / Vector
3. 💬 LLM Interface & Chat
4. ⚙️ Code Generation & Dev Tools
5. 🔗 Workflow & Orchestration
6. 🎨 Multimodal (Vision / Audio / Video)
7. 🏋️ Fine-tuning & Training
8. 📊 Eval & Benchmark
9. ⭐ Awesome Lists & 资源合集

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

> 定时用 `crawl` 只更新数据；SPA 每 30s 自动轮询到新数据。若要同时刷新静态 HTML，用 `all`（会打开浏览器，不适合无头 cron）。

---

## 目录结构

```
lodestone/
├── SKILL.md              # skill 入口（frontmatter: name + description）
├── radar.py              # Python 全部逻辑（~1470 行，stdlib）— crawl + render + API + install
├── install.sh            # 创建 ~/.claude/skills + ~/.codex/skills symlink
├── uninstall.sh          # 移除 symlink
├── data/
│   ├── latest.json       # 最新快照（/api/data 读这个）
│   ├── YYYY-MM-DD.json   # 历史归档
│   ├── zh_cache.json     # 翻译缓存
│   └── crawl.log         # 后台 crawl 输出
├── out/index.html        # render 生成的静态页
└── frontend/             # Vue 3 SPA
    ├── package.json
    ├── dev.cjs           # Node stdlib 编排器（48 行）— 并行起 Python + Vite
    ├── vite.config.js    # /api/* → :8765 代理
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue       # 主组件（971 行）— fetch + 30s 轮询 + 本机 Skills + 一键安装
        └── style.css
```

---

## 已知限制

- **GitHub Search 二级限流**：约 30 req/min，`crawl` 一次约 30 个查询会踩线，冷却几分钟重试。
- **翻译质量**：长 description 偶尔不通顺；原始英文可在详情里查看。
- **分类粒度**：基于 topic / name 关键词匹配，不读 README 语义。误分类时改 `radar.py` 的 `CATEGORIES`。
