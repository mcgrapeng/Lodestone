# Lodestone 架构重构 + 安装审计 + UI 回归 Appica 设计

日期:2026-09-07
状态:**已实施完毕(2026-09-08)** — Plan A 审计零漏报+卸载两 bug 修复闭环;Plan B 八模块拆分(radar.py 4779→163 行 facade);Plan C Appica token 回归+侧边栏。执行分支 `refactor/arch-install-ui`。

## 背景与目标

- radar.py 已增长到 4779 行单体,爬取/过滤/翻译/安装/检测/serve 全部混居,修改互相污染。
- 本机安装状态仍有「已装但显示未装」的误报(2026-09-07 已修三根因后仍有残余)。
- 前端叠加了大量自定义颜色(渐变/彩色 accent),偏离 @appica/ui-react 默认 token;分类横向滚动条交互差。

三个子项目相互独立,执行顺序 A → B → C。

## A. 安装状态全面审计 + 闭环修复

### 审计方法(证据先行)

写一次性对照脚本(throwaway,不进主干):
1. 枚举本机全部安装形态:四平台技能目录(`_SKILL_PLATFORM_PATHS`)条目、symlink 目标还原、`installed_plugins.json` 全部插件、`~/.claude/commands|agents`。
2. 对每条推导「应判已装」的 GitHub 全名集合(origin_full / meta.url / marketplace 映射 / 目录名)。
3. 与 `/api/data` 各卡片的 `local_installed` 实际值 diff,输出不一致清单(方向:漏报/误报分开)。

### 根因候选(审计验证)

| # | 候选 | 机制 | 修复方向 |
|---|---|---|---|
| A1 | 官方 marketplace 插件 origin 错位 | `mattpocock-skills@claude-plugins-official` 的缓存 `.git` 指向 marketplace 仓库而非作者仓库 → full-name 匹配失败 | 解析 marketplace 的 `.claude-plugin/marketplace.json`(插件名 → source repo 映射),缓存于 detect 结果 |
| A2 | 手装/共享目录技能 | `~/.agents/skills` symlink 不指向 `~/.cache/lodestone` → `origin_full` 为空;PG 索引不认识目录名 → 漏 | PG seg 兜底(已有);marketplace 映射;接受合理残余并在审计报告标注 |
| A3 | 卸载语义 | `uninstall_skill` 删全部平台链接+保留缓存的行为是否符合预期 | 审计确认;如需按平台卸载则 API 加 targets(默认全卸) |

### 闭环验证

用 `octocat/Hello-World` 真实执行:安装(默认 claude)→ 断言徽标翻转 → 更新(force_update)→ 断言 up_to_date → 卸载 → 断言徽标消失、四平台链接与 sidecar 清理干净。

## B. 域模块拆分 + facade

### 目标结构

```
lodestone/
├─ radar.py            # 薄 facade:from radar_pkg.* import *(re-export 全部公开名)
├─ radar_pkg/
│  ├─ __init__.py
│  ├─ core.py          # CATEGORIES / TOP_5K_QUERIES / MANUAL_SEED / CURATED /
│  │                   # AI_TOPIC_* 过滤 / is_ai_relevant / normalize_git_url / 路径常量
│  ├─ gh.py            # gh_search / _gh_search_html_fallback / gh_fetch_repo /
│  │                   # fetch_github_trending / fetch_recent_active_repos
│  ├─ translate.py     # translate_text / translate_batch / zh 缓存 / enrich_summaries / get_readme_zh
│  ├─ crawl.py         # crawl / _crawl_inner / crawl 锁 / today / audit
│  ├─ detect.py        # 平台表 / detect_local_skills / detect_cli_tools / TTL 缓存
│  ├─ install.py       # install_skill_from_github / uninstall / replace / find_skill_replacements / set_capability_origin / install_cli_wrapper
│  ├─ match.py         # _owner_repo_from_url / _owner_repo_from_link_target / _installed_segments / _annotate_local_installed / _build_plugin_segs / _load_repo_index
│  └─ serve.py         # serve() + Handler(纯组装,调用上述模块)
├─ sources/ scrapers/ db/   # 不变
├─ refresh_snapshot.py      # 零改动(经 facade)
└─ tests/                   # 零改动(经 facade;mock 路径 radar._xxx 继续有效因 facade re-export)
```

