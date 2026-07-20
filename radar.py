#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + categorized dashboard.

Commands:
  radar.py crawl   - fetch trending AI repos from GitHub, save to data/
  radar.py render  - regenerate out/index.html from latest data
  radar.py serve   - serve dashboard on http://localhost:PORT
  radar.py today   - print today's top picks in terminal
  radar.py all     - crawl + render + open browser

Reuses `gh` CLI for GitHub auth (avoids token management).
Ponytail: minimum code, stdlib only, single static HTML output.
"""
import json, subprocess, sys, os, re, datetime, time, html, webbrowser, http.server, socketserver, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "out"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# ponytail: cache for cloned skill repos; sidecar stores install origin (URL survives latest.json roll)
SKILLS_CACHE = Path.home() / ".cache" / "lodestone" / "skills"
SKILL_ORIGINS = Path.home() / ".cache" / "lodestone" / "origins.json"

# ponytail: topic-based queries — keep simple, GitHub topics are user-curated and accurate
CATEGORIES = [
    {
        "id": "agent",
        "name": "AI Agent & Skills",
        "desc": "自主代理、Multi-agent、Skills、Claude Skills、MCP",
        "queries": [
            "topic:ai-agent stars:>500",
            "topic:claude-code stars:>300",
            "topic:mcp-server stars:>200",
            "agent in:name,description stars:>1000",
        ],
    },
    {
        "id": "memory",
        "name": "RAG / Memory / Vector",
        "desc": "向量库、记忆系统、检索增强生成、Embedding",
        "queries": [
            "topic:rag stars:>500",
            "topic:vector-database stars:>500",
            "topic:llm-memory stars:>100",
            "agent-memory in:name,description stars:>200",
        ],
    },
    {
        "id": "llm",
        "name": "LLM Interface & Chat",
        "desc": "大模型接口、Chatbot、Prompt 工程、Anthropic / OpenAI SDK",
        "queries": [
            "topic:llm stars:>1000",
            "topic:chatbot stars:>1000",
            "topic:prompt-engineering stars:>300",
            "claude-api in:name,description stars:>500",
        ],
    },
    {
        "id": "devtool",
        "name": "Code Generation & Dev Tools",
        "desc": "Copilot、Code Agent、开发者增强工具、Cursor 替代",
        "queries": [
            "topic:copilot stars:>500",
            "topic:ai-coding stars:>300",
            "code-agent in:name,description stars:>500",
            "developer-tools topic:ai stars:>300",
        ],
    },
    {
        "id": "workflow",
        "name": "Workflow & Orchestration",
        "desc": "LangGraph、DAG、Pipeline、Agent 编排",
        "queries": [
            "topic:langgraph stars:>200",
            "topic:workflow-orchestration stars:>500",
            "langchain in:name stars:>1000",
            "agent-orchestration in:name,description stars:>200",
        ],
    },
    {
        "id": "multimodal",
        "name": "Multimodal (Vision / Audio / Video)",
        "desc": "图像理解、语音、视频生成、多模态应用",
        "queries": [
            "topic:multimodal stars:>500",
            "topic:text-to-video stars:>500",
            "topic:vision-language-model stars:>300",
        ],
    },
    {
        "id": "finetune",
        "name": "Fine-tuning & Training",
        "desc": "模型微调、训练框架、LoRA、PEFT",
        "queries": [
            "topic:fine-tuning stars:>500",
            "topic:llama-factory stars:>200",
            "lora in:name,description stars:>1000",
            "topic:peft stars:>300",
        ],
    },
    {
        "id": "eval",
        "name": "Eval & Benchmark",
        "desc": "模型评估、测试基准、LLM-as-Judge、可观测性",
        "queries": [
            "topic:llm-evaluation stars:>300",
            "topic:benchmark stars:>500",
            "llm-eval in:name,description stars:>200",
        ],
    },
    {
        "id": "awesome",
        "name": "Awesome Lists & 资源合集",
        "desc": "精选列表、教程、Awesome-* 仓库 — 发现新方向的入口",
        "queries": [
            "awesome-ai in:name stars:>500",
            "awesome-llm in:name stars:>500",
            "awesome-claude in:name stars:>200",
        ],
    },
]

# ponytail: 5k+ pass — broad queries to catch mainstream AI tools not in category queries
TOP_5K_QUERIES = [
    "stars:>5000 topic:ai",
    "stars:>5000 topic:llm",
    "stars:>5000 topic:agent",
    "stars:>5000 topic:rag OR topic:vector-database",
    "stars:>5000 topic:claude OR topic:claude-code OR topic:mcp-server",
]
TOP_5K_LIMIT = 200

# ponytail: AI topic whitelist — used to drop non-AI high-star repos (e.g. awesome-go) from top_5k list
AI_TOPIC_WHITELIST = frozenset({
    "ai", "llm", "gpt", "agent", "agents", "claude", "openai", "anthropic",
    "rag", "embedding", "embeddings", "vector", "mcp", "mcp-server",
    "chatbot", "transformer", "transformers", "langchain", "huggingface",
    "hugging-face", "prompt", "prompts", "prompt-engineering", "copilot",
    "stable-diffusion", "text-to-image", "text-to-video", "multimodal",
    "voice", "speech", "whisper", "computer-vision", "cv",
    "machine-learning", "deep-learning", "neural-network", "pytorch",
    "tensorflow", "diffusion", "fine-tuning", "lora", "peft",
    "llama", "llama-index", "langgraph", "autogen", "crewai",
})

# ponytail: static dictionaries, cheap & deterministic — LLM-based per-repo intro is overkill for a daily radar
PLAIN_BY_CAT = {
    "agent":    "让 AI 像人一样自主决策、调用工具完成复杂任务",
    "memory":   "给 AI 装上'记忆'和'知识库'，回答更准确、越用越懂你",
    "llm":      "调用大模型（GPT/Claude 等）的开发工具包",
    "devtool":  "程序员的 AI 提效工具，写代码、做项目更快",
    "workflow": "把多个 AI 步骤编排成自动化流水线",
    "multimodal": "AI 处理图片、音频、视频等多种感官信息",
    "finetune": "用自家数据训练/微调大模型，让 AI 更懂你的业务",
    "eval":     "评估 AI 表现和质量、跑基准测试",
    "awesome":  "精心整理的 AI 资源列表，发现新方向的入口",
}

# ponytail: topic → plain Chinese phrase; first match wins, max 3 phrases combined
PLAIN_BY_TOPIC = {
    "claude-code":          "为 Claude 编程工具打造的扩展生态",
    "mcp":                  "实现 MCP 协议 — AI 连接外部数据和工具的标准",
    "mcp-server":           "MCP 服务器实现，让 AI 能调用你的本地工具",
    "agent":                "AI 代理框架，自主规划与执行",
    "autonomous-agent":     "自主 AI 代理，减少人工干预",
    "multi-agent":          "多 AI 协同工作，互相配合完成任务",
    "skills":               "AI 技能库 — 把好用的工作流打包成可复用技能",
    "subagent-driven-development": "子代理驱动的开发方法论",
    "sdlc":                 "完整软件开发生命周期方法论",
    "agent-skills":         "AI 代理技能合集",
    "rag":                  "支持 RAG（检索增强生成）— 让 AI 回答有据可查",
    "vector-database":      "向量数据库 — 文字/图片变数字，AI 检索超快",
    "memory":               "为 AI 添加长期记忆能力",
    "copilot":              "AI 结对编程伙伴，帮你写代码、找 Bug",
    "ai-coding":            "AI 辅助编程工具",
    "code-generation":      "根据描述自动生成代码",
    "langgraph":            "LangGraph — 用图（Graph）方式编排 AI 流程",
    "langchain":            "LangChain 生态工具",
    "prompt-engineering":   "提示词工程技巧合集 — 跟 AI 说话的'咒语'",
    "fine-tuning":          "模型微调框架",
    "lora":                 "LoRA 微调 — 用小成本定制大模型",
    "peft":                 "参数高效微调，省显存省算力",
    "vision-language-model":"视觉语言模型，能看图说话",
    "text-to-video":        "文字生成视频的 AI 模型",
    "multimodal":           "多模态 AI，处理图像+文本+音频",
    "llm-evaluation":       "大模型评测工具",
    "benchmark":            "AI 性能基准测试",
    "awesome-list":         "精心整理的资源清单",
}

CAT_ICONS = {  # Lucide icon names per category
    "agent": "bot", "memory": "brain", "llm": "message-square-text",
    "devtool": "code-2", "workflow": "workflow", "multimodal": "image",
    "finetune": "dumbbell", "eval": "bar-chart-3", "awesome": "bookmark",
}

TRANSLATE_CACHE = DATA / "zh_cache.json"

# ponytail: SKILL.md frontmatter description extractor — stops at next key, closing ---, or EOF
FRONTMATTER_DESC = re.compile(r"^description:\s*(.+?)(?=\n[a-z\-]+:|\n---|\Z)", re.MULTILINE | re.DOTALL)


def translate_text(text, target="zh-CN"):
    """Google Translate free endpoint via urllib — zero deps. Returns '' on failure."""
    if not text or not text.strip():
        return ""
    try:
        params = urllib.parse.urlencode({
            "client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text[:500],
        })
        req = urllib.request.Request(
            f"https://translate.googleapis.com/translate_a/single?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception:
        return ""


def translate_batch(pairs):
    """Translate (key, text) pairs in parallel, with persistent cache. Returns {key: translated}."""
    cache = json.loads(TRANSLATE_CACHE.read_text()) if TRANSLATE_CACHE.exists() else {}
    out = {}
    todo = {}
    for k, v in pairs:
        if not v or not v.strip():
            out[k] = ""
        elif k in cache:
            out[k] = cache[k]
        else:
            todo[k] = v
    if todo:
        print(f"  · translating {len(todo)} descriptions…", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(translate_text, v): k for k, v in todo.items()}
            for fut in as_completed(futs):
                out[futs[fut]] = fut.result() or ""
        # ponytail: don't cache empty results — a failed translation shouldn't be permanent
        cache.update({k: out[k] for k in todo if out[k]})
        TRANSLATE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return out


def plain_for_repo(repo, cat_id):
    """DEPRECATED — kept for back-compat. Use facts_for_repo() + desc_zh instead."""
    return facts_for_repo(repo)


def facts_for_repo(repo):
    """Evidence-based intro: ONLY verifiable facts from GitHub data.
    Format: '📚 {lang} · 🏷 {top topics} · ⭐ {stars}'.
    No invented phrases — every claim is sourced from the repo's actual metadata."""
    parts = []
    if repo.get("lang") and repo["lang"] != "—":
        parts.append(f"📚 {repo['lang']}")
    topics = (repo.get("topics") or [])[:4]
    if topics:
        parts.append("🏷 " + " · ".join(topics))
    parts.append(f"⭐ {repo['stars']:,}")
    return " · ".join(parts)


