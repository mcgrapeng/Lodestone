# Plan B:radar.py 域模块拆分 + facade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 4779 行的 radar.py 拆成 `radar_pkg/` 八个域模块,radar.py 退化为薄 facade,行为零变化。

**Architecture:** 按依赖无环方向逐模块搬移(core → match → detect → gh → translate → install → crawl → serve),每步 facade re-export + 三套测试 + 单模块 commit。模块内代码**原样搬移**(不重写),仅 import 头与跨模块引用调整。

**Tech Stack:** Python 3.13 stdlib;无新依赖。

**Spec:** `docs/superpowers/specs/2026-09-07-arch-install-ui-design.md`(B 节 + 修正节)

## Global Constraints

- **行为零变化**:只搬移不改写;发现坏味道记 TODO 注释,不顺手修。
- 每任务结束三套测试全绿:`python3 -m tests.test_radar && python3 -m tests.test_install_detection && python3 -m tests.test_crawl_sources`
- 测试只改 patch 目标路径(`radar.X` → `radar_pkg.<定义模块>.X`),断言/逻辑零改动(spec 修正节)。
- `refresh_snapshot.py`、`SKILL.md`、serve/crawl CLI 入口零改动。
- 模块 import 规则:core 无兄弟依赖;match 仅 core;detect 仅 core+match;gh/translate 仅 core;install 仅 core+detect+match;crawl/serve 全部可用。违反即重构失败。
- git 每任务一个 commit。

## 符号→模块分配表(搬移的权威清单)

| 模块 | 搬入符号(从 radar.py 原样剪切) |
|---|---|
| `core.py` | 常量 `ROOT DATA SKILLS_CACHE SKILL_ORIGINS TRANSLATE_CACHE README_ZH_CACHE`、`CATEGORIES TOP_5K_QUERIES TOP_5K_LIMIT`、`AI_TOPIC_HARD AI_TEXT_HINTS CURATED_ALLOWLIST AI_TOPIC_BLOCKLIST NON_AI_DEV_DESC_BLOCKLIST`、`_SEARCH_PACE GH_SEARCH_STATS CRAWL_LOCK CRAWL_LOCK_STALE_S FRONTMATTER_DESC`、函数 `is_finance_blocked is_ai_relevant normalize_git_url _parse_frontmatter_desc _repo_slug_from_url`、`__doc__` 模块说明 |
| `match.py` | `_owner_repo_from_url _owner_repo_from_link_target _marketplace_plugin_sources _load_repo_index _repo_index_cache _REPO_INDEX_TTL invalidate_repo_index _installed_segments _annotate_local_installed _build_plugin_segs` |
| `detect.py` | `_SKILL_PLATFORM_PATHS SKILL_PLATFORM_LABELS SUPPORTED_CLIS _DEFAULT_INSTALL_TARGETS _skills_root_for`、`_LOCAL_SCAN_TTL _local_scan_cache _local_scan_lock invalidate_local_scan detect_local_skills detect_cli_tools` |
| `gh.py` | `_search_pace gh_search _parse_github_search_html _gh_search_html_fallback gh_fetch_repo fetch_github_trending fetch_recent_active_repos` |
| `translate.py` | `_LANG_NAV_WORDS _clean_readme_text _summary_from_entry _build_summary_zh enrich_summaries translate_text translate_batch _fetch_readme_from_github _strip_markdown_to_text _chunked_translate _looks_translated get_readme_zh` |
| `install.py` | `_git_head_sha _git_pull_fast_forward _git_remote_head_sha install_skill_from_github uninstall_skill replace_skill find_skill_replacements set_capability_origin group_capabilities_by_origin install_cli_wrapper` |
| `crawl.py` | `acquire_crawl_lock release_crawl_lock crawl_lock_held crawl _crawl_inner today audit` |
| `serve.py` | `serve web`(含 Handler 内部类) |

**tests patch 路径修正表**(搬移对应模块时同步改):