### 依赖方向(无环)

```
core ← gh ← crawl
core ← translate ← crawl
core ← detect(match 不 import detect — match 是纯函数,只消费 detect 的输出 dict)
core ← install(detect 的失效缓存由 install 调用)
crawl / serve 组装其余全部
```

规则:core 不 import 任何兄弟模块;gh/translate/detect/match/install 只 import core;crawl/serve 可 import 全部。

### 迁移策略

逐模块搬移,每步:搬 → radar.py 补 re-export → 跑三套测试(tests/test_radar、test_install_detection、test_crawl_sources)→ git commit(单模块单 commit)。
测试中 `patch("radar.Path.home")` / `patch.object(radar, "SKILLS_CACHE")` 等 mock 经 facade re-export 继续指向原对象,facade 必须 `from x import y`(绑定同一对象)而非 `import x`(属性查找)——迁移时逐点验证。

### 验证

- 三套单测全绿(40+ 用例)
- `python3 radar.py today` / `serve` 冒烟
- 审计脚本(A)重跑,结果与拆分前一致

### 修正(2026-09-07 计划期发现)

「tests 零改动」不可达:`mock.patch("radar.X")` 替换的是 facade 名字,定义模块内部的 globals 查找不受影响,隔离会失效。修正承诺为:**测试断言与逻辑零改动,仅 patch 目标路径从 `radar.X` 改为 `radar_pkg.<定义模块>.X`**(约 8 处);`refresh_snapshot.py` 保持真零改动(仅调用公开函数,无 patch)。

## C. UI 回归 Appica 默认视觉 + 左侧分类侧边栏

### 配色

- 删除 `app.css` 中 body 的 radial 渐变背景、`gradient-text` 硬编码三色、`categoryAccent` 每分类彩色渐变。
- 全部回归 appica token:近黑 primary、蓝 secondary、绿 success(语义:已装徽标)。选中态用 `primary`/ring,不再用分类彩色。
- 卡片 hover、chip、divider 等一律用 token 类(`bg-background-subtle` 等),删除手写 rgba。

### Logo

- 去掉渐变方块 + Zap 图标 + gradient-text 标题。
- 替换为 appica 风格 monochrome 徽标:radar/信号类图标(优先 `@appica/icons-react` 现有图标,无合适的用 lucide `Radar`)+ token 化排版(`text-foreground` 主标题、`text-foreground-subtle` 副标题)。

### 分类布局

- `CategoryBrowser` 重构:左侧固定侧边栏(约 220-240px,图标 + 名称 + 计数),26 分类全部可见、当前项 primary 高亮;内容区单分类。
- `<lg` 断点:侧边栏折叠为顶部 appica `Select` 下拉(单选分类),横向滚动条彻底移除。
- 组件机会点:筛选换 appica `Select`/`Toggle`,卡片操作换 `Button`/`Tooltip`(现有 Drawer/Button 已在用)。

### 验证

- `npm run build` 通过;Playwright 截图走查:侧边栏(选中态/窄屏折叠)、卡片、抽屉(安装平台多选)、已装徽标、logo。

## 明确不做(YAGNI)

- 不做 hexagonal/ports-adapters(单仓 CLI 工具收益低)。
- 不改 sources/scrapers/db 的内部结构(已是独立模块)。
- 不引入状态管理库/UI 框架迁移。
- 不新增后端 API(除 A3 若审计结论需要按平台卸载)。

## 风险与对策

| 风险 | 对策 |
|---|---|
| 拆分引入行为回归 | A 的审计脚本做前后对照;三套测试;单模块 commit 可回退 |
| facade mock 语义变化 | 迁移时逐点验证 mock 绑定;tests 零改动是验收标准 |
| marketplace.json 拉取失败 | 缓存 + 失败静默回退现状(不比现在差) |
| UI 改动破坏现有交互 | build + Playwright 走查清单 |
