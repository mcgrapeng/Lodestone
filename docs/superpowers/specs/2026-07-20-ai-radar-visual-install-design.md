# Lodestone — 视觉 / 本机能力 / 安装 Bug 修复设计

**日期**：2026-07-20
**项目**：lodestone
**范围**：Vue 3 SPA 前端 + Python radar.py 后端（API 层）
**不涉及**：radar.py 的 crawl/today 逻辑、`data/latest.json` 生产逻辑、README/SKILL.md

---

## 背景 / 痛点

用户反馈三件事：

1. **页面背景是炫酷的黑色，但视觉优化空间有限** — 当前 Aurora 背景（紫/青/粉 blob + grid + vignette）已存在，但 Hero 信息密度低，本机能力区像 debug 输出而非产品 UI
2. **本机能力模块视觉效果差，每个 skill / plugin 等没有来源（GitHub 仓库等）也没有介绍** — 现有卡片只显示 name + 2px 平台标签，desc / url / topics 全部缺失
3. **一键安装按钮点击报错** — `install_skill_from_github` 校验把 `name="obra/superpowers"` 当成单段目录名（只允许 `isalnum + "-_."`），`/` 字符直接 ValueError

## 设计决策（已与用户确认）

| 决策 | 选 | 备选 |
|------|----|----|
| 整体视觉方向 | A. Aurora Glass 增强 | B. Terminal / Cyberpunk · C. Linear / Minimal |
| 本机能力卡布局 | B. 富信息卡（150-180px，desc+topics+GitHub 按钮） | A. 紧凑横排 · A+. 紧凑+展开 · C. 列表+抽屉 |
| 已装 skill 的来源/介绍数据源 | A. latest.json 匹配 + sidecar origin 兜底 | B. SKILL.md frontmatter · C. 实时 GitHub API · D. 仅推荐区显示 |

---

## 1. 视觉增强（Aurora Glass 强化）

**文件**：`frontend/src/App.vue`（Hero/本机能力区结构），`frontend/src/style.css`（卡片玻璃/hover 样式）

### 1.1 Hero 区
现状：标题 + 5 个小 chip + 搜索框
**改为**：
- 标题区增加渐变光晕（CSS：`text-shadow: 0 0 40px rgba(167,139,250,0.4)`）保持现有 `gradient-text` 类
- 标题下方加 **4 格统计面板**（`grid-cols-2 md:grid-cols-4`），替换 5 个小 chip：
  - 本机 Skills 数（带 Folder 图标 + 绿色）
  - 今日 Repos 数（Flame 图标 + 紫色）
  - 分类数（Bookmark 图标 + 青色）
  - CLI 工具数（Terminal 图标 + 灰色）
- 每格样式：圆角 `1rem`，`bg-white/[0.04]`，`border border-white/10`，内嵌 icon + 大数字 + 小标签
- 搜索框宽度从 `max-w-xl` 改为 `max-w-2xl`，保持不变

### 1.2 本机能力区开篇
现状：5 个小 chip + 一行说明文字
**改为**：
- 保留 section title + 一行说明
- 删除原 5 个 chip 行
- 增加 **4 张「系统能力卡」入口**（仅 Skills / Commands / Agents / Plugins，CLI 数量通常较小合并到 Skills 卡的角标）：
  - 每张：圆角 `1.25rem`，`bg-white/[0.03]`，`backdrop-blur-2xl`
  - 顶部：大图标（`Folder` / `Hash` / `Users` / `Plug`）+ 名称
  - 中部：数字（48px 粗体） + 副标签（如 "任务型能力"）
  - 底部：跳到对应小节锚点的 `↓ 查看` 文字按钮
  - hover：`translateY(-3px)` + 渐变光边框