# SKILLS_CACHE / SKILL_ORIGINS defined at top of file (lines 27-28)


def detect_local_skills():
    """Scan all forms of installed Claude/Codex capabilities.
    Returns: {
      "skills":   {name: {claude, codex, url, desc_zh, desc_en, topics, stars, source}},
      "commands": {name: {claude}},
      "agents":   {name: {claude}},
      "plugins":  [{name, marketplace, version, install_path}],
    }
    Source priority: latest.json match → sidecar origin → SKILL.md frontmatter → none
    """
    out = {"skills": {}, "commands": {}, "agents": {}, "plugins": []}

    # ponytail: build lookup from latest.json — match by repo segment (last path component)
    by_repo = {}  # repo segment → repo data
    latest = DATA / "latest.json"
    if latest.exists():
        try:
            snap = json.loads(latest.read_text())
            for r in (snap.get("hot_now") or []):
                by_repo[r["name"].split("/")[-1]] = r
            for cat in (snap.get("categories") or []):
                for r in cat.get("repos") or []:
                    by_repo.setdefault(r["name"].split("/")[-1], r)
        except (OSError, ValueError):
            pass

    # ponytail: build lookup from sidecar — covers installs not in latest.json
    by_origin = {}
    if SKILL_ORIGINS.exists():
        try:
            data = json.loads(SKILL_ORIGINS.read_text())
            for repo_name, info in (data.get("skills") or {}).items():
                by_origin[repo_name] = info
        except (OSError, ValueError):
            pass

    # skills dirs
    for label, d in [("claude", Path.home() / ".claude" / "skills"),
                     ("codex", Path.home() / ".codex" / "skills")]:
        if not d.exists():
            continue
        try:
            for entry in d.iterdir():
                if entry.name.startswith("."):
                    continue
                if not (entry.is_dir() or entry.is_symlink()):
                    continue
                meta = out["skills"].setdefault(entry.name, {
                    "claude": False, "codex": False,
                    "url": None, "desc_zh": None, "desc_en": None,
                    "topics": [], "stars": 0, "source": "none",
                })
                meta[label] = True
        except OSError:
            pass

    # ponytail: enrich each skill with desc/url from 3 sources (priority: cache > origin > skillmd)
    for name, meta in out["skills"].items():
        if name in by_repo:
            r = by_repo[name]
            meta.update({
                "url": r.get("url"),
                "desc_zh": r.get("desc_zh") or r.get("desc"),
                "desc_en": r.get("desc"),
                "topics": r.get("topics") or [],
                "stars": r.get("stars") or 0,
                "source": "cache",
            })
        elif name in by_origin:
            o = by_origin[name]
            meta["url"] = o.get("url")
            meta["source"] = "origin"
        else:
            for skills_root in [Path.home() / ".claude" / "skills",
                                Path.home() / ".codex" / "skills"]:
                skill_md = skills_root / name / "SKILL.md"
                if skill_md.exists():
                    try:
                        text = skill_md.read_text()
                        m = FRONTMATTER_DESC.search(text)
                        if m:
                            meta["desc_en"] = m.group(1).strip().strip('"').strip("'")
                            meta["source"] = "skillmd"
                    except OSError:
                        pass
                    break

    # ponytail: any skill with desc_en but no desc_zh → translate via existing cache/translate_batch
    to_translate = [(name, meta["desc_en"]) for name, meta in out["skills"].items()
                    if meta.get("desc_en") and not meta.get("desc_zh")]
    if to_translate:
        zh_map = translate_batch(to_translate)
        for name, zh in zh_map.items():
            if zh and out["skills"][name].get("desc_zh") in (None, ""):
                out["skills"][name]["desc_zh"] = zh

    # ponytail: Claude slash commands are *.md files (not subdirs) in commands/
    cmd_dir = Path.home() / ".claude" / "commands"
    if cmd_dir.exists():
        try:
            for f in cmd_dir.iterdir():
                if f.suffix == ".md" and not f.name.startswith("."):
                    out["commands"][f.stem] = {"claude": True}
        except OSError:
            pass

    # ponytail: Claude subagent definitions are *.md files in agents/
    agent_dir = Path.home() / ".claude" / "agents"
    if agent_dir.exists():
        try:
            for f in agent_dir.iterdir():
                if f.suffix == ".md" and not f.name.startswith("."):
                    out["agents"][f.stem] = {"claude": True}
        except OSError:
            pass

    # ponytail: plugins from installed_plugins.json (v2 schema)
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        try:
            data = json.loads(plugins_file.read_text())
            for plugin_key, installs in (data.get("plugins") or {}).items():
                if "@" in plugin_key:
                    name, marketplace = plugin_key.split("@", 1)
                else:
                    name, marketplace = plugin_key, ""
                inst = max(installs, key=lambda i: i.get("installedAt", "")) if installs else {}
                out["plugins"].append({
                    "name": name,
                    "marketplace": marketplace,
                    "version": inst.get("version", ""),
                    "install_path": inst.get("installPath", ""),
                })
        except (OSError, ValueError, TypeError):
            pass

    return out


