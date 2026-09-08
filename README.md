# ⚡ Lodestone

每日 AI 工具发现仪表盘 —— GitHub + HuggingFace + MCP Registry + arXiv，按 20 个用途分类，中文友好。

给 AI 应用工程师找「本周值得关注的新工具 / 新模型 / 新协议」，不用刷十几个 RSS。

## 一图流

```
              5 个数据源                    4 级爬虫兜底
GitHub ──┐                              ┌─ httpx（默认）── 大多数直接命中
HF Spaces┤                              ├─ cloudscraper ── 破 Cloudflare
HF Models┼─→ 抓 + 去重 + 过滤 ──→ AI 仪表盘  ├─ playwright_stealth ── 真浏览器
MCP Reg  ┤     ↓                        └─ jina（云）── 本地 IP 被封时换出口
arXiv   ─┘   中文翻译 + 摘要
            ↓
       Postgres（推荐） / JSON 回退
            ↓
       ┌─ 卡片墙（hot_now / 分类 / trending / 24h 星增）
       ├─ 详细介绍（README 拆分 + LLM 5 维度决策）
       └─ 一键安装为 skill（仅当仓库有 SKILL.md）
```

## 30 秒上手

```bash
# 1. 装好 Python 3.10+ + Node 18+ + gh CLI（已登录）— 见 安装说明.md
git clone <仓库> ~/lodestone && cd ~/lodestone

# 2. 抓数据 + 起服务
./radar.py crawl            # ~3-5 分钟（首次拉 + 翻译 1k+ repo）
./radar.py web              # 后台起 serve + 自动开浏览器

# 3. 装成 Claude Code skill（可选）
./install.sh install
# 完全退出 Claude Code 再重开
# 然后说 "刷一下 AI 雷达" 就能用
```

## 这是给谁用的

**主要用户**：AI 应用工程师，每天想花 5 分钟扫一眼「最近出了什么值得关注的新东西」。

**解决的问题**：

- GitHub Trending 噪音大 —— 每天 25 条只有 ~5 个跟 AI 有关
- HuggingFace 主页不会主动推新模型
- MCP 协议刚起步，没有「热门 MCP server」榜
- arXiv 每天 100+ AI 论文，谁有空挨个翻

## 5 个数据源覆盖什么

| 源 | 抓什么 | 为什么不能少 |
|---|---|---|
| **GitHub** | 主流开源 AI 项目 | 90% 的 AI 工具在这里 |
| **HuggingFace Spaces** | 社区精选 AI demo | 跑得起来的东西比 README 有用 |
| **HuggingFace Models** | 模型权重排行 | 知道现在流行什么模型（Qwen / Llama / DeepSeek） |
| **MCP Registry** | 官方 MCP server | MCP 协议生态入门 |
| **arXiv** | 最新 AI 论文 | 模型权重还没出，论文先发 |

GitHub 抗爬时其他 4 个源仍然工作 —— 你不会「今天啥都看不到」。

## 关键能力

| 能力 | 怎么实现的 |
|---|---|
| **4 级爬虫 fallback** | httpx → cloudscraper → playwright_stealth → jina，每天只有 httpx 在跑 |
| **中文友好** | desc / README 自动翻译 + 结构化摘要（介绍 / 能干什么 / 优势） |
| **Postgres + JSON 双模** | PG 优先（24h 星增、历史快照），PG 不可达回退 JSON |
| **决策支持** | LLM 5 维度分析（是什么 / 痛点 / 同类 / 优缺 / 何时选），可选用 Claude / GPT / Ollama |
| **Skill 一键安装** | 探测 `SKILL.md` → 标记 is_skill → 卡片显示装按钮（仅当仓库真的是 skill 格式） |
| **20 个分类** | Agent / RAG / LLM / IDE / MCP / Voice / 安全 / 机器人 / arXiv 论文 … |

## 文档导航

| 你想看什么 | 跳到 |
|---|---|
| 🚀 装好跑起来 | [安装说明](安装说明.md) |
| 📖 命令清单 / 故障排查 / 加新数据源 | [使用手册](使用手册.md) |
| 🤖 Claude Code 触发入口 | [SKILL.md](SKILL.md) |

## 技术栈

- **后端**：Python 3.10+（stdlib + 可选 `pg8000`）
- **数据库**：PostgreSQL（JSON 回退）
- **爬虫**：4 引擎分级 fallback，stdlib + 可选依赖
- **数据源**：5 个互补源（GitHub + HF × 2 + MCP + arXiv）
- **前端**：React 19 + Vite 6 + Appica UI + Tailwind v4
- **依赖**：`gh` CLI 已认证；翻译走 Google Translate；可选 LLM 走 Claude / OpenAI / Ollama

## 部署

本地默认 `127.0.0.1:8765`（安全：API 能 `git clone` 你的 skill 目录）。

服务器部署需要 3 个改动（详见 [安装说明 § 部署到服务器](安装说明.md#部署到服务器)）：

```bash
# .env
RADAR_HOST=0.0.0.0          # 让 serve 监听外部接口（前面挂 nginx 做 TLS）
AI_RADAR_HOME=/var/lib/lodestone   # skill 缓存重定向到项目目录（多用户）
PGHOST=10.0.0.5            # PG 不在 localhost 时
```

## License

MIT