### 1.3 全局卡片玻璃/hover
- 所有 `.repo-card`、`.hot-card`、本机能力卡：
  - `backdrop-filter: blur(24px)`（从 12px 提升）
  - `background: rgba(15, 12, 24, 0.78)`（已存在）
  - hover：边框从 1px `rgba(255,255,255,0.08)` → `1.5px` 渐变（`linear-gradient(135deg, #7c3aed, #06b6d4)` 用 mask 实现），`translateY(-2px)`

---

## 2. 本机能力卡：B 富信息卡

**文件**：`frontend/src/App.vue`（template 部分），`frontend/src/style.css`（新加 `.capability-card` 类）

### 2.1 Skills 卡（B 富信息卡）
**结构**（每张 ~150-180px 高）：
```
┌──────────────────────────────────────────────────┐
│ obra/superpowers              ⭐ 257k  [↗ GitHub] │  ← 头部：name + stars + github
│ [Claude] [Codex]                                   │  ← 平台标签
│ 代理技能框架和软件开发方法。提供 brainstorming、   │  ← desc_zh（2-3 行 line-clamp-3）
│ subagent-driven-development 等模式化流程。         │
│ #ai #brainstorming #sdlc #skills                  │  ← topics chip
└──────────────────────────────────────────────────┘
```
- 容器：`rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-2xl p-4`
- name：`text-lg font-bold text-purple-200 break-all`（保留 `break-all` 防止 owner/repo 换行难看）
- 平台标签：现有 chip 样式（橙 = Claude，蓝 = Codex）
- desc：`text-sm text-white/75 line-clamp-3 leading-relaxed`
- topics chip：`<el-tag size="small" effect="plain" v-for="t in topics.slice(0,4)">#{{t}}</el-tag>`
- GitHub 按钮：`<el-button size="small" :icon="ExternalLink" @click.stop="openUrl(meta.url)">↗ GitHub</el-button>`，需要 `.stop` 防止冒泡触发外层点击

**响应式**：
- `lg`：3 列（`lg:grid-cols-3`）
- `md`：2 列（`md:grid-cols-2`）
- `sm`：1 列

### 2.2 Plugins 卡
同 Skills 布局，多一行：
- 平台标签下方：`marketplace@version`，`text-xs text-amber-300/80 font-mono`

### 2.3 Commands / Agents 卡（保持紧凑）
**不升级到 B 卡**（无外部 URL），改为：
- 单行：name（粗体等宽） + `· 路径提示`（`~/.claude/commands/foo.md`） + `本地创建` 灰 chip
- Agents 保持现有的「前 30 个 + 展开全部」折叠逻辑

### 2.4 CLI 卡（保持紧凑）
现状已经够用：name + path + version + `包成 /xxx` 按钮，不动

---

## 3. 数据层：双源 desc/url

**文件**：`radar.py`（`detect_local_skills` + `install_skill_from_github`），`frontend/src/App.vue`（读取新字段）

### 3.1 后端改动

#### 3.1.1 `install_skill_from_github`（修复安装 bug + 写 sidecar）
**位置**：`radar.py:313-339`

**改动**：
- `name` 校验从「单段目录名」改为「完整 owner/repo」：`^[\w.-]+/[\w.-]+$`（word chars + `-_.` + 一个 `/`）
- 拆分：`owner, repo = name.split('/', 1)`
- cache 目录名 = `repo`（即 `name.split('/')[-1]`），cache 名再做一次 `^[A-Za-z0-9_.-]+$` 校验
- url 兜底：如果前端没传 url，用 `f"https://github.com/{name}"` 构造
- **写 sidecar**：`~/.cache/lodestone/origins.json`，结构：
  ```json
  {
    "skills": {
      "superpowers": {
        "owner": "obra",
        "repo": "superpowers",
        "url": "https://github.com/obra/superpowers",
        "installed_at": "2026-07-20T11:35:00"
      }
    }
  }
  ```
- sidecar 路径常量：`SKILL_ORIGINS = Path.home() / ".cache" / "lodestone" / "origins.json"`，在文件顶部 `Path` import 附近定义