| 测试现行 patch | 改为 |
|---|---|
| `patch("radar.Path.home")` | 保留(patch 类方法,全局生效,无需改) |
| `patch.object(radar, "SKILLS_CACHE", …)` | `patch.object(radar_pkg.detect, "SKILLS_CACHE", …)` — SKILLS_CACHE 定义在 core、detect/gh/install/match 使用;**统一改为 `patch("radar_pkg.core.SKILLS_CACHE", …)` 并在使用模块以 `from radar_pkg import core` + `core.SKILLS_CACHE` 属性访问**(from-import 绑定无法被 patch 穿透,故使用模块一律属性访问共享常量) |
| `patch.object(radar, "SKILL_ORIGINS")` / `TRANSLATE_CACHE` / `README_ZH_CACHE` | 同上,`radar_pkg.core.*` 属性访问 |
| `patch.object(radar, "_SKILL_PLATFORM_PATHS")` | `radar_pkg.detect._SKILL_PLATFORM_PATHS` |
| `patch("radar._load_repo_index")` | `radar_pkg.detect._load_repo_index`(detect 内部调用)或 `radar_pkg.match._load_repo_index`(match/爬取侧调用)——以调用点所在模块为准,两处都可能 |
| `patch("radar.translate_batch")` | `radar_pkg.translate.translate_batch` |
| `mock.patch.object(radar, "_marketplace_plugin_sources")` 及 `.cache_clear` | `radar_pkg.match._marketplace_plugin_sources` |

**共享可变常量访问规约**(全计划最重要的一条):`SKILLS_CACHE / SKILL_ORIGINS / TRANSLATE_CACHE / README_ZH_CACHE / _SKILL_PLATFORM_PATHS / GH_SEARCH_STATS / _SEARCH_PACE` 在使用方模块一律写 `from radar_pkg import core` 然后 `core.SKILLS_CACHE`(属性访问,可被 patch 穿透);**禁止** `from radar_pkg.core import SKILLS_CACHE`(值绑定,patch 穿不透)。

---

### Task 1: 骨架 + core.py

**Files:**
- Create: `radar_pkg/__init__.py`(空)、`radar_pkg/core.py`
- Modify: `radar.py`(剪切常量与过滤函数,保留其余)

**Interfaces:**
- Produces: `radar_pkg.core` 的全部符号(见分配表);facade 段 `from radar_pkg.core import *`(core 定义 `__all__`)

- [ ] **Step 1: 建 `radar_pkg/` 与空 `__init__.py`**(`mkdir radar_pkg && touch radar_pkg/__init__.py`)
- [ ] **Step 2: 建 core.py**:文件头 `# -*- coding: utf-8 -*-` + radar.py 的 stdlib import(json/os/re/sys/time/datetime/urllib/shutil/subprocess/pathlib/typing)+ 按分配表剪切符号粘入;尾部定义 `__all__ = [全部公开名 + 下划线名也含](供 facade *)`。
- [ ] **Step 3: radar.py 对应段替换为**:

```python
# ponytail: 2026-09 架构拆分 — radar.py 是薄 facade,实现在 radar_pkg/
from radar_pkg.core import *  # noqa: F401,F403
from radar_pkg.core import _SEARCH_PACE, GH_SEARCH_STATS, CRAWL_LOCK, CRAWL_LOCK_STALE_S, FRONTMATTER_DESC  # 下划线名 * 不导
```

(后续任务逐行追加同型 re-export;剪切后 radar.py 内对这些符号的**使用处**改为 `core.X` 属性访问:`from radar_pkg import core`。)

- [ ] **Step 4: 跑三套测试**(此时多数测试仍测 facade 上的过滤函数 — re-export 生效应全绿;若有失败,失败点即遗漏符号,补 re-export)
- [ ] **Step 5: Commit** `refactor: 抽出 radar_pkg.core(常量/过滤/归一化)`

### Task 2: match.py

**Files:**
- Create: `radar_pkg/match.py`;Modify: `radar.py`、`tests/test_install_detection.py`

