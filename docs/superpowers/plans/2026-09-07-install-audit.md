# Plan A:安装状态全面审计 + 闭环修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消灭「已装但显示未装」——全量对照本机安装形态与 `/api/data` 标注,修复 marketplace 插件 origin 错位等根因,并用 Hello-World 走通装/更/卸闭环。

**Architecture:** 一次性审计脚本产出不一致清单(证据)→ 修复 `radar.py` 匹配层(`_installed_segments` 增加 marketplace.json 源仓库映射)→ 审计复跑归零 → 真实闭环验证。

**Tech Stack:** Python 3.13(stdlib + gh CLI),radar.py 现有 detect/match 管线。

**Spec:** `docs/superpowers/specs/2026-09-07-arch-install-ui-design.md`(A 节)

## Global Constraints

- 行为基线:修复只允许让更多「真已装」被标注,**不得引入误报**(对照 `BehiSecc/awesome-claude-skills` 必须保持 False)。
- 测试套件:`python3 -m tests.test_radar`、`tests.test_install_detection`、`tests.test_crawl_sources` 每任务结束全绿。
- 本机 curl 一律 `--noproxy '*'`(shell 有 http_proxy=127.0.0.1:7890)。
- marketplace.json 路径:`~/.claude/plugins/marketplaces/<marketplace>/.claude-plugin/marketplace.json`。

---

### Task 1: 审计脚本(throwaway,不 commit)

**Files:**
- Create: `audit_install_state.py`(仓库根,执行完删除)

**Interfaces:**
- Consumes: `radar.detect_local_skills`、`radar._installed_segments`、`radar._build_plugin_segs`、`radar._annotate_local_installed`
- Produces: stdout 不一致清单 + 退出码(0=零不一致)

- [ ] **Step 1: 写审计脚本**