**向后兼容**：
- 如果 `~/.cache/lodestone/skills/<repo>` 已存在（被 `target.exists()` 短路），**也写 sidecar**（幂等更新 metadata）
- 已安装的 skill 第一次访问新代码时 sidecar 是空的，下次 radar crawl 触发 install 才会写入

#### 3.1.2 `detect_local_skills`（加 desc / url）
**位置**：`radar.py:245-310`

**改动**：
- 加载 `latest.json`（如果存在），构建 `by_repo_name: Dict[str, repo_data]`，key 是 `name.split('/')[-1]`（即 repo 段，用于匹配 `~/.claude/skills/<repo>` 这种 symlink 目录名）
- 加载 sidecar `origins.json`（如果存在），构建 `by_origin_name: Dict[str, origin_data]`
- 对每个本机 skill（key 是目录名）按优先级填 `meta`：
  1. **匹配 latest.json**：用 `meta.desc_zh = repo.desc_zh, meta.url = repo.url, meta.topics = repo.topics, meta.stars = repo.stars, meta.source = "cache"`
  2. **匹配 origins.json sidecar**：`meta.desc_zh = None, meta.url = origin.url, meta.topics = [], meta.stars = 0, meta.source = "origin"`（只有 URL，desc 没有）
  3. **读 SKILL.md frontmatter**：读 `<skill_dir>/SKILL.md`，用正则解析 `^description:\s*(.+)$` → `meta.desc_zh = None, meta.desc_en = desc, meta.url = None, meta.source = "skillmd"`
  4. **都没有**：`meta.source = "none"`
- 输出结构（替换现在的 `{claude, codex}`）：
  ```python
  out["skills"][entry.name] = {
      "claude": bool,
      "codex": bool,
      "url": str | None,
      "desc_zh": str | None,
      "desc_en": str | None,
      "topics": list[str],
      "stars": int,
      "source": "cache" | "origin" | "skillmd" | "none",
  }
  ```

**性能**：
- latest.json 已经在磁盘上，load 一次 ≈ 10ms
- origins.json 一次
- SKILL.md 只在 fallback 时读，30 个 skill 最坏 30 次小文件读 ≈ 50ms
- 整体 < 200ms，不影响 30s 轮询

### 3.2 `/api/local` 响应
- 已经在 `do_GET` 里 return `{"skills": local["skills"], ...}` — skills 已经是新结构，**前端不用改 API 调用**
- counts 仍然按 `len(local["skills"])` 算，不变

### 3.3 前端改动
**位置**：`frontend/src/App.vue:332-350`（Skills 卡模板）

- 模板里读 `localSkills[name].url`、`localSkills[name].desc_zh`、`localSkills[name].topics`、`localSkills[name].stars`、`localSkills[name].source`
- 条件渲染：
  - `desc_zh` 存在 → 显示 desc
  - 否则 `desc_en` 存在 → 显示英文 desc + 「(en)」小角标
  - 都没有 → 显示「本地安装 · 无介绍」灰字
  - `url` 存在 → 显示 ↗ GitHub 按钮
  - `url` 不存在 + source === "skillmd" → 不显示按钮（只显示「本地安装」灰 chip）
  - `url` 不存在 + source === "none" → 同上
- `topics` 数组存在 → 渲染 chip
- `stars > 0` → 渲染 ⭐

### 3.4 安装后刷新
- `installSkill()` 成功后调用 `await fetchAll()`，触发 `/api/local` 重新拉，新 skill 立即出现在本机能力区
- 已存在行为，不改

---

## 4. 错误兜底

**文件**：`frontend/src/App.vue:87-107`

- `installSkill()` 失败时：`ElMessage.error(d.error, { duration: 5000, showClose: true })`（从默认 3s 延长到 5s，加关闭按钮，用户能看清错误）
- 真实错误场景（不是当前 `name` 校验挂掉，而是其他）：
  - git clone 失败（网络 / 仓库不存在）：`{ok: false, error: "git clone failed: <stderr前200字>"}`
  - URL 不是 github.com：`{ok: false, error: "only github.com urls allowed"}`
  - 这些错误对用户可读，5s 足够看清