def install_skill_from_github(name, url):
    """Clone GitHub repo to SKILLS_CACHE/<repo>, symlink to both skills dirs.
    Validates name as 'owner/repo'. Writes/updates sidecar at SKILL_ORIGINS.
    Idempotent. `url` is optional — if empty, derived from name."""
    if not name or not all(c.isalnum() or c in "-_." for c in name.replace("/", "")) or ".." in name:
        raise ValueError(f"invalid skill name: {name!r}")
    if "/" not in name:
        raise ValueError(f"skill name must be 'owner/repo': {name!r}")
    owner, repo = name.split("/", 1)
    if not all(c.isalnum() or c in "-_." for c in owner) or not all(c.isalnum() or c in "-_." for c in repo):
        raise ValueError(f"invalid owner/repo: {name!r}")
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")
    if not url:
        url = f"https://github.com/{name}"

    target = SKILLS_CACHE / repo
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(target)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()[:200]}")

    for skills_root in [Path.home() / ".claude" / "skills",
                        Path.home() / ".codex" / "skills"]:
        skills_root.mkdir(parents=True, exist_ok=True)
        link = skills_root / repo
        if link.is_symlink() or link.exists():
            continue
        link.symlink_to(target)

    # ponytail: write sidecar so origin URL survives latest.json roll; idempotent update
    try:
        SKILL_ORIGINS.parent.mkdir(parents=True, exist_ok=True)
        origins = {}
        if SKILL_ORIGINS.exists():
            try:
                origins = json.loads(SKILL_ORIGINS.read_text())
            except (OSError, ValueError):
                origins = {}  # ponytail: corrupted sidecar — start fresh, don't break install
        origins.setdefault("skills", {})[repo] = {
            "owner": owner,
            "repo": repo,
            "url": url,
            "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
    except OSError as e:
        sys.stderr.write(f"  [warn] sidecar write failed: {e}\n")

    return str(target)


# ponytail: well-known AI/dev CLI tools worth surfacing to the user
KNOWN_CLIS = [
    "rtk", "gh", "docker", "kubectl", "helm", "terraform",
    "jq", "rg", "fd", "fzf", "tmux", "git", "curl", "ffmpeg",
    "aws", "gcloud", "az", "supabase", "vercel", "wrangler",
]


def detect_cli_tools():
    """Run `which` for KNOWN_CLIS, return {name: {path, version}}. Cheap — ~50ms total."""
    out = {}
    for tool in KNOWN_CLIS:
        try:
            r = subprocess.run(["which", tool], capture_output=True, text=True, timeout=2)
            if r.returncode != 0:
                continue
            path = r.stdout.strip()
            version = ""
            # ponytail: try common version flags, take first line of first successful output
            for flag in ["--version", "-version", "-V", "version"]:
                try:
                    vr = subprocess.run([path, flag], capture_output=True, text=True, timeout=2)
                    candidate = (vr.stdout or vr.stderr).strip().split("\n")[0]
                    if vr.returncode == 0 and candidate:
                        version = candidate[:60]
                        break
                except (OSError, subprocess.TimeoutExpired):
                    continue
            out[tool] = {"path": path, "version": version}
        except (OSError, subprocess.TimeoutExpired):
            continue
    return out


def install_cli_wrapper(name, command):
    """Create ~/.claude/commands/<name>.md slash command wrapping `command`.
    Validates name (no traversal). `command` is the literal shell command to invoke."""
    if not name or not all(c.isalnum() or c in "-_." for c in name) or ".." in name:
        raise ValueError(f"invalid command name: {name!r}")
    if not command or len(command) > 200:
        raise ValueError("command must be 1-200 chars")

    target = Path.home() / ".claude" / "commands" / f"{name}.md"
    if target.exists():
        return str(target)  # idempotent

    target.parent.mkdir(parents=True, exist_ok=True)
    body = f"""---
description: Run `{command}` and stream output
---

# /{name}

Execute `{command}` and explain the result.

!`{command}`
"""
    target.write_text(body, encoding="utf-8")
    return str(target)


def gh_search(q, per_page=20):
    """Use gh CLI to search repos. Returns list of normalized repo dicts."""
    cmd = [
        "gh", "api", "-X", "GET", "search/repositories",
        "-f", f"q={q}",
        "-f", "sort=stars",
        "-f", "order=desc",
        "-f", f"per_page={per_page}",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  ! gh api failed for q={q!r}: {r.stderr.strip()[:120]}", file=sys.stderr)
            return []
        data = json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        print(f"  ! gh api timeout (>60s) for q={q!r}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  ! gh search error: {e}", file=sys.stderr)
        return []

    out = []
    for item in data.get("items", []):
        out.append({
            "name": item["full_name"],
            "desc": (item.get("description") or "").strip(),
            "url": item["html_url"],
            "stars": item.get("stargazers_count", 0),
            "forks": item.get("forks_count", 0),
            "lang": item.get("language") or "—",
            "topics": item.get("topics", []) or [],
            "updated": item.get("updated_at", "")[:10],
            "pushed": item.get("pushed_at", "")[:10],
            "score": round(item.get("score", 0), 2),
        })
    return out


def crawl():
    """Fetch all categories, dedupe, save."""
    today = datetime.date.today().isoformat()
    print(f"[crawl] {today} — {len(CATEGORIES)} categories")
    all_repos = {}  # name -> {repo, categories:[]}
    cat_results = []

    for cat in CATEGORIES:
        seen = set()
        repos = []
        for q in cat["queries"]:
            for r in gh_search(q):
                if r["name"] in seen:
                    continue
                seen.add(r["name"])
                repos.append(r)
        # sort by stars desc
        repos.sort(key=lambda x: x["stars"], reverse=True)
        repos = repos[:30]
        cat_results.append({
            "id": cat["id"],
            "name": cat["name"],
            "desc": cat["desc"],
            "count": len(repos),
            "repos": repos,
        })
        for r in repos:
            all_repos.setdefault(r["name"], {**r, "categories": []})
            if cat["id"] not in all_repos[r["name"]]["categories"]:
                all_repos[r["name"]]["categories"].append(cat["id"])
        print(f"  ✓ {cat['name']}: {len(repos)} repos")

    # Sort overall by stars
    hot_now = sorted(all_repos.values(), key=lambda x: x["stars"], reverse=True)[:40]

    # ponytail: 5k+ pass — catch mainstream AI tools not matched by category queries
    print(f"[crawl] 5k+ pass ({len(TOP_5K_QUERIES)} queries, sleep 2s between)...")
    top_5k_repos = {}
    for q in TOP_5K_QUERIES:
        time.sleep(2)  # rate limit: 30 req/min
        try:
            for r in gh_search(q, per_page=100):
                # ponytail: filter to AI-relevant — drop awesome-go etc. that have 5k+ stars
                topics = [t.lower() for t in r.get("topics", [])]
                if not any(t in AI_TOPIC_WHITELIST for t in topics):
                    continue
                top_5k_repos.setdefault(r["name"], r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}")

    top_5k_sorted = sorted(top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True)[:TOP_5K_LIMIT]
    print(f"  ✓ 5k+ pass: {len(top_5k_sorted)} repos after AI filter")

    # Detect local skills — runs every crawl, cheap (just iterates 2 dirs)
    local = detect_local_skills()
    print(f"[crawl] local skills detected: {len(local)}")

    # ponytail: translate 5k+ repo descriptions (reuses cache, so most cost = 0)
    pairs5k = [(f"{r['name']}::desc", r.get("desc", "")) for r in top_5k_sorted]
    zh5k = translate_batch(pairs5k)
    for r in top_5k_sorted:
        r["desc_zh"] = zh5k.get(f"{r['name']}::desc", "")
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = r["name"].split("/")[-1] in local

    snapshot = {
        "date": today,
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_unique": len(all_repos),
        "categories": cat_results,
        "hot_now": [{
            "name": r["name"], "desc": r["desc"], "url": r["url"],
            "stars": r["stars"], "lang": r["lang"], "topics": r["topics"],
            "categories": r["categories"],
        } for r in hot_now],
        "top_5k_plus": {
            "count": len(top_5k_sorted),
            "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "repos": [{
                "name": r["name"], "desc": r["desc"], "url": r["url"],
                "stars": r["stars"], "lang": r["lang"], "topics": r["topics"],
                "pushed": r.get("pushed", ""),
                "desc_zh": r.get("desc_zh", ""),
                "facts": r.get("facts", ""),
                "local_installed": r.get("local_installed", False),
            } for r in top_5k_sorted],
        },
        "local_skills": {
            "installed": local,
            "installed_count": len(local),
            "detected_at": datetime.datetime.now().isoformat(timespec="seconds"),
        },
    }

    # ponytail: translate once, cache forever — descriptions don't change day-to-day
    print("[crawl] translating to Chinese…")
    pairs = []
    for cat in cat_results:
        for r in cat["repos"]:
            pairs.append((f"{r['name']}::desc", r["desc"]))
    zh = translate_batch(pairs)

    # Attach Chinese fields — facts only, no invented phrases
    for cat in cat_results:
        for r in cat["repos"]:
            r["desc_zh"] = zh.get(f"{r['name']}::desc", "")
            r["facts"] = facts_for_repo(r)
            r["local_installed"] = r["name"].split("/")[-1] in local
    for r in snapshot["hot_now"]:
        r["desc_zh"] = zh.get(f"{r['name']}::desc", "")
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = r["name"].split("/")[-1] in local
    out_path = DATA / f"{today}.json"
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    latest = DATA / "latest.json"
    latest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"[crawl] saved → {out_path.relative_to(ROOT)} + latest.json ({snapshot['total_unique']} unique)")
    return snapshot