```python
# -*- coding: utf-8 -*-
"""一次性审计:本机全部安装形态 vs /api/data 的 local_installed 标注。
用法: python3 audit_install_state.py [--api http://127.0.0.1:8765]"""
import json
import subprocess
import sys
import urllib.request

import radar

API = "http://127.0.0.1:8765"


def expected_installed_names() -> set[str]:
    """从本机安装形态推导『应判已装』的小写 GitHub 全名集合(独立于 radar 实现,
    用作 oracle:直接枚举四平台目录 + 插件清单,逐条还原 owner/repo)。"""
    names: set[str] = set()
    # 1. 四平台技能目录:symlink → SKILLS_CACHE/owner__repo 还原;其余靠目录名
    for cli, path in radar._SKILL_PLATFORM_PATHS.items():
        d = __import__("pathlib").Path(path).expanduser()
        if not d.exists():
            continue
        for entry in d.iterdir():
            if entry.name.startswith(".") or not (entry.is_dir() or entry.is_symlink()):
                continue
            full = radar._owner_repo_from_link_target(entry)
            if full:
                names.add(full.lower())
            else:
                names.add(f"~dir~/{cli}/{entry.name.lower()}")  # 无法还原 — 单列
    # 2. 插件:installed_plugins.json + marketplace.json source.url
    import pathlib
    home = pathlib.Path.home()
    market_src: dict[str, str] = {}  # "mp/plugin" -> full name
    for mp_dir in (home / ".claude/plugins/marketplaces").glob("*/"):
        mj = mp_dir / ".claude-plugin" / "marketplace.json"
        if not mj.exists():
            continue
        try:
            data = json.loads(mj.read_text())
        except Exception:
            continue
        for p in data.get("plugins") or []:
            src = p.get("source") or {}
            url = src.get("url") if isinstance(src, dict) else None
            full = radar._owner_repo_from_url(url or "")
            if full:
                market_src[f"{mp_dir.name}/{p.get('name')}"] = full.lower()
    ip = home / ".claude/plugins/installed_plugins.json"
    if ip.exists():
        for key in (json.loads(ip.read_text()).get("plugins") or {}):
            name, _, mp = key.partition("@")
            if f"{mp}/{name}" in market_src:
                names.add(market_src[f"{mp}/{name}"])
            else:
                names.add(f"~plugin~/{mp}/{name.lower()}")
    return names


def main() -> int:
    expected = expected_installed_names()
    raw = subprocess.run(
        ["curl", "-s", "--noproxy", "*", f"{API}/api/data"],
        capture_output=True, text=True, timeout=60,
    ).stdout
    data, _ = json.JSONDecoder().raw_decode(raw.lstrip())

    cards: dict[str, bool] = {}

    def walk(rows):
        for r in rows or []:
            if isinstance(r, dict):
                if "repos" in r:
                    walk(r["repos"])
                elif "name" in r:
                    cards[r["name"].lower()] = bool(r.get("local_installed"))

    walk(data.get("hot_now"))
    walk(data.get("categories"))

    gh_expected = {n for n in expected if not n.startswith(("~dir~", "~plugin~"))}
    misses = sorted(n for n in gh_expected if n in cards and not cards[n])
    unknown = sorted(n for n in gh_expected if n not in cards)
    dir_items = sorted(n for n in expected if n.startswith("~dir~"))
    plug_items = sorted(n for n in expected if n.startswith("~plugin~"))

    print(f"oracle 可还原 GitHub 全名: {len(gh_expected)}")
    print(f"卡片总数: {len(cards)}, 其中已装: {sum(cards.values())}")
    print(f"\n[漏报] 装了但卡片未标已装({len(misses)}):")
    for n in misses:
        print("   ", n)
    print(f"\n[卡片外] oracle 命中但不在当前卡片集({len(unknown)}):")
    for n in unknown[:20]:
        print("   ", n)
    print(f"\n[无法还原-目录]({len(dir_items)}):", *dir_items[:15])
    print(f"[无法还原-插件]({len(plug_items)}):", *plug_items[:15])
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 跑审计,保存输出**

Run: `python3 audit_install_state.py | tee data/audit-before.txt`
Expected: 输出漏报清单(misses 非空的可能性高——marketplace 插件错位);退出码记录。

- [ ] **Step 3: 人工核对漏报清单前 5 项**

对每项:`ls ~/.claude/plugins/cache/<mp>/<plugin>/` 与 `gh api repos/<owner>/<repo> --jq .full_name` 确认真是同源仓库。剔除 oracle 自身误判(如有)。

### Task 2: marketplace.json 源仓库映射(修 A1)

**Files:**
- Modify: `radar.py`(`_installed_segments` 函数,现位于 ~3570)
- Test: `tests/test_install_detection.py`

**Interfaces:**
- Consumes: `radar._owner_repo_from_url(url) -> str | None`(已有)
- Produces: `_marketplace_plugin_sources() -> dict[str, str]`(键 `"{marketplace}/{plugin_name}"`,值小写 `owner/repo`);`_installed_segments` 行为扩展:插件 origin 优先级变为 `插件缓存 .git > marketplace.json source.url > marketplace 仓库 URL`

- [ ] **Step 1: 写失败测试**

```python
def test_marketplace_plugin_sources_maps_to_author_repo():
    """marketplace.json plugins[].source.url 是真正的作者仓库
    (实测 mattpocock-skills → github.com/mattpocock/skills.git)。"""
    import json as _json

    radar._marketplace_plugin_sources.cache_clear()
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        mp_dir = home / ".claude" / "plugins" / "marketplaces" / "mp1" / ".claude-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(_json.dumps({
            "plugins": [
                {"name": "mattpocock-skills",
                 "source": {"source": "url",
                            "url": "https://github.com/mattpocock/skills.git"}},
                {"name": "agent-sdk-dev", "source": "./plugins/agent-sdk-dev"},
            ]
        }))
        with mock.patch("radar.Path.home", return_value=home):
            m = radar._marketplace_plugin_sources()
        assert m.get("mp1/mattpocock-skills") == "mattpocock/skills"
        assert "mp1/agent-sdk-dev" not in m  # 相对路径不产生映射