---

## 5. 范围外（明确不做）

- Commands / Agents / CLI 的 source 链接（这些是本地创建/系统工具，无外部 URL）
- 推荐区（未安装 skills）— 已经展示 desc + URL，不动
- radar.py 的 crawl / today 逻辑
- README / SKILL.md 文档（功能没变，只是前端呈现升级 + 修 bug）
- 卸载功能（sidecar 写但不删 — 卸载时是否清理 sidecar 留给后续）

---

## 6. 测试 / 验证

### 6.1 手动验证清单
- [ ] 启动 `cd frontend && npm run dev`，浏览器开 `http://localhost:5173`
- [ ] Hero 4 格统计面板正确显示数字（Skills / Repos / Cats / CLI）
- [ ] 本机能力区开篇 4 张系统能力卡可见，点击跳到对应锚点
- [ ] Skills 区每个 skill 显示 desc_zh（如果 latest.json 里有）+ ↗ GitHub 按钮（如果有 url）
- [ ] 点击 ↗ GitHub 按钮新窗口打开对应 repo（事件 `.stop` 不冒泡）
- [ ] 点击 Skills 卡其他区域不跳 GitHub（不触发任何导航）
- [ ] 找一个 latest.json 里没有的 skill（手动装个），desc 走 SKILL.md fallback
- [ ] **一键安装**：点推荐区「一键安装」按钮，请求 `/api/install` 不再报 `invalid skill name`（验证：前端发 `name="obra/superpowers"` 时后端不再 ValueError，而是写入 `~/.cache/lodestone/skills/superpowers/` 并 symlink 到 `~/.claude/skills/superpowers`）
- [ ] 装完后本机能力区立即多出该 skill
- [ ] sidecar `~/.cache/lodestone/origins.json` 存在且包含新装的 skill
- [ ] 错误场景：把 url 改成 `https://gitlab.com/foo/bar` 触发，应该弹 5s 红 toast

### 6.2 回归
- [ ] `out/` 旧静态 HTML 模式（README 提到有但代码已移除）— 不需要
- [ ] `data/zh_cache.json` 翻译缓存 — 不需要
- [ ] `data/crawl.log` — 不需要
- [ ] 30s 轮询 — fetchAll 仍能完成（< 200ms）

### 6.3 自动化（可选，不阻塞）
- 单元测试：`install_skill_from_github("foo/bar", "")` 应该不抛 ValueError
- 单元测试：`detect_local_skills()` 对一个 `latest.json` 里存在的 skill 返回 `source: "cache"`

---

## 7. 改动文件清单

| 文件 | 改动类型 | 估行数 |
|------|---------|--------|
| `frontend/src/App.vue` | 改 Hero / 本机能力区模板 + 新 `meta.url/desc/topics/stars/source` 字段读取 | +60 -15 |
| `frontend/src/style.css` | 加 `.capability-card`、`.stat-tile`、`.system-cap-card` 类 | +40 |
| `radar.py` | 改 `install_skill_from_github`（校验+sidecar）、改 `detect_local_skills`（多源 desc）、加 `SKILL_ORIGINS` 常量 | +60 -20 |

总计 ~125 行新增/修改，单文件不超过 100 行新增。

---

## 9. 5k+ 顶级项目（/top 独立路由）

**用户新增需求**：
> 爬取的数据太少了，超过 5k 星的都应该爬取，可以做成炫酷的分页，利用可读性很强的视觉效果可以看到目前最主流的 AI 方面的工具

### 9.1 范围 / 决策
| 决策 | 选 |
|------|----|
| 处理位置 | 扩当前 spec（一并落地） |
| 页面位置 | 独立路由 `/top`（`?page=top` query 参数，0 新依赖） |
| 分页风格 | A. 大卡 12 项/页 + 翻页 |