def render():
    """Generate out/index.html from latest data — cool dark, evidence-based cards, local skill install."""
    latest = DATA / "latest.json"
    if not latest.exists():
        print("[render] no data yet — run `radar.py crawl` first", file=sys.stderr)
        sys.exit(1)
    snap = json.loads(latest.read_text())

    local = snap.get("local_skills", {}).get("installed", {})

    # ----- Build "Recommended to install" — top trending agent/skills repos not yet installed locally -----
    recommend_pool = []
    seen_names = set()
    # pull from agent + memory + devtool categories, prioritize by stars
    for cat in snap["categories"]:
        if cat["id"] not in ("agent", "memory", "devtool", "llm"):
            continue
        for r in cat["repos"]:
            short = r["name"].split("/")[-1]
            if short in local or short in seen_names:
                continue
            # heuristic: must look "skill-ish" — has topics like skill/mcp/agent, OR has SKILL.md
            topic_set = {t.lower() for t in r.get("topics", [])}
            skill_signal = bool(topic_set & {"skill", "skills", "mcp", "mcp-server", "claude-code", "claude", "agent"})
            if not skill_signal:
                continue
            seen_names.add(short)
            recommend_pool.append({
                "name": short, "full": r["name"], "url": r["url"],
                "stars": r["stars"], "lang": r["lang"],
                "desc_zh": (r.get("desc_zh") or r.get("desc") or "")[:120],
                "topics": (r.get("topics") or [])[:4],
            })
    recommend_pool.sort(key=lambda x: x["stars"], reverse=True)
    recommend_cards = recommend_pool[:8]

    # ----- Local skills badges -----
    installed_badges = []
    for name, where in sorted(local.items()):
        in_claude = where.get("claude", False)
        in_codex = where.get("codex", False)
        platforms = []
        if in_claude: platforms.append("Claude")
        if in_codex: platforms.append("Codex")
        installed_badges.append({"name": name, "platforms": " · ".join(platforms)})

    # ----- Hot Now — 4-col grid, evidence-based cards -----
    hot_cards = []
    for i, r in enumerate(snap["hot_now"][:24], 1):
        facts = r.get("facts", "")
        desc_zh = (r.get("desc_zh") or r.get("desc") or "").strip()
        local_mark = " · <span style='color:#22c55e'>✓ 本机已装</span>" if r.get("local_installed") else ""
        payload = json.dumps(r, ensure_ascii=False)
        hot_cards.append(f'''
        <div class="repo-card hot" data-payload='{html.escape(payload, quote=True)}' onclick="showRepo(this)">
          <div class="flex items-center justify-between mb-2">
            <span class="text-2xl font-black text-purple-300">#{i}</span>
            <span class="text-amber-400 font-mono text-sm">⭐ {r["stars"]:,}</span>
          </div>
          <h3 class="font-bold text-base leading-tight mb-2 truncate">{html.escape(r["name"])}</h3>
          <div class="text-xs text-cyan-300/80 font-mono leading-relaxed mb-2">{html.escape(facts)}{local_mark}</div>
          <p class="text-xs text-white/60 leading-relaxed" style="display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;">{html.escape(desc_zh[:160])}</p>
        </div>''')

    # ----- Category sections — 3-col evidence-based cards -----
    sections_html = []
    for cat in snap["categories"]:
        icon = CAT_ICONS.get(cat["id"], "star")
        cat_plain = PLAIN_BY_CAT.get(cat["id"], cat["desc"])
        cards = []
        for r in cat["repos"][:12]:
            facts = r.get("facts", "")
            desc_zh = (r.get("desc_zh") or r.get("desc") or "").strip()
            tags = "".join(
                f'<span class="tag-chip">{html.escape(t)}</span>'
                for t in r["topics"][:3]
            )
            local_dot = '<span class="local-dot" title="本机已安装">●</span>' if r.get("local_installed") else ""
            payload = json.dumps({**r, "cat_id": cat["id"], "cat_name": cat["name"]}, ensure_ascii=False)
            cards.append(f'''
            <div class="repo-card" data-payload='{html.escape(payload, quote=True)}' onclick="showRepo(this)">
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="font-bold text-base leading-tight flex items-center gap-1.5">{local_dot}{html.escape(r["name"])}</h3>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {r["stars"]:,}</span>
              </div>
              <div class="text-xs text-cyan-300/80 font-mono leading-relaxed mb-3">{html.escape(facts)}</div>
              <p class="text-sm text-white/70 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;">{html.escape(desc_zh[:200])}</p>
              <div class="flex items-center justify-between flex-wrap gap-1">
                <div class="flex gap-1 flex-wrap">{tags}</div>
                <span class="text-xs text-white/40 font-mono">{html.escape(r["lang"])}</span>
              </div>
            </div>''')
        sections_html.append(f'''
        <section id="cat-{cat["id"]}" class="scroll-mt-24 mb-20">
          <div class="flex items-end justify-between mb-6 flex-wrap gap-3">
            <div>
              <div class="flex items-center gap-2 mb-2">
                <i data-lucide="{icon}" class="w-7 h-7 text-purple-300"></i>
                <h2 class="text-2xl md:text-3xl font-bold tracking-tight">{html.escape(cat["name"])}</h2>
              </div>
              <p class="text-white/60 max-w-2xl mb-1">{html.escape(cat["desc"])}</p>
              <p class="text-purple-300/70 text-sm italic">👉 {html.escape(cat_plain)}</p>
            </div>
            <span class="font-mono text-sm text-white/40">{cat["count"]} 个项目</span>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {''.join(cards)}
          </div>
        </section>''')

    # ----- Local Skills section cards -----
    rec_html = []
    for r in recommend_cards:
        rec_html.append(f'''
        <div class="install-card">
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="min-w-0 flex-1">
              <h3 class="font-bold text-sm truncate">{html.escape(r["full"])}</h3>
              <div class="text-xs text-cyan-300/80 font-mono mt-0.5">⭐ {r["stars"]:,} · {html.escape(r["lang"])}</div>
            </div>
            <button class="btn-install" onclick="installSkill(this, '{html.escape(r["name"], quote=True)}', '{html.escape(r["url"], quote=True)}')">
              ⬇ 安装
            </button>
          </div>
          <p class="text-xs text-white/60 leading-relaxed" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">{html.escape(r["desc_zh"])}</p>
          <div class="flex gap-1 flex-wrap mt-2">
            {''.join(f'<span class="tag-chip">{html.escape(t)}</span>' for t in r["topics"])}
          </div>
        </div>''')

    installed_html = []
    for b in installed_badges:
        installed_html.append(f'''
        <div class="installed-badge" title="平台：{html.escape(b["platforms"])}">
          <span class="text-green-400">●</span>
          <span class="font-mono text-xs">{html.escape(b["name"])}</span>
        </div>''')

    fetched_time = snap["fetched_at"][:16].replace("T", " ")
    nav_tabs = ['<a href="#local" class="nav-tab" data-target="local"><i data-lucide="package" class="w-4 h-4"></i>本机 Skills</a>']
    nav_tabs.append('<a href="#hot" class="nav-tab" data-target="hot"><i data-lucide="flame" class="w-4 h-4"></i>今日最热</a>')
    nav_tabs += [
        f'<a href="#cat-{c["id"]}" class="nav-tab" data-target="cat-{c["id"]}">'
        f'<i data-lucide="{CAT_ICONS.get(c["id"], "star")}" class="w-4 h-4"></i>'
        f'{html.escape(c["name"].split("(")[0].split("&")[0].strip())}</a>'
        for c in snap["categories"]
    ]

    html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-theme="radar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ Lodestone · 每日 GitHub AI 热门情报站</title>