```

(测试文件顶部已 import `tempfile`/`mock`/`Path` 的话直接用;`functools.lru_cache` 挂在实现上,测试先 `cache_clear()`。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m tests.test_install_detection`
Expected: FAIL — `radar` 无 `_marketplace_plugin_sources`。

- [ ] **Step 3: 实现(加入 radar.py,放在 `_installed_segments` 前)**

```python
import functools


@functools.lru_cache(maxsize=1)
def _marketplace_plugin_sources() -> dict[str, str]:
    """marketplace.json plugins[].source.url → 作者仓库映射。
    键 "{marketplace}/{plugin_name}",值小写 owner/repo。
    相对路径 source('./plugins/x')不产生映射 — 那些插件归 marketplace 本体仓库。
    解析失败返回空 dict(调用方回退现有 .git/URL 逻辑,不比现状差)。"""
    out: dict[str, str] = {}
    mp_root = Path.home() / ".claude" / "plugins" / "marketplaces"
    if not mp_root.exists():
        return out
    for mp_dir in mp_root.iterdir():
        mj = mp_dir / ".claude-plugin" / "marketplace.json"
        if not mj.is_file():
            continue
        try:
            data = json.loads(mj.read_text())
        except (OSError, ValueError):
            continue
        for p in data.get("plugins") or []:
            if not isinstance(p, dict) or not p.get("name"):
                continue
            src = p.get("source")
            url = src.get("url") if isinstance(src, dict) else None
            full = _owner_repo_from_url(url or "")
            if full:
                out[f"{mp_dir.name}/{p['name']}"] = full.lower()
    return out
```

并在 `_installed_segments` 的插件循环中,`mp_source` 兜底**之前**插入映射查询:

```python
        # ponytail: marketplace.json 的 source.url 是作者仓库(实测
        # mattpocock-skills → mattpocock/skills),优先于 marketplace 本体 URL
        mp_map = _marketplace_plugin_sources()
        ...
        # 在 "if git_origin: segs.add(git_origin) elif mp_name in mp_source:" 处改为:
        if git_origin:
            segs.add(git_origin)
        elif f"{mp_name}/{name}" in mp_map:
            segs.add(mp_map[f"{mp_name}/{name}"])
        elif mp_name in mp_source:
            segs.add(mp_source[mp_name])
```

注意:该循环内已有变量 `name`(插件名)与 `mp_name`;`mp_map` 在循环外取一次。

- [ ] **Step 4: 跑三套测试全绿**

Run: `python3 -m tests.test_install_detection && python3 -m tests.test_radar && python3 -m tests.test_crawl_sources`
Expected: 全部 PASS。

- [ ] **Step 5: 重启 serve 使修复生效,审计复跑**

```bash
kill $(lsof -tiTCP:8765 -sTCP:LISTEN) $(lsof -tiTCP:8767 -sTCP:LISTEN) 2>/dev/null
nohup python3 radar.py serve 8765 > data/serve-8765.log 2>&1 &
nohup python3 radar.py serve 8767 > data/serve-8767.log 2>&1 &
sleep 3 && python3 audit_install_state.py | tee data/audit-after.txt
```
Expected: misses 数较 before 显著下降(mattpocock/skills 等 marketplace 插件卡片翻转)。

- [ ] **Step 6: Commit**