### 9.2 后端改动

#### 9.2.1 `crawl()` 增加 5k+ 抓取 pass
**位置**：`radar.py:439-518`

**改动**：
- 在现有 9 类抓取结束后，加一个 `top_5k_pass`：
  ```python
  TOP_5K_QUERIES = [
      "stars:>5000 topic:ai",
      "stars:>5000 topic:llm",
      "stars:>5000 topic:agent",
      "stars:>5000 topic:rag",
      "stars:>5000 topic:claude OR topic:claude-code OR topic:mcp",
  ]
  ```
  5 个查询 × 每查询最多 10 页（API 上限） = 50 次 API 调用 — **会踩 rate limit**
- **rate limit 缓解**（必做）：
  - 每个查询之间 `time.sleep(2)`（30 req/min limit）
  - 总耗时：5 查询 × 10 页 × 2s = 100s ≈ 1.7 分钟（用户已接受 1-2 分钟 crawl）
  - 如果中途撞 limit，`gh_search` 已经有 5xx 重试，爬到一半就保存已有的
- 去重合并到 `top_5k_repos: {name → repo_data}` 字典（同 owner/repo 跨多 topic 的合并）
- 排序：按 stars 降序，截前 200（避免 latest.json 爆掉；200 项 × 500 字节 = 100KB）
- **关键过滤**：5k+ star 的项目大多数是 awesome-list / 老牌框架（如 langchain、transformers），只取 AI 相关（命中至少一个 `TOPIC_BLACKLIST` 之外的话题）
  - 黑名单（不算 AI）：`blockchain`, `crypto`, `game`, `unity-template`, `flutter`, `awesome-go`, `awesome-rust`, `awesome-python` 之外的，**至少含一个 AI 关键词 topic**：`ai`, `llm`, `gpt`, `agent`, `claude`, `openai`, `rag`, `embedding`, `vector`, `mcp`, `chatbot`, `transformer`, `langchain`, `huggingface`, `prompt`, `copilot`, `stable-diffusion`, `text-to-image`, `multimodal`
- 输出加到 snapshot：
  ```python
  snapshot["top_5k_plus"] = {
      "count": len(top_5k_repos),
      "fetched_at": now,
      "repos": [top_200_sorted_by_stars],
  }
  ```
- 翻译：`desc_zh` / `facts` / `local_installed` 同现有逻辑（re-use 翻译缓存）

**新写常量**（在文件顶部 CATEGORIES 附近）：
- `TOP_5K_QUERIES: list[str]`
- `AI_TOPIC_WHITELIST: set[str]`（过滤用）
- `TOP_5K_LIMIT: int = 200`

#### 9.2.2 新增 `/api/top` 端点
**位置**：`radar.py:serve` 的 `do_GET`（1167 行附近）

**新增路由**：
```python
if self.path.startswith("/api/top"):
    # Query: ?page=N&size=12&sort=stars
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    page = max(1, int(qs.get("page", [1])[0]))
    size = min(48, max(1, int(qs.get("size", [12])[0])))
    sort = qs.get("sort", ["stars"])[0]  # stars | name | recent

    latest = DATA / "latest.json"
    if not latest.exists():
        return self._json({"error": "no data"}, status=503)
    snap = json.loads(latest.read_text())
    all_repos = snap.get("top_5k_plus", {}).get("repos", [])

    # 客户端排序：stars / name / recent (按 pushed)
    if sort == "name":
        all_repos = sorted(all_repos, key=lambda r: r["name"].lower())
    elif sort == "recent":
        all_repos = sorted(all_repos, key=lambda r: r.get("pushed", ""), reverse=True)
    # default stars desc (already sorted by crawler)

    total = len(all_repos)
    pages = (total + size - 1) // size
    start = (page - 1) * size
    return self._json({
        "repos": all_repos[start:start + size],
        "page": page,
        "size": size,
        "total": total,
        "pages": pages,
        "sort": sort,
    })
```