**Interfaces:**
- Consumes: `core.SKILLS_CACHE`(属性访问)、`core.normalize_git_url` 不需要、`db`(外部包)
- Produces: 分配表 match 全部符号;`radar._installed_segments` 等 facade 名继续可用

- [ ] **Step 1: 按分配表剪切 9 个符号到 match.py**(头部 `from radar_pkg import core` + `import functools/json/time/threading`;SKILLS_CACHE 引用改 `core.SKILLS_CACHE`)
- [ ] **Step 2: radar.py 追加 re-export + 使用点改 `from radar_pkg import match` 属性访问**
- [ ] **Step 3: 修 tests patch 路径**(按修正表:`_load_repo_index`/`_marketplace_plugin_sources`/`SKILLS_CACHE`/`SKILL_ORIGINS` 中属 match/detect 调用点的)
- [ ] **Step 4: 三套测试全绿**
- [ ] **Step 5: Commit** `refactor: 抽出 radar_pkg.match(已装匹配纯函数)`

### Task 3: detect.py

同 Task 2 节奏。剪切平台表与 detect_*;`_load_repo_index`/`_owner_repo_from_link_target` 来自 `from radar_pkg import match`;`SKILL_ORIGINS` 用 `core.SKILL_ORIGINS`。
tests 修正:`patch.object(radar, "_SKILL_PLATFORM_PATHS") → radar_pkg.detect._SKILL_PLATFORM_PATHS`。
Commit: `refactor: 抽出 radar_pkg.detect(本机能力扫描)`。

### Task 4: gh.py

剪切 7 个搜索/抓取函数;`_search_pace` 逻辑搬入并使用 `core._SEARCH_PACE`(属性访问);`GH_SEARCH_STATS` 计数用 `core.GH_SEARCH_STATS`。
Commit: `refactor: 抽出 radar_pkg.gh(GitHub 搜索/trending)`。

### Task 5: translate.py

剪切 12 个翻译/摘要函数;缓存文件常量 `core.TRANSLATE_CACHE`/`core.README_ZH_CACHE` 属性访问。
tests 修正:`patch("radar.translate_batch") → radar_pkg.translate.translate_batch`。
Commit: `refactor: 抽出 radar_pkg.translate(翻译与摘要)`。

### Task 6: install.py

剪切 10 个安装/替换函数;`core.SKILLS_CACHE`、`detect._skills_root_for`/`detect.SUPPORTED_CLIS`/`detect.invalidate_local_scan`、`match.invalidate_repo_index` 属性访问。
tests 修正:install 测试的 `SKILLS_CACHE`/`SKILL_ORIGINS`/`_SKILL_PLATFORM_PATHS` patch 路径。
Commit: `refactor: 抽出 radar_pkg.install(安装/卸载/替换)`。

### Task 7: crawl.py

剪切锁与编排;调用 `gh. gh_search`、`translate.translate_batch`、`detect.detect_local_skills`、`match._installed_segments`、`install` 无(crawl 不直接用)。
Commit: `refactor: 抽出 radar_pkg.crawl(爬取编排)`。

### Task 8: serve.py

剪切 serve/web(Handler 类整体);全部跨模块调用属性访问。`if __name__ == "__main__"` 入口保留在 radar.py,改为 `from radar_pkg.crawl import crawl …` 后分发。
Commit: `refactor: 抽出 radar_pkg.serve(HTTP API)— radar.py 至此为纯 facade`。

### Task 9: 终验

- [ ] 三套测试全绿;`python3 radar.py today` 冒烟输出正常
- [ ] `wc -l radar.py` ≤ 60 行;`grep -c "def " radar.py` = 0(纯 re-export + main 分发)
- [ ] 重启 8765/8767,curl `/api/stats` `/api/data` 200
- [ ] Plan A 审计脚本(若已删则用 `python3 -c "import radar; …"` 三行内联对照 detect/match 输出)结果与拆分前一致
- [ ] Commit(空则跳过)+ 更新 spec 执行状态