```bash
git add radar.py tests/test_install_detection.py
git commit -m "fix: 插件已装匹配接入 marketplace.json 源仓库映射

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: 审计驱动的残余修复(A2/A3,视 Task 2 后审计输出)

**Files:**
- Modify: `radar.py`(按审计结果定位)
- Test: 对应测试文件

**Interfaces:**
- Consumes: `data/audit-after.txt` 的 `[无法还原-目录]`/`[无法还原-插件]` 清单
- Produces: 修复 + 对应单测;若结论是「合理残余」则记录原因

- [ ] **Step 1: 逐条审 `[无法还原-*]` 清单**,按规则分类:
  - 目录项指向 `~/.agents/skills` 且 PG 索引能按目录名命中 → 已由 by_repo 兜底,卡片若在则不算漏;
  - 手装且目录名与任何卡片 seg 不一致 → **合理残余**(无元数据可还原),在 `data/audit-after.txt` 末尾追加 `[accepted] <名称>: 手装无 origin 元数据` 说明;
  - 插件项在 marketplace.json 无 url 映射 → 归 marketplace 本体,若该本体仓库是真实卡片(如 obra/superpowers 自建 marketplace)则正确;否则追加 `[accepted]`。
- [ ] **Step 2: 对每条真漏报写失败测试 → 最小修复 → 三套测试 → 逐一 commit**(与 Task 2 同节奏;每条一个 commit,message 注明审计条目)。
- [ ] **Step 3: 若审计确认卸载语义需按平台(卡片装在多平台、用户只想卸其一)**:为 `/api/uninstall` 增加 `targets` 可选参数(缺省=全平台,现行为),`uninstall_skill(name, targets=None)` 只删所选平台链接;不传时行为与现在完全一致。加测试:`uninstall_skill("octocat/Hello-World", targets=["claude"])` 只删 claude 链接。

### Task 4: Hello-World 真机闭环验证

**Files:**
- 无代码改动;验证脚本内联执行

**Interfaces:**
- Consumes: `/api/install`、`/api/update`、`/api/uninstall`、`/api/data`
- Produces: 验证记录(写入本计划文件末尾的执行日志区)

- [ ] **Step 1: 安装(默认 claude 平台)**

```bash
curl -s --noproxy '*' -X POST http://127.0.0.1:8765/api/install \
  -H 'Content-Type: application/json' \
  -d '{"name":"octocat/Hello-World","url":"https://github.com/octocat/Hello-World","targets":["claude"]}'
```
Expected: `"ok": true`;`ls -l ~/.claude/skills/Hello-World` 是 symlink → `~/.cache/lodestone/skills/octocat__Hello-World`;`~/.codex/skills`、`~/.config/opencode/skills` 无该链接。

- [ ] **Step 2: 徽标翻转断言**

```bash
curl -s --noproxy '*' http://127.0.0.1:8765/api/data | python3 -c "
import json,sys
d,_=json.JSONDecoder().raw_decode(sys.stdin.read().lstrip())
cards={}
def walk(rs):
    for r in rs or []:
        if isinstance(r,dict):
            walk(r['repos']) if 'repos' in r else cards.__setitem__(r['name'].lower(), r.get('local_installed'))
walk(d.get('hot_now')); walk(d.get('categories'))
print('octocat/hello-world installed:', cards.get('octocat/hello-world'))
"
```
Expected: `True`。(Hello-World 若不在卡片集,改用 `mattpocock/skills` 卸载重装流程验证,或临时用 `gh api` 断言 `/api/local` 的 skills 含 Hello-World。)

- [ ] **Step 3: 更新 → 卸载 → 徽标消失 + 四平台干净**

```bash
curl -s --noproxy '*' -X POST http://127.0.0.1:8765/api/update -H 'Content-Type: application/json' \
  -d '{"name":"octocat/Hello-World","url":"https://github.com/octocat/Hello-World","targets":["claude"]}'
# 断言 "up_to_date" 或 "updated"
curl -s --noproxy '*' -X POST http://127.0.0.1:8765/api/uninstall -H 'Content-Type: application/json' \
  -d '{"name":"octocat/Hello-World"}'
ls ~/.claude/skills/Hello-World 2>&1   # No such file
```
Expected: 徽标 False、链接全清、sidecar 无 Hello-World 残留(`grep -c Hello-World ~/.cache/lodestone/origins.json` 为 0 或条目已删)。

- [ ] **Step 4: 删除审计脚本 + 最终三套测试 + commit(如有代码变更)**

```bash
rm audit_install_state.py
python3 -m tests.test_radar && python3 -m tests.test_install_detection && python3 -m tests.test_crawl_sources
```