<link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
[data-theme="radar"] {{
  --p: 262 83% 65%; --s: 189 94% 55%; --a: 262 83% 65%;
  --n: 240 12% 8%; --b1: 240 14% 6%; --b2: 240 14% 9%;
  --b3: 240 14% 14%; --bc: 220 13% 92%;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}

/* ponytail: cool dark — animated aurora mesh + grid overlay */
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: hsl(var(--bc));
  min-height: 100vh;
  position: relative;
  background-color: #050509;
  background-image:
    radial-gradient(ellipse 60% 50% at 12% 8%, rgba(124, 58, 237, 0.35) 0%, transparent 55%),
    radial-gradient(ellipse 50% 40% at 88% 12%, rgba(6, 182, 212, 0.25) 0%, transparent 55%),
    radial-gradient(ellipse 55% 45% at 50% 95%, rgba(236, 72, 153, 0.18) 0%, transparent 60%);
  background-attachment: fixed;
  animation: aurora 25s ease-in-out infinite;
}}
@keyframes aurora {{
  0%, 100% {{ background-position: 0% 0%, 100% 0%, 50% 100%; }}
  33% {{ background-position: 50% 30%, 0% 60%, 100% 50%; }}
  66% {{ background-position: 100% 0%, 50% 100%, 0% 30%; }}
}}
/* grid overlay — fades at edges */
body::before {{
  content: '';
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 56px 56px;
  pointer-events: none;
  z-index: 0;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 30%, black 0%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 30%, black 0%, transparent 75%);
}}
.font-mono {{ font-family: 'JetBrains Mono', ui-monospace, monospace; }}