**为何客户端分页**：数据已经在 JSON 里，client 切比 server 切省一个端点；~200 项一次性返回 ≈ 100KB，可接受。

### 9.3 前端改动

#### 9.3.1 路由（query 参数模式，0 新依赖）
**位置**：`frontend/src/App.vue`

- 新 ref：`const view = ref(window.location.search.includes('page=top') ? 'top' : 'main')`
- 新监听：`window.addEventListener('popstate', () => { view.value = ... })`
- Hero 加一个「🌟 5k+ 顶级 AI 工具」按钮（紧邻「重新爬取」），点击 `history.pushState({}, '', '?page=top')` 切换到 /top
- /top 视图点返回键 → `history.back()` → 回到主页（用 `popstate` 监听）

**为何不用 vue-router**：vue-router 多 30KB，单页面加 200 个文件逻辑杀鸡用牛刀；query 参数 + popstate 一共 10 行。

#### 9.3.2 /top 页面组件（写在 `App.vue` 里，单文件）
**位置**：`App.vue` template 中根据 `view === 'top'` 渲染不同的 main

**结构**：
```
<main v-if="view === 'top' && topData">
  <!-- Hero -->
  <header class="aurora-1 full-bg">
    <h1>🌟 AI Top 5,000+</h1>
    <p>主流 AI 工具 · 按 ⭐ 排序 · 共 {{ topData.total }} 个</p>
    <input v-model="topQ" placeholder="搜索..." />
    <select v-model="topSort">stars / name / recent</select>
  </header>

  <!-- 12 大卡 3 列 -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
    <div v-for="r in topData.repos" class="top-card">
      <div class="rank-badge">#{{ (topData.page-1)*12 + i + 1 }}</div>
      <h2>{{ r.name }}</h2>
      <div class="stars">⭐ {{ r.stars.toLocaleString() }}</div>
      <p class="lang">{{ r.lang }}</p>
      <p class="desc">{{ r.desc_zh || r.desc }}</p>
      <div class="topics">{{ topics chips }}</div>
      <div class="actions">
        <el-button @click="openUrl(r.url)">↗ GitHub</el-button>
        <el-button v-if="!r.local_installed" @click="installSkill(r)">⬇ 安装</el-button>
        <span v-else>✓ 已装</span>
      </div>
    </div>
  </div>

  <!-- 翻页 -->
  <div class="pagination">
    <button @click="topPage = 1">«</button>
    <button v-for="p in visiblePages" @click="topPage = p" :class="{active: p === topData.page}">{{ p }}</button>
    <button @click="topPage = topData.pages">»</button>
  </div>
</main>
```

**响应式**：
- 桌面：3 列 × 4 行 = 12 卡
- 平板：2 列 × 6 行
- 手机：1 列 × 12 行

**视觉增强**（style.css 新加 `.top-card`）：
```css
.top-card {
  position: relative;
  background: linear-gradient(135deg, rgba(124,58,237,0.08), rgba(6,182,212,0.06));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 1.25rem;
  padding: 1.5rem;
  min-height: 220px;
  transition: all 0.2s ease;
}
.top-card:hover {
  transform: translateY(-4px);
  border-image: linear-gradient(135deg, #7c3aed, #06b6d4) 1;
  box-shadow: 0 16px 48px rgba(124,58,237,0.2);
}
.top-card .rank-badge {
  position: absolute; top: 1rem; right: 1rem;
  font-family: ui-monospace, monospace;
  font-size: 0.75rem; color: #fbbf24;
  background: rgba(251,191,36,0.1);
  padding: 2px 8px; border-radius: 9999px;
}
```

#### 9.3.3 分页组件
- 页码 1-N，超长时省略（1 ... 5 6 [7] 8 9 ... 42）
- `visiblePages` computed：当前页 ±2 + 首尾
- 大箭头键 + 数字键
- 当前页用渐变背景（与 Hero 标题同一渐变）