/* Hero */
.hero {{
  position: relative; z-index: 1;
  padding: 5rem 1.5rem 3rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
}}
.hero h1 {{
  font-size: clamp(2.8rem, 7vw, 5rem);
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.0;
  background: linear-gradient(135deg, #c4b5fd 0%, #67e8f9 50%, #f0abfc 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gradient 8s ease infinite;
  margin: 0;
}}
@keyframes gradient {{ 0%,100% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} }}
.hero .tagline {{ color: rgba(255,255,255,0.65); margin-top: 1.25rem; font-size: 1.15rem; max-width: 38rem; line-height: 1.6; }}
.stat-pill {{
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08);
  padding: 0.6rem 1.1rem;
  border-radius: 999px;
  font-size: 0.9rem;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}}
.stat-pill b {{ color: #c4b5fd; font-family: 'JetBrains Mono', monospace; }}

/* Sticky nav */
.nav-tabs {{
  position: sticky; top: 0; z-index: 30;
  background: rgba(5, 5, 9, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  padding: 0.75rem 0;
  overflow-x: auto;
  scrollbar-width: none;
}}
.nav-tabs::-webkit-scrollbar {{ display: none; }}
.nav-tab {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 999px;
  font-size: 0.875rem;
  color: rgba(255,255,255,0.6);
  text-decoration: none;
  white-space: nowrap;
  transition: all 0.2s;
  border: 1px solid transparent;
}}
.nav-tab:hover {{ background: rgba(255,255,255,0.05); color: white; }}
.nav-tab.active {{
  background: rgba(124, 58, 237, 0.15);
  color: #c4b5fd;
  border-color: rgba(124, 58, 237, 0.4);
}}

/* Repo cards */
.repo-card {{
  position: relative; z-index: 1;
  background: rgba(15, 13, 25, 0.55);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.9rem;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}
.repo-card.hot {{ padding: 1.1rem; }}
.repo-card:hover {{
  transform: translateY(-2px);
  border-color: rgba(124, 58, 237, 0.45);
  background: rgba(20, 18, 32, 0.7);
  box-shadow: 0 10px 40px rgba(124, 58, 237, 0.15);
}}
.local-dot {{ color: #22c55e; font-size: 0.7rem; }}

/* Install section */
.section-title {{
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.18em;
  color: rgba(255,255,255,0.45); margin-bottom: 0.5rem; font-weight: 600;
}}
.install-card {{
  background: rgba(15, 13, 25, 0.55);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.85rem;
  padding: 1rem;
  transition: all 0.2s;
}}
.install-card:hover {{ border-color: rgba(124, 58, 237, 0.4); }}
.btn-install {{
  background: linear-gradient(135deg, #7c3aed, #06b6d4);
  color: white;
  border: none;
  padding: 0.45rem 0.9rem;
  border-radius: 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}}
.btn-install:hover {{ transform: scale(1.05); box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4); }}
.btn-install:disabled {{ opacity: 0.6; cursor: not-allowed; }}
.btn-install.done {{ background: #16a34a; }}
.btn-install.error {{ background: #dc2626; }}

.installed-badge {{
  display: inline-flex; align-items: center; gap: 0.4rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  color: rgba(255,255,255,0.85);
  transition: all 0.2s;
}}
.installed-badge:hover {{ background: rgba(34, 197, 94, 0.15); border-color: rgba(34, 197, 94, 0.5); }}

.tag-chip {{
  display: inline-block;
  background: rgba(255,255,255,0.06);
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  color: rgba(255,255,255,0.65);
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
}}

/* Modal */
dialog.modal {{ background: transparent; }}
dialog.modal::backdrop {{
  background: rgba(5, 5, 9, 0.75);
  backdrop-filter: blur(8px);
}}
.modal-box {{
  background: #15131f;
  border: 1px solid rgba(255,255,255,0.1);
  max-width: 640px;
  border-radius: 1.25rem;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.6);
}}

.search-wrap {{ position: relative; max-width: 38rem; margin-top: 2rem; }}
.search-wrap input {{
  width: 100%;
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.1);
  color: white;
  padding: 0.9rem 1rem 0.9rem 3rem;
  border-radius: 999px;
  font-size: 1rem;
  outline: none;
  transition: all 0.2s;
}}
.search-wrap input:focus {{ border-color: #7c3aed; box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2); }}
.search-wrap .icon {{ position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: rgba(255,255,255,0.4); }}

*::-webkit-scrollbar {{ width: 10px; height: 10px; }}
*::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 5px; }}
*::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.2); }}
*::-webkit-scrollbar-track {{ background: transparent; }}

.toast {{
  position: fixed; bottom: 2rem; right: 2rem; z-index: 100;
  background: #15131f;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 0.9rem 1.25rem;
  border-radius: 0.75rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  font-size: 0.9rem;
  animation: slideIn 0.25s ease-out;
  max-width: 22rem;
}}
.toast.success {{ border-color: rgba(34, 197, 94, 0.4); }}
.toast.error {{ border-color: rgba(220, 38, 38, 0.4); }}
@keyframes slideIn {{ from {{ transform: translateY(20px); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
</style>
</head>
<body>

<header class="hero">
  <div class="max-w-7xl mx-auto">
    <h1>⚡ Lodestone</h1>
    <p class="tagline">每日 GitHub AI 热门仓库 · 已为 AI 应用工程师分类整理 · 自动检测本机 Skills · 一键安装缺失的好工具</p>
    <div class="flex flex-wrap gap-2 mt-6">
      <div class="stat-pill">📅 <b>{snap["date"]}</b></div>
      <div class="stat-pill">📦 <b>{snap["total_unique"]}</b> 个项目</div>
      <div class="stat-pill">🗂 <b>{len(snap["categories"])}</b> 个分类</div>
      <div class="stat-pill">🛠 <b>{len(local)}</b> 个本机 Skills</div>
      <div class="stat-pill">🕒 <b>{fetched_time}</b></div>
    </div>
    <div class="search-wrap">
      <i data-lucide="search" class="icon w-5 h-5"></i>
      <input id="q" type="text" placeholder="搜索项目名、tag、语言…" autocomplete="off">
    </div>
  </div>
</header>

<nav class="nav-tabs">
  <div class="max-w-7xl mx-auto px-4 flex gap-1">
    {''.join(nav_tabs)}
  </div>
</nav>

<main class="max-w-7xl mx-auto px-4 md:px-8 py-12" style="position:relative;z-index:1;">

  <!-- Local Skills -->
  <section id="local" class="scroll-mt-24 mb-20">
    <div class="section-title">🛠 本机 Skills · 自动检测</div>
    <p class="text-white/50 text-sm mb-6">扫描 <code class="px-1.5 py-0.5 rounded bg-white/5 text-purple-300">~/.claude/skills/</code> + <code class="px-1.5 py-0.5 rounded bg-white/5 text-cyan-300">~/.codex/skills/</code> · 点 "⬇ 安装" 一键拉取到本机</p>

    <h3 class="text-lg font-bold mb-3 flex items-center gap-2">
      <i data-lucide="download" class="w-5 h-5 text-purple-300"></i>
      推荐安装 · Top {len(recommend_cards)}
    </h3>
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-10">
      {''.join(rec_html) if rec_html else '<p class="text-white/40 col-span-full">暂无推荐 — 今日趋势中没匹配到 skills/mcp/agent 类项目</p>'}
    </div>

    <h3 class="text-lg font-bold mb-3 flex items-center gap-2">
      <i data-lucide="check-circle-2" class="w-5 h-5 text-green-400"></i>
      已安装 · {len(installed_badges)}
    </h3>
    <div class="flex flex-wrap gap-2">
      {''.join(installed_html) if installed_html else '<p class="text-white/40">本机未检测到任何 Skills — 试试 `./install.sh` 安装 lodestone 自己</p>'}
    </div>
  </section>

  <!-- Hot Now -->
  <section id="hot" class="scroll-mt-24 mb-20">
    <div class="section-title">🔥 Top 24 · 今日最热</div>
    <p class="text-white/50 text-sm mb-6">按 ⭐ 排序 · <span class="text-green-400">●</span> = 本机已装</p>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {''.join(hot_cards)}
    </div>
  </section>

  {''.join(sections_html)}

  <footer class="text-center py-12 mt-12 border-t border-white/5 text-white/40 text-sm">
    <div>一次 <code class="px-2 py-0.5 rounded bg-white/5 text-purple-300">radar.py crawl</code> 拉取 · 数据存 <code class="px-2 py-0.5 rounded bg-white/5">data/latest.json</code></div>
    <div class="mt-2">支持挂 cron / launchd 每日自动刷新 · 为 AI 应用工程师的情报站</div>
  </footer>
</main>

<dialog id="modal" class="modal">
  <div class="modal-box max-w-2xl">
    <div id="m-body"></div>
    <div class="modal-action">
      <button class="btn btn-ghost btn-sm" onclick="document.getElementById('modal').close()">关闭</button>
    </div>
  </div>
  <form method="dialog" class="modal-backdrop"><button>close</button></form>
</dialog>

<div id="toast-host"></div>

<script>
lucide.createIcons();

// === Search ===
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const term = q.value.trim().toLowerCase();
  document.querySelectorAll('.repo-card').forEach(el => {{
    const hay = el.textContent.toLowerCase();
    el.style.display = (!term || hay.includes(term)) ? '' : 'none';
  }});
  document.querySelectorAll('.install-card').forEach(el => {{
    const hay = el.textContent.toLowerCase();
    el.style.display = (!term || hay.includes(term)) ? '' : 'none';
  }});
}});
q.focus();

// === Nav active state ===
const tabs = document.querySelectorAll('.nav-tab');
const sections = Array.from(tabs).map(t => document.querySelector(t.getAttribute('href')));
const obs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      tabs.forEach(t => t.classList.remove('active'));
      const id = '#' + e.target.id;
      const active = document.querySelector(`.nav-tab[href="${{id}}"]`);
      if (active) active.classList.add('active');
    }}
  }});
}}, {{ rootMargin: '-40% 0px -55% 0px' }});
sections.forEach(s => s && obs.observe(s));

// === Modal ===
function showRepo(el) {{
  const r = JSON.parse(el.dataset.payload);
  const tags = (r.topics || []).slice(0, 8).map(t => `<span class="tag-chip">${{escapeHtml(t)}}</span>`).join(' ');
  const cats = (r.categories || []).map(c => `<span class="badge badge-sm badge-primary badge-outline">${{escapeHtml(c)}}</span>`).join(' ');
  const facts = r.facts || '';
  const descZh = r.desc_zh || r.desc || '（暂无描述）';
  document.getElementById('m-body').innerHTML = `
    <div class="flex items-start justify-between gap-3 mb-4">
      <div class="min-w-0">
        <h2 class="text-xl font-bold break-all">${{escapeHtml(r.name)}}</h2>
        <div class="flex flex-wrap gap-1 mt-2">${{cats}}</div>
      </div>
      <a href="${{escapeHtml(r.url)}}" target="_blank" rel="noopener" class="btn btn-primary btn-sm gap-1">
        <i data-lucide="external-link" class="w-4 h-4"></i> GitHub
      </a>
    </div>
    <div class="text-xs text-cyan-300/80 font-mono leading-relaxed mb-3">${{escapeHtml(facts)}}</div>
    <div class="rounded-lg bg-purple-500/10 border border-purple-500/20 p-4 mb-4">
      <div class="text-xs uppercase tracking-wider text-purple-300/70 mb-1.5 font-semibold">📖 官方描述（中文翻译）</div>
      <p class="text-sm leading-relaxed text-white/85">${{escapeHtml(descZh)}}</p>
    </div>
    ${{r.desc && r.desc !== descZh ? `
    <details class="mb-4">
      <summary class="text-xs uppercase tracking-wider text-white/50 cursor-pointer font-semibold">🌐 英文原描述</summary>
      <p class="text-xs text-white/60 mt-2 leading-relaxed">${{escapeHtml(r.desc)}}</p>
    </details>` : ''}}
    <div class="flex items-center gap-2 flex-wrap pt-3 border-t border-white/5">
      <span class="text-amber-400 font-mono font-bold">⭐ ${{r.stars.toLocaleString()}}</span>
      <span class="badge badge-sm badge-outline">${{escapeHtml(r.lang)}}</span>
      <div class="flex flex-wrap gap-1">${{tags}}</div>
    </div>
  `;
  lucide.createIcons();
  document.getElementById('modal').showModal();
}}