#### 9.3.4 安装按钮复用
- 复用 `installSkill()` 函数
- 装完后 `r.local_installed = true`（响应里加），卡片即时显示「✓ 已装」

### 9.4 改动文件清单（追加）

| 文件 | 改动类型 | 估行数 |
|------|---------|--------|
| `radar.py` | `crawl()` 加 5k+ pass、新增 `TOP_5K_QUERIES`/`AI_TOPIC_WHITELIST` 常量、新增 `/api/top` 端点 | +90 -5 |
| `frontend/src/App.vue` | 新增 `view` ref + popstate 监听、新增 `topData` ref + `fetchTop()`、新增 /top 页面模板、新增分页 computed | +180 -10 |
| `frontend/src/style.css` | 加 `.top-card`、`.pagination`、`.rank-badge` 类 | +40 |

**累计**：
- 之前：~125 行
- 现在：~420 行新增/修改

### 9.5 风险

- **GitHub API rate limit**：5k+ pass 50 次调用 + 现有 ~27 次 = 77 次，踩线。**缓解**：每个查询间 `time.sleep(2)`、5xx 重试（gh_search 已有）、爬一半保存已有
- **latest.json 膨胀**：5k+ 200 项 × 500 字节 = 100KB 新增，加上翻译后 ~250KB，文件从 ~3MB → ~3.3MB，可接受
- **5k+ 列表被无关 repo 污染**（如 awesome-go）：靠 `AI_TOPIC_WHITELIST` 过滤；如果 5k+ list 看到 langchain/transformers 这种该有的在，就 OK
- **首次 crawl 慢**：从 ~1 分钟 → ~3 分钟；UI 已显示「1-2 分钟」文案，改成「首次 3 分钟左右」（或更精确测后改）
- **/top 路由深链 / 刷新**：query 参数天然支持刷新（`?page=top` 解析为 view='top'）；`/top` 直接访问 → 用户输 `http://localhost:5173/?page=top` 即可

### 9.6 验证清单（追加）
- [ ] 跑 `radar.py crawl`，日志显示 `[crawl] 5k+ pass: N repos fetched`
- [ ] `data/latest.json` 有 `top_5k_plus.count > 0` 字段
- [ ] 5k+ 列表前 5 是真正主流 AI 工具（如 langchain、transformers、ollama、open-webui、comfyui）— 不是 awesome-go
- [ ] 浏览器开 `http://localhost:5173/?page=top`，看到 /top 页面
- [ ] 12 个大卡渲染正常，rank badge 数字正确（1-12）
- [ ] 翻页：点 2 → 看到 13-24，点末页 → 看到最后 12 个
- [ ] 搜索：输入 `langchain` → 只显示 langchain 相关
- [ ] 排序：切到 `name` → 按字母排，切到 `recent` → 按 pushed 降序
- [ ] 点 ↗ GitHub 按钮新窗口打开
- [ ] 点 ⬇ 安装按钮 → 装到本机 + 卡片变「✓ 已装」
- [ ] Hero 5k+ 按钮点击进入 /top；浏览器返回键回主页

---

## 8. 风险 / 边界

- **sidecar 写失败**（磁盘满 / 权限）：不影响安装主流程，只在 `~/.cache/lodestone/origins.json` 写失败时 `pass`（try/except 包住），记一行 warning 到 stderr
- **latest.json 太大**（万一几千 repo）：当前 ~3MB，O(n) 遍历一次构建 dict ≈ 50ms，可接受
- **SKILL.md 不规范**（无 frontmatter 或格式错）：fallback 静默跳过，`source` 标记为 `"none"`
- **owner/repo 含非法字符**（`@` `#` 等）：新校验 `^[\w.-]+/[\w.-]+$` 直接拒绝，错误信息保留 `invalid skill name` 风格
- **前端 meta.url 为 null** 但 source==="cache"：理论上不可能（latest.json 里的 repo 都有 url），但模板用 `v-if` 兜底