// === Install ===
async function installSkill(btn, name, url) {{
  if (!confirm(`确认安装 skill "${{name}}" 到 ~/.claude/skills/ 和 ~/.codex/skills/？\\n\\n这会 git clone + 创建 symlink。`)) return;
  btn.disabled = true;
  const oldText = btn.innerHTML;
  btn.innerHTML = '⏳ 克隆中…';
  try {{
    const resp = await fetch('/api/install', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ name, url }})
    }});
    const data = await resp.json();
    if (data.ok) {{
      btn.innerHTML = '✓ 已装';
      btn.classList.add('done');
      toast(`✓ 已安装 ${{name}} · 重新加载中…`, 'success');
      setTimeout(() => location.reload(), 1200);
    }} else {{
      btn.innerHTML = '✗ 失败';
      btn.classList.add('error');
      btn.disabled = false;
      toast(`✗ 安装失败：${{data.error || '未知错误'}}`, 'error');
    }}
  }} catch (e) {{
    btn.innerHTML = oldText;
    btn.disabled = false;
    toast(`✗ 网络错误：${{e.message}}`, 'error');
  }}
}}

function toast(msg, kind) {{
  const host = document.getElementById('toast-host');
  const el = document.createElement('div');
  el.className = `toast ${{kind || ''}}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}}

function escapeHtml(s) {{
  return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}
</script>
</body>
</html>'''
    out_path = OUT / "index.html"
    out_path.write_text(html_doc)
    print(f"[render] {out_path.relative_to(ROOT)} ({len(html_doc)//1024} KB)")
    return out_path


def today():
    """Print today's top picks to terminal."""
    latest = DATA / "latest.json"
    if not latest.exists():
        print("[today] no data — run `radar.py crawl`", file=sys.stderr)
        sys.exit(1)
    snap = json.loads(latest.read_text())
    print(f"\n⚡ Lodestone · {snap['date']} · {snap['total_unique']} repos\n")
    print("🔥 Top 15 Hot Now:")
    for i, r in enumerate(snap["hot_now"][:15], 1):
        print(f"  {i:2}. {r['name']:<42} ⭐ {r['stars']:>6,}  {r['lang']}")
        if r["desc"]:
            print(f"      {r['desc'][:90]}")
    print(f"\n📂 Categories:")
    for cat in snap["categories"]:
        print(f"  · {cat['name']:<35} {cat['count']} repos")


def serve(port=8765):
    """API + static server for Vue 3 frontend (proxies through Vite).
    Endpoints:
      GET  /api/data    → data/latest.json contents
      GET  /api/local   → installed skills in ~/.claude/skills + ~/.codex/skills
      POST /api/crawl   → spawn `radar.py crawl` in background
      POST /api/install → clone+symlink a skill (validated)
      GET  /*           → static files from OUT/
    """
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    # ponytail: serve OUT/ via chdir so SimpleHTTPRequestHandler resolves correctly
    os.chdir(OUT)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write(f"  [{self.command}] {self.path}\n")

        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self):
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self):
            if self.path == "/api/data":
                latest = DATA / "latest.json"
                if latest.exists():
                    with open(latest, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._json({"error": "no data yet — run ./radar.py crawl"}, status=503)
                return
            if self.path == "/api/local":
                local = detect_local_skills()
                clis = detect_cli_tools()
                return self._json({
                    "skills": local["skills"],
                    "commands": local["commands"],
                    "agents": local["agents"],
                    "plugins": local["plugins"],
                    "clis": clis,
                    "counts": {
                        "skills": len(local["skills"]),
                        "commands": len(local["commands"]),
                        "agents": len(local["agents"]),
                        "plugins": len(local["plugins"]),
                        "clis": len(clis),
                    },
                    "total": (
                        len(local["skills"]) + len(local["commands"]) +
                        len(local["agents"]) + len(local["plugins"]) + len(clis)
                    ),
                })
            if self.path.startswith("/api/top"):
                # ponytail: client-paginate over the bundled top_5k_plus list — 0 extra endpoints
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                try:
                    page = max(1, int(qs.get("page", ["1"])[0]))
                except ValueError:
                    page = 1
                try:
                    size = min(48, max(1, int(qs.get("size", ["12"])[0])))
                except ValueError:
                    size = 12
                sort = qs.get("sort", ["stars"])[0]

                latest_path = DATA / "latest.json"
                if not latest_path.exists():
                    return self._json({"error": "no data yet — run ./radar.py crawl"}, status=503)
                try:
                    snap = json.loads(latest_path.read_text())
                except (OSError, ValueError):
                    return self._json({"error": "corrupt latest.json"}, status=500)

                repos = list((snap.get("top_5k_plus") or {}).get("repos") or [])
                if sort == "name":
                    repos = sorted(repos, key=lambda r: r["name"].lower())
                elif sort == "recent":
                    repos = sorted(repos, key=lambda r: r.get("pushed", ""), reverse=True)
                # default: stars desc (crawler already sorts)

                total = len(repos)
                pages = max(1, (total + size - 1) // size)
                page = min(page, pages)
                start = (page - 1) * size
                return self._json({
                    "repos": repos[start:start + size],
                    "page": page,
                    "size": size,
                    "total": total,
                    "pages": pages,
                    "sort": sort,
                })
            return super().do_GET()

        def do_POST(self):
            if self.path == "/api/install":
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    path = install_skill_from_github(name, url)
                    self._json({"ok": True, "message": f"已安装 {name}", "path": path})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/install-cli":
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    command = body.get("command", "").strip()
                    path = install_cli_wrapper(name, command)
                    self._json({"ok": True, "message": f"已创建 /{name} 命令", "path": path})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/crawl":
                # ponytail: fire-and-forget background crawl so UI doesn't block
                subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "crawl"],
                    cwd=str(Path(__file__).parent.resolve()),
                    stdout=open(DATA / "crawl.log", "ab"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                return self._json({"ok": True, "message": "crawl started in background"})
            self.send_error(404)

    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"[serve] {url}  (API: /api/data /api/local /api/top /api/install /api/crawl · Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] stopped")


def all_in_one():
    """crawl → render → open browser → keep serving."""
    crawl()
    render()
    webbrowser.open(f"file://{(OUT / 'index.html').resolve()}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl": crawl()
    elif cmd == "render": render()
    elif cmd == "serve": serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "today": today()
    elif cmd == "all": all_in_one()
    else:
        print(__doc__)
        sys.exit(1)