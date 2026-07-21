#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + JSON API for the Vue 3 frontend.

Commands:
  radar.py crawl   - fetch trending AI repos from GitHub, write to PG
  radar.py serve   - JSON API on http://localhost:PORT (Vite at :5173 proxies /api/* here)
  radar.py today   - print today's top picks in terminal

Reuses `gh` CLI for GitHub auth (avoids token management).
Ponytail: minimum code, stdlib only, Vue UI lives in frontend/.
"""
import json, subprocess, sys, os, re, datetime, time, http.server, socketserver, urllib.request, urllib.parse, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict
import db  # ponytail: PG is source of truth (was: data/latest.json)

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

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
        "id": "ide",
        "name": "AI IDE & 编辑器",
        "desc": "AI 编程 IDE、Cursor 替代品、嵌入式代码助手",
        "queries": [
            "topic:cursor stars:>200",
            "topic:cursor-ai stars:>200",
            "topic:windsurf stars:>200",
            "topic:ai-ide stars:>100",
            "aider in:name,description stars:>500",
            "cline in:name,description stars:>500",
            "continue in:name stars:>500",
        ],
    },
    {
        "id": "gateway",
        "name": "LLM Gateway & Router",
        "desc": "统一接入多家 LLM 的代理/路由 — OpenRouter、LiteLLM、Portkey",
        "queries": [
            "topic:litellm stars:>200",
            "topic:openrouter stars:>200",
            "topic:llm-gateway stars:>100",
            "topic:llm-router stars:>100",
            "LLM gateway in:name,description stars:>200",
            "LLM proxy in:name,description stars:>300",
        ],
    },
    {
        "id": "observability",
        "name": "LLM 可观测 & Tracing",
        "desc": "LLM 应用监控、trace、token 计费、prompt 调优 — Langfuse / Helicone / Phoenix",
        "queries": [
            "topic:langfuse stars:>200",
            "topic:llm-observability stars:>100",
            "topic:llmops stars:>200",
            "topic:helicone stars:>100",
            "LLM tracing in:name,description stars:>200",
            "LLM observability in:name,description stars:>100",
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
# ponytail: GitHub Search API 422s on `stars:>N topic:X OR topic:Y` (multi-topic OR). Each topic
# gets its own single-topic query. New repos are added slowly enough that 1 query per topic is
# fine — duplicates collapse in the `top_5k_repos` dict.
TOP_5K_QUERIES = [
    # ponytail: threshold is 1000 (matches SQL gate) so we don't waste API quota on rows
    # the UI will filter out. Topic queries — the obvious AI hard-tags.
    "stars:>1000 topic:ai",
    "stars:>1000 topic:llm",
    "stars:>1000 topic:agent",
    "stars:>1000 topic:rag",
    "stars:>1000 topic:vector-database",
    # ponytail: each Claude/Codex/MCP family topic on its own line (the OR-combined version 422s).
    "stars:>1000 topic:claude",
    "stars:>1000 topic:claude-code",
    "stars:>1000 topic:mcp-server",
    "stars:>1000 topic:mcp",
    # ponytail: code agent / AI dev tools — caught by topic tags common in 1k-5k tier.
    "stars:>1000 topic:ai-coding",
    "stars:>1000 topic:ai-coding-agent",
    "stars:>1000 topic:code-agent",
    "stars:>1000 topic:agent-skills",
    "stars:>1000 topic:claude-skills",
    "stars:>1000 topic:ai-skills",
    "stars:>1000 topic:copilot",
    "stars:>1000 topic:ai-coding-tools",
    "stars:>1000 topic:developer-tools",
    # ponytail: framework topics — one each.
    "stars:>1000 topic:langchain",
    "stars:>1000 topic:langgraph",
    "stars:>1000 topic:llamaindex",
    # ponytail: text-based queries catch topic=[] projects (openai/codex 100k⭐, msitarzewski/agency-agents
    # 135k⭐, earendil-works/pi 74k⭐). Same AI phrases the topic whitelist uses, but searched in
    # name/description instead.
    'stars:>1000 "AI agent" in:name,description',
    'stars:>1000 "coding agent" in:name,description',
    'stars:>1000 "LLM" in:name,description',
    'stars:>1000 "Claude Code" in:name,description',
    'stars:>1000 "knowledge graph" in:name,description',
    'stars:>1000 "agent skill" in:name,description',
    'stars:>1000 "AI skill" in:name,description',
    # ponytail: awesome lists are huge but escape topic filters (their topic tags are generic).
    'stars:>10000 awesome-llm in:name',
    'stars:>10000 awesome-ai in:name',
    # ponytail: provider gateways (volcengine/OpenViking etc.)
    'stars:>1000 "agent memory" in:name,description',
    'stars:>1000 "context database" in:name,description',
]
TOP_5K_LIMIT = 300

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

# ponytail: HARD AI topics — strict subset. Bare 'ai' is NOT here. Used to require a strong
# AI signal so non-AI repos with just an 'ai' topic (dbeaver, netdata) get filtered out.
AI_TOPIC_HARD = frozenset({
    "llm", "llms", "gpt", "chatgpt", "openai", "anthropic", "claude", "claude-code",
    "gemini", "deepseek", "llama", "qwen", "mistral", "ollama", "vllm",
    "transformer", "transformers", "huggingface", "hugging-face",
    "autogen", "crewai", "langchain", "langgraph", "llamaindex",
    "rag", "embedding", "embeddings", "vector-database", "pgvector",
    "stable-diffusion", "comfyui", "diffusion-models",
    "text-to-image", "text-to-video", "image-generation", "image2image",
    "whisper", "tts", "speech-to-text", "speech-recognition",
    "voice-cloning", "voice-ai",
    "object-detection", "computer-vision", "nlp",
    "natural-language-processing", "artificial-intelligence",
    "copilot", "cursor-ai", "code-assistant", "ai-coding",
    "ai-coding-agent", "prompt-engineering",
    "agentic", "agentic-ai", "autonomous-agent", "multi-agent",
    "agent-skills", "ai-agent",
    "mcp-server",
    "spring-ai", "springai",
})

# ponytail: text-level AI hints — checked in repo name + description when topic check fails.
# Bare ' ai ' (with spaces) catches "personal AI assistant" / "Build with AI" without matching
# 'ai-powered', 'email', 'main', etc.
AI_TEXT_HINTS = frozenset({
    " ai ",
    " llm ", " gpt ",
    "chatgpt", "openai", "anthropic", "claude",
    "langchain", "huggingface", "stable-diffusion", "comfyui",
    "voice-cloning", "autogen", "crewai", "langgraph",
    "mcp-server", "mcp_server",
    "deepfake", "face swap", "face-swap",
    "generative", "neural network", "deep learning", "machine learning",
    "natural language", "computer vision", "object detection",
    "speech recognition", "speech-to-text", "speech to text",
    "coding agent",
})

# ponytail: high-star noise that would otherwise sneak past the AI whitelist
AI_TOPIC_BLOCKLIST = frozenset({
    "stock", "stocks", "trading", "crypto", "nft", "forex", "porn",
    "ai-porn", "ai-girlfriend", "adult-content",
    "astrology", "fortune-telling",
})


def is_ai_relevant(repo):
    """Strict AI filter — requires at least one HARD topic, OR an AI phrase in name/description.
    ponytail: bare 'ai' topic alone is no longer enough — that caught dbeaver/netdata."""
    topics = [t.lower() for t in (repo.get("topics") or [])]
    if any(t in AI_TOPIC_BLOCKLIST for t in topics):
        return False
    blob_topics = " ".join(topics)
    if any(h in blob_topics for h in AI_TOPIC_HARD):
        return True
    # fallback: name + description must contain a strong AI phrase
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or repo.get("desc") or "").lower()
    text = f" {name} {desc} "
    return any(h in text for h in AI_TEXT_HINTS)

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
    "ide":      "AI 原生 IDE / 嵌入式代码助手 — Cursor 替代品",
    "gateway":  "统一接入多家 LLM 的代理/路由，一套代码跑全模型",
    "observability": "监控 LLM 应用的 trace、token 消耗、prompt 调优",
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


def _parse_frontmatter_desc(path) -> str | None:
    """Read the YAML frontmatter `description` field from a .md file. Cheap — reads first 4KB only."""
    try:
        with open(path, "rb") as fp:
            head = fp.read(4096).decode("utf-8", errors="ignore")
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    end = head.find("\n---", 3)
    if end < 0:
        return None
    block = head[3:end]
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("description:"):
            val = s[len("description:"):].strip()
            return val.strip('"').strip("'") or None
    return None


def _repo_slug_from_url(url: str | None) -> str:
    """Extract 'owner/repo' from a GitHub URL, or return '' for empty/invalid."""
    if not url or "github.com/" not in url:
        return ""
    tail = url.split("github.com/", 1)[1].rstrip("/").rstrip(".git")
    parts = tail.split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _gh_repo_meta(full_name: str) -> dict | None:
    """Query GitHub via `gh` for {stars, topics, pushed_at, description}. Caches per process.
    Returns None if `gh` unavailable or repo private/missing."""
    if not full_name or "/" not in full_name:
        return None
    if not hasattr(_gh_repo_meta, "_cache"):
        _gh_repo_meta._cache = {}
    if full_name in _gh_repo_meta._cache:
        return _gh_repo_meta._cache[full_name]
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            _gh_repo_meta._cache[full_name] = None
            return None
        data = json.loads(r.stdout)
        out = {
            "name": data.get("full_name"),
            "url": data.get("html_url"),
            "stars": data.get("stargazers_count") or 0,
            "topics": data.get("topics") or [],
            "pushed_at": data.get("pushed_at"),
            "description": data.get("description"),
        }
        _gh_repo_meta._cache[full_name] = out
        return out
    except Exception:
        _gh_repo_meta._cache[full_name] = None
        return None


def _load_repo_index() -> dict:
    """Build repo lookup {segment → repo} from PG. Used for topic/stars enrichment + replacement detection."""
    by_repo = {}
    try:
        import db
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name, url, description, desc_zh, stars, lang, topics, pushed_at, best_category
                FROM repos WHERE is_ai_relevant
            """)
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                rec["topics"] = list(rec.get("topics") or [])
                by_repo[rec["name"].split("/")[-1]] = rec
    except Exception:
        pass
    return by_repo


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

    # ponytail: build lookup from PostgreSQL — match by repo segment (last path component). DB is source of truth (latest.json deprecated).
    by_repo = _load_repo_index()

    # ponytail: build lookup from sidecar — covers installs not in latest.json
    by_origin = {"skills": {}, "commands": {}, "agents": {}, "plugins": {}}
    if SKILL_ORIGINS.exists():
        try:
            data = json.loads(SKILL_ORIGINS.read_text())
            for kind in ("skills", "commands", "agents", "plugins"):
                for key, info in (data.get(kind) or {}).items():
                    by_origin[kind][key] = info
        except (OSError, ValueError):
            pass
    # ponytail: index by bare name for commands/agents (file stem matches name)
    cmd_origin_by_name = by_origin["commands"]
    agent_origin_by_name = by_origin["agents"]
    plugin_origin_by_key = by_origin["plugins"]  # plugin key format: name@marketplace

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
        elif name in by_origin["skills"]:
            o = by_origin["skills"][name]
            meta["url"] = o.get("url")
            meta["source"] = "origin"
            # ponytail: installed skill not in our PG — fetch stars/topics live from GitHub so the source card shows real ⭐
            full = f"{o.get('owner')}/{o.get('repo')}" if o.get("owner") and o.get("repo") else None
            if full:
                gh = _gh_repo_meta(full)
                if gh:
                    meta["stars"] = gh.get("stars") or 0
                    meta["topics"] = gh.get("topics") or []
                    meta["desc_en"] = gh.get("description") or meta.get("desc_en")
                    meta["pushed_at"] = gh.get("pushed_at")
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
                    origin = cmd_origin_by_name.get(f.stem, {})
                    desc_en = origin.get("desc_en") or _parse_frontmatter_desc(f)
                    out["commands"][f.stem] = {
                        "claude": True,
                        "path": str(f),
                        "url": origin.get("url"),
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": desc_en,
                    }
        except OSError:
            pass

    # ponytail: Claude subagent definitions are *.md files in agents/
    agent_dir = Path.home() / ".claude" / "agents"
    if agent_dir.exists():
        try:
            for f in agent_dir.iterdir():
                if f.suffix == ".md" and not f.name.startswith("."):
                    origin = agent_origin_by_name.get(f.stem, {})
                    desc_en = origin.get("desc_en") or _parse_frontmatter_desc(f)
                    out["agents"][f.stem] = {
                        "claude": True,
                        "path": str(f),
                        "url": origin.get("url"),
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": desc_en,
                    }
        except OSError:
            pass

    # ponytail: plugins from installed_plugins.json (v2 schema).
    # GitHub URL priority: sidecar override > known_marketplaces.json dynamic read > none.
    # Reading known_marketplaces.json means we auto-pick-up every marketplace the user has
    # installed — no need to maintain a hardcoded list.
    marketplace_urls: dict[str, str] = {}
    known_mp_file = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if known_mp_file.exists():
        try:
            mp_data = json.loads(known_mp_file.read_text())
            for mp_name, mp_info in (mp_data or {}).items():
                src = mp_info.get("source") or {}
                if src.get("source") == "github" and src.get("repo"):
                    marketplace_urls[mp_name] = f"https://github.com/{src['repo']}"
        except (OSError, ValueError):
            pass
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
                origin = plugin_origin_by_key.get(plugin_key, {})
                default_url = marketplace_urls.get(marketplace)
                out["plugins"].append({
                    "name": name,
                    "marketplace": marketplace,
                    "version": inst.get("version", ""),
                    "install_path": inst.get("installPath", ""),
                    "url": origin.get("url") or default_url,
                    "desc_zh": origin.get("desc_zh"),
                    "desc_en": origin.get("desc_en"),
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
    else:
        # ponytail: name/url consistency — refuse mismatched pair to prevent cloning malicious
        # content under a trusted name. Parse the path and require it to match name.
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        # path may include trailing ".git" — strip it
        if path.endswith(".git"):
            path = path[:-4]
        if path != name:
            raise ValueError(f"url {url!r} does not match name {name!r} — refusing to clone mismatch")

    target = SKILLS_CACHE / f"{owner}__{repo}"   # ponytail: namespace by owner to avoid collisions across different owners with same repo name
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


def uninstall_skill(name: str) -> dict:
    """Remove a skill: unlink from ~/.claude/skills + ~/.codex/skills, drop cache dir, remove sidecar entry.
    Returns {removed_links: [paths], cache: path_or_null}."""
    if not name or not all(c.isalnum() or c in "-_." for c in name):
        raise ValueError(f"invalid skill name: {name!r}")
    removed = []
    for skills_root in [Path.home() / ".claude" / "skills",
                        Path.home() / ".codex" / "skills"]:
        link = skills_root / name
        if link.is_symlink() or link.exists():
            try:
                if link.is_symlink():
                    link.unlink()
                elif link.is_dir():
                    shutil.rmtree(link)
                removed.append(str(link))
            except OSError as e:
                sys.stderr.write(f"  [warn] failed to remove {link}: {e}\n")
    # ponytail: also remove the cache clone dir if no other skill symlinks point to it
    if SKILL_ORIGINS.exists():
        try:
            origins = json.loads(SKILL_ORIGINS.read_text())
            entry = (origins.get("skills") or {}).pop(name, None)
            if entry:
                owner = entry.get("owner", "")
                repo = entry.get("repo", name)
                # ponytail: check both new (owner__repo) and legacy (bare repo) cache paths
                candidates = [SKILLS_CACHE / f"{owner}__{repo}"]
                if owner:
                    candidates.append(SKILLS_CACHE / repo)
                still_used = False
                for r in (origins.get("skills") or {}).values():
                    if r.get("owner") == owner and r.get("repo") == repo:
                        still_used = True
                        break
                for cache_dir in candidates:
                    if cache_dir.exists() and not still_used:
                        try:
                            shutil.rmtree(cache_dir)
                        except OSError:
                            pass
            SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
        except (OSError, ValueError):
            pass
    return {"removed_links": removed}


def replace_skill(old_name: str, new_name: str, new_url: str = "") -> dict:
    """Install `new_name` then remove `old_name`. Used when user picks a superior alternative.
    ponytail: rollback on uninstall failure — if new installs but old can't be removed,
    we uninstall new to restore pre-call state. Without this the user is left with BOTH
    installed, which is the opposite of "replace"."""
    new_path = install_skill_from_github(new_name, new_url)
    try:
        removed = uninstall_skill(old_name)
    except Exception as e:
        # ponytail: rollback — best-effort, log if rollback itself fails so user sees the state
        sys.stderr.write(f"  [warn] replace: uninstall {old_name!r} failed ({e}); rolling back new install\n")
        try:
            uninstall_skill(new_name)
        except Exception as e2:
            sys.stderr.write(f"  [ERROR] rollback also failed: {e2}; new still installed at {new_path}\n")
        raise
    return {"new_path": new_path, "old_removed": removed}


# ponytail: generic topics every AI tool has — exclude from "same domain" matching so we don't
# falsely recommend hermes-agent as a replacement for graphify just because both have "claude-code".
# Threshold for "generic" = ≥5 repos in DB share this tag. Picked empirically; tighten if too noisy.
_GENERIC_TOPICS = frozenset({
    # AI/agent meta
    "ai", "ai-agents", "ai-agent", "ai-tools", "agent", "agents", "agentic", "agentic-ai",
    "agentic-framework", "agentic-workflow", "llm", "llms", "large-language-models",
    "machine-learning", "deep-learning", "generative-ai", "genai", "rag",
    # RAG/embedding/data layer buzzwords — shared by every RAG-flavored repo, can't be anchors
    "graphrag", "knowledge-graph", "embedding", "embeddings", "vector-database", "pgvector",
    "gpt", "gpt-4", "openai-api",
    # vendor names (every Claude/Codex tool has these)
    "anthropic", "claude", "claude-code", "claude-ai", "codex", "openai", "chatgpt",
    "google", "gemini", "deepseek", "qwen", "kimi", "openclaw",
    # generic IDE/coding tool names
    "opencode", "antigravity", "kiro", "qoder", "trae", "windsurf", "windsurf-ai",
    "cursor", "cursor-ai", "copilot", "command-line",
    # scaffolding
    "skills", "agent-skills", "skill", "obra", "superpowers",
    "awesome", "awesome-list", "awesome-llm-apps", "awesome-claude-skills",
    "developer-tools", "devtools", "tools", "cli",
    # languages
    "python", "typescript", "javascript", "rust", "go", "ruby",
})


def find_skill_replacements(local: dict, repos_by_segment: dict, min_anchors: int = 1,
                            min_topic_repos: int = 1) -> list[dict]:
    """For each installed skill with topics+stars, find uninstalled repos that share
    VERTICAL-domain topics AND look like a stronger alternative.

    Strategy:
      1. Filter out generic topics (claude, codex, ai, agent, llm, graphrag, knowledge-graph, ...) —
         these are universal across many AI tools, so overlapping on them is meaningless. The
         graphrag/knowledge-graph/etc. terms (RAG-flavored) are generic because they're shared
         by every RAG repo regardless of vertical; using them as anchors gave wrong matches
         like LightRAG → graphify.
      2. ponytail: VERTICAL ANCHOR requirement — at least one of the overlap topics must be a
         vertical-specific topic shared by ≤ a few repos in DB. Topics like 'graphrag' or
         'knowledge-graph' don't qualify as anchors even after the generic filter, because the
         overlap itself could be just two AI buzzwords. Require ≥1 overlap topic that's NOT a
         known "buzzword" (i.e. appears in < threshold repos).
      3. Same-category guard — candidate's best_category MUST match installed's best_category.
      4. Score = specific overlap count × 100 + candidate stars.
      5. Sort candidates by score; require ≥min_topic_repos candidates to confirm a category
         exists before surfacing a replacement.

    Returns [{installed, recommended}]."""
    out = []
    # ponytail: build dynamic anchor topic whitelist — a topic is a "vertical anchor" if
    # fewer than 8 repos in our DB share it. Topics like graphrag/knowledge-graph show up in
    # 4-5 repos but they cross distinct verticals (LightRAG vs graphify), so we additionally
    # exclude RAG-flavored anchors entirely.
    _RAG_FLAVORED_ANCHORS = frozenset({"graphrag", "knowledge-graph", "rag", "vector-database",
                                       "embedding", "embeddings", "large-language-models",
                                       "llm-evaluation", "llm-memory", "agent-memory"})
    for name, meta in (local.get("skills") or {}).items():
        url = meta.get("url")
        if not url:
            continue
        inst_topics = set(meta.get("topics") or [])
        inst_specific = inst_topics - _GENERIC_TOPICS
        inst_stars = meta.get("stars") or 0
        if not inst_specific or not inst_stars:
            continue
        # ponytail: vertical anchor — installed must have ≥1 specific topic that is also
        # a real vertical differentiator (not just another AI buzzword).
        inst_anchors = inst_specific - _RAG_FLAVORED_ANCHORS
        if len(inst_anchors) < min_anchors:
            continue
        # ponytail: look up installed skill's best_category from the same PG index
        inst_record = repos_by_segment.get(name) or {}
        inst_cat = inst_record.get("best_category")
        candidates = []
        for r in repos_by_segment.values():
            rseg = r["name"].split("/")[-1]
            rurl = (r.get("url") or "").lower()
            if rseg == name:
                continue
            if rurl and rurl == (url or "").lower():
                continue
            # ponytail: same-domain guard. If installed has a category, candidate must match.
            c_cat = r.get("best_category")
            if inst_cat and c_cat and inst_cat != c_cat:
                continue
            c_topics = set(r.get("topics") or [])
            c_specific = c_topics - _GENERIC_TOPICS
            overlap = inst_specific & c_specific
            # ponytail: vertical anchor — overlap must contain ≥min_anchors TRUE vertical anchor(s)
            # shared between installed and candidate. Pure RAG-flavored overlap
            # (graphrag/knowledge-graph only) doesn't count. This is the SOLE filter; we dropped
            # the old `min_overlap=2` gate because vertical-anchored matches with 1 specific
            # topic (e.g. graphify↔tirth8205/code-review-graph via tree-sitter) are valid.
            anchor_overlap = inst_anchors & c_specific
            if len(anchor_overlap) < min_anchors:
                continue
            c_stars = r.get("stars") or 0
            if c_stars < 200:
                continue
            # ponytail: score favors anchor strength + topic count + stars
            score = len(anchor_overlap) * 200 + len(overlap) * 50 + min(c_stars, 50000) // 100
            reasons = [
                f"共享 vertical anchor：{', '.join(sorted(anchor_overlap))}",
                f"共 {len(overlap)} 个特定 topic：{', '.join(sorted(list(overlap))[:4])}",
                f"⭐ {c_stars:,}" + (f" vs 已装 {inst_stars:,}" if inst_stars else ""),
            ]
            if inst_cat and c_cat and inst_cat == c_cat:
                reasons.append(f"同领域：{inst_cat}")
            candidates.append({
                "name": r["name"], "url": r["url"], "stars": c_stars,
                "topics": sorted(c_topics),
                "desc_zh": r.get("desc_zh"), "desc_en": r.get("description"),
                "overlap": sorted(overlap), "anchors": sorted(anchor_overlap),
                "reasons": reasons, "score": score,
            })
        if len(candidates) >= min_topic_repos:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]
            # ponytail: decide replace vs alongside per installed→recommended pair.
            # "替代" requires ALL three signals to fire — same vertical AND ≥2 anchor overlap
            # AND the recommended is meaningfully stronger. Anything less → "并存" (coexist
            # with the existing install). Conservative on purpose: better to nudge coexistence
            # than to talk the user into uninstalling something that works.
            top_record = repos_by_segment.get(top["name"].split("/")[-1]) or {}
            top_cat = top_record.get("best_category")
            same_cat = bool(inst_cat and top_cat and inst_cat == top_cat)
            strong_overlap = len(top.get("anchors") or []) >= 2
            much_stronger = top["stars"] > (inst_stars or 0) * 1.5
            mode = "replace" if (same_cat and strong_overlap and much_stronger) else "alongside"
            out.append({
                "installed": {
                    "name": name, "url": url, "stars": inst_stars,
                    "topics": sorted(inst_topics),
                    "best_category": inst_cat,
                },
                "recommended": {**top, "best_category": top_cat},
                "alternatives_count": len(candidates),
                "mode": mode,
            })
    out.sort(key=lambda x: x["recommended"]["score"], reverse=True)
    return out


def set_capability_origin(kind: str, name: str, url: str = "", desc_zh: str = "", desc_en: str = ""):
    """Write/edit GitHub origin for a command/agent/plugin in the sidecar.
    `kind` ∈ {commands, agents, plugins}. For plugins, `name` is the full plugin key (name@marketplace).
    Empty `url` clears the entry. Returns the merged origin dict for this item."""
    if kind not in ("commands", "agents", "plugins"):
        raise ValueError(f"unsupported kind: {kind!r}")
    if not name or "/" in name and kind != "plugins":
        raise ValueError(f"invalid name: {name!r}")
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")

    SKILL_ORIGINS.parent.mkdir(parents=True, exist_ok=True)
    origins = {}
    if SKILL_ORIGINS.exists():
        try:
            origins = json.loads(SKILL_ORIGINS.read_text())
        except (OSError, ValueError):
            origins = {}  # ponytail: corrupted sidecar — start fresh

    bucket = origins.setdefault(kind, {})
    if url or desc_zh or desc_en:
        entry = bucket.get(name, {})
        if url:
            entry["url"] = url
        if desc_zh:
            entry["desc_zh"] = desc_zh
        if desc_en:
            entry["desc_en"] = desc_en
        entry["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        bucket[name] = entry
    else:
        bucket.pop(name, None)

    SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
    return bucket.get(name, {})


# ponytail: well-known AI/dev CLI tools worth surfacing to the user
KNOWN_CLIS = [
    "rtk", "gh", "docker", "kubectl", "helm", "terraform",
    "jq", "rg", "fd", "fzf", "tmux", "git", "curl", "ffmpeg",
    "aws", "gcloud", "az", "supabase", "vercel", "wrangler",
]


def group_capabilities_by_origin(local: dict) -> list[dict]:
    """Bucket skills/commands/agents/plugins by their `url` (source repo). Only items with
    a URL are included — local-only / unknown-source items are dropped per UX rule:
    "if it's from a GitHub repo, show this source card; the rest don't need to be shown".
    Returns [{url, slug, name, counts, items}], where `items` is a flat list of
    {type, name, desc_en, desc_zh, path, url, stars, topics} for drill-in display."""
    bucket: dict[str, dict] = {}
    # ponytail: skills are a dict {name: meta}; commands/agents are same shape; plugins is a list
    sources = [
        ("skills",   [(n, m) for n, m in (local.get("skills") or {}).items() if m.get("url")]),
        ("commands", [(n, m) for n, m in (local.get("commands") or {}).items() if m.get("url")]),
        ("agents",   [(n, m) for n, m in (local.get("agents") or {}).items() if m.get("url")]),
        ("plugins",  [(f"{p['name']}@{p.get('marketplace','')}", p) for p in (local.get("plugins") or []) if p.get("url")]),
    ]
    for kind, items in sources:
        for name, entry in items:
            url = entry.get("url")
            slug = _repo_slug_from_url(url)
            grp = bucket.setdefault(url, {
                "url": url,
                "slug": slug,
                "name": slug,
                "counts": {"skills": 0, "commands": 0, "agents": 0, "plugins": 0},
                "items": [],
            })
            grp["counts"][kind] += 1
            grp["items"].append({
                "type": kind,
                "name": entry.get("name") or name,
                "desc_en": entry.get("desc_en"),
                "desc_zh": entry.get("desc_zh"),
                "path": entry.get("path") or entry.get("install_path"),
                "url": url,
                "stars": entry.get("stars"),
                "topics": entry.get("topics") or [],
            })
    groups = sorted(bucket.values(), key=lambda g: g["slug"])
    for g in groups:
        g["items"].sort(key=lambda it: (it["type"], it["name"] or ""))
        # ponytail: expose total for the stat tile convenience
        g["total"] = len(g["items"])
    return groups


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

    Security: the generated markdown uses Claude Code's `!`cmd`` syntax which EXECUTES
    the command when the slash command is invoked. So `command` is treated as shell —
    we must reject anything that could redirect, pipe, substitute, or chain.
    ponytail: allowlist = "a single executable token + optional safe flags + safe path args".
    Examples that pass: `claude`, `gh`, `git status --short`, `ls /tmp`, `python3 script.py`
    Examples that fail: `curl x|sh`, `rm -rf ~`, `$(whoami)`, `a; b`, `a && b`, backticks.
    """
    if not name or not all(c.isalnum() or c in "-_." for c in name) or ".." in name:
        raise ValueError(f"invalid command name: {name!r}")
    if not command or len(command) > 200:
        raise ValueError("command must be 1-200 chars")

    # ponytail: shell metacharacter check — reject any of these BEFORE writing to disk.
    # They enable pipe/chain/substitution/redirection that turn this into RCE.
    forbidden = set(";|&$()<>`\\\"'*?[]{}~#\n\r\t")
    bad = sorted({c for c in command if c in forbidden})
    if bad:
        raise ValueError(f"command contains forbidden shell metacharacters: {bad!r}")
    # ponytail: require single executable at start (alnum + _-.+), then whitespace + args.
    # Each arg = same safe charset. No `$VAR`, no `~`, no backticks already blocked above.
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_.\-+]+(?:\s+[A-Za-z0-9_.\-+/=@:]+)*", command):
        raise ValueError(f"command must be a single executable + safe args: {command!r}")

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


# ponytail: hand-picked repos that escape topic/description search but are obvious AI tools
# (some maintainers never set topics, some are <5k stars at crawl time). Force-include on every
# crawl so the 5k+ view reflects what users actually expect to see.
MANUAL_SEED_REPOS = frozenset({
    # User-curated 2026-07-21 list — these all slipped past TOP_5K_QUERIES at crawl time
    "Egonex-AI/Understand-Anything",  # knowledge-graph IDE (75k stars, claude-code topic)
    "lodestone/hallmark",             # anti-AI-slop design skill
    "Shubhamsaboo/awesome-llm-apps",  # 100+ AI agent apps (125k stars, generic topics)
    "stablyai/orca",                  # desktop ADE for parallel coding agents (24k stars)
    "GaoSSR/best-claude-hud",         # Claude HUD plugin
    "lidge-jun/opencodex",            # universal LLM proxy for codex/claude-code
    "lodestone/ai-agent-book",        # 《深入理解 AI Agent》开源书
    "volcengine/OpenViking",          # ByteDance context DB for agents (27k stars)
    "msitarzewski/agency-agents",     # complete AI agency (135k stars, no topics)
    # Safety net
    "all-hands-ai/openhands",         # common 2025 coding agent
})


def gh_fetch_repo(full_name):
    """Fetch a single repo's full metadata. Used for MANUAL_SEED_REPOS."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        item = json.loads(r.stdout)
    except Exception:
        return None
    return {
        "name": item["full_name"],
        "desc": (item.get("description") or "").strip(),
        "url": item["html_url"],
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "lang": item.get("language") or "—",
        "topics": item.get("topics", []) or [],
        "updated": item.get("updated_at", "")[:10],
        "pushed": item.get("pushed_at", "")[:10],
        "score": 0,
    }


def fetch_github_trending(since: str = "daily", max_repos: int = 30):
    """Scrape github.com/trending and enrich each entry with full data via gh_search.

    Why: search-by-stars misses fresh AI tools that haven't crossed 5k yet but are trending today.
    Returns normalized repo dicts (same shape as gh_search output) with extra 'source' marker.
    """
    url = f"https://github.com/trending?since={since}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html_text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ! github trending scrape failed: {e}", file=sys.stderr)
        return []

    seeds = []
    seen = set()
    for art in re.findall(r'<article class="Box-row">(.+?)</article>', html_text, re.DOTALL):
        h2 = re.search(r'<h2[^>]*>\s*<a[^>]+href="/([^"]+)"', art)
        if not h2:
            continue
        name = h2.group(1).strip()
        # filter out sponsors/, apps/, and other non-repo paths
        parts = name.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            continue
        if name in seen:
            continue
        seen.add(name)
        lang_m = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        lang = (lang_m.group(1).strip() if lang_m else None) or "—"
        stars_m = re.search(r'([\d,]+)\s*</span>\s*</a>\s*</span>', art)
        stars = int(stars_m.group(1).replace(",", "")) if stars_m else 0
        desc_m = re.search(r'<p class="col-9[^"]*"[^>]*>(.+?)</p>', art, re.DOTALL)
        desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
        # ponytail: github shows "X stars today" — that's the literal 24h delta we want for /api/gain
        today_m = re.search(r'([\d,]+)\s*stars\s*today', art)
        stars_today = int(today_m.group(1).replace(",", "")) if today_m else None
        seeds.append({"name": name, "desc": desc, "stars": stars, "lang": lang, "stars_today": stars_today})
        if len(seeds) >= max_repos:
            break

    # Enrich each seed via gh_search to get topics + url + canonical desc.
    # repo:owner/name query returns just that one repo (if it exists); per_page=1 caps the call.
    out = []
    for s in seeds:
        try:
            hits = gh_search(f"repo:{s['name']}", per_page=1)
        except Exception:
            hits = []
        if hits:
            r = hits[0]
            r["source"] = "github_trending"
            # ponytail: gh_search returns the repo's *total* stars but not today's gain — carry over
            # the "X stars today" we parsed from the trending HTML so upsert_repos can persist it.
            r["stars_today"] = s.get("stars_today")
            out.append(r)
        else:
            # fallback: synthesize minimal dict (no topics → will fail is_ai_relevant, dropped)
            out.append({
                "name": s["name"], "url": f"https://github.com/{s['name']}",
                "desc": s["desc"], "stars": s["stars"], "forks": 0,
                "lang": s["lang"], "topics": [], "source": "github_trending",
                "stars_today": s.get("stars_today"),
                "updated": "", "pushed": "", "score": 0,
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
                if not is_ai_relevant(r):
                    continue
                top_5k_repos.setdefault(r["name"], r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}")

    top_5k_sorted = sorted(top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True)[:TOP_5K_LIMIT]
    print(f"  ✓ 5k+ pass: {len(top_5k_sorted)} repos after AI filter")

    # ponytail: manual seed — guaranteed inclusion of well-known AI tools that escape topic search
    for full_name in MANUAL_SEED_REPOS:
        if full_name in top_5k_repos:
            continue
        r = gh_fetch_repo(full_name)
        if not r or not is_ai_relevant(r):
            continue
        top_5k_repos[full_name] = r
        print(f"  ✓ manual seed: {full_name} ({r['stars']} ⭐)")

    # ponytail: GitHub trending — catches fresh AI tools with <5k stars that are hot today.
    # Pull BOTH daily and weekly — daily = today's buzz, weekly = rising stars the daily
    # doesn't yet show. Dedupe on name so a repo on both lists is counted once.
    print("[crawl] GitHub trending (daily + weekly)…")
    trending_daily = fetch_github_trending(since="daily", max_repos=30)
    trending_weekly = fetch_github_trending(since="weekly", max_repos=30)
    trending_seen, trending = set(), []
    for r in trending_daily + trending_weekly:
        if r["name"] in trending_seen:
            continue
        trending_seen.add(r["name"])
        trending.append(r)
    for r in trending:
        if r["name"] not in top_5k_repos:
            top_5k_repos[r["name"]] = r
    trending_ai = [r for r in trending if is_ai_relevant(r)]
    print(f"  ✓ trending: {len(trending_daily)} daily + {len(trending_weekly)} weekly → {len(trending)} unique → {len(trending_ai)} AI-relevant → merged into 5k+ pool")
    top_5k_sorted = sorted(top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True)[:TOP_5K_LIMIT]

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

    # ponytail: build flat deduped list of (cats ∪ 5k+); assign best_category; is_ai_relevant
    to_persist = []
    cat_pairs = []  # (repo_name, category_id) for repo_categories
    for cat in cat_results:
        for r in cat["repos"]:
            r["best_category"] = cat["id"]
            to_persist.append(r)
            cat_pairs.append((r["name"], cat["id"]))
    for r in top_5k_sorted:
        r["best_category"] = None  # 5k+ doesn't belong to a single category
        to_persist.append(r)
    seen = set()
    deduped = []
    for r in to_persist:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        r["is_ai_relevant"] = is_ai_relevant(r)
        deduped.append(r)

    # ponytail: translate once, cache forever — descriptions don't change day-to-day
    print("[crawl] translating to Chinese…")
    pairs = [(f"{r['name']}::desc", r.get("desc", "")) for r in deduped]
    zh = translate_batch(pairs)
    for r in deduped:
        r["desc_zh"] = zh.get(f"{r['name']}::desc", "") or r.get("desc_zh", "")
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = r["name"].split("/")[-1] in local

    # ponytail: write everything to Postgres in one transaction
    import db
    db.ensure_database()
    db.ensure_schema()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO crawl_log DEFAULT VALUES RETURNING id")
    crawl_id = cur.fetchone()[0]
    n_inserted, n_updated = db.upsert_repos(conn, deduped)
    db.replace_categories(conn, cat_pairs)
    db.snapshot_stars(conn, [r["name"] for r in deduped])
    # ponytail: trending flag is recomputed each crawl — clear stale, then set today's trending repos
    db.set_trending(conn, [r["name"] for r in trending_ai])
    cur.execute(
        "UPDATE crawl_log SET finished_at = NOW(), repos_seen = %s, repos_added = %s, repos_updated = %s WHERE id = %s",
        (len(deduped), n_inserted, n_updated, crawl_id),
    )
    conn.commit()
    conn.close()
    print(f"[crawl] saved → postgres ai_radar ({n_inserted} added, {n_updated} updated, {len(deduped)} unique this run)")
    return {"total_unique": len(deduped), "crawl_id": crawl_id}





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


def _installed_segments(local: dict) -> set:
    """Flatten detect_local_skills() output to a set of repo segment names.
    ponytail: the existing `name in local` check in crawl() was broken (local is a
    dict of dicts; `"foo" in {"skills": ...}` always False). This is the right shape."""
    segs = set()
    for kind in ("skills", "commands", "agents"):
        segs.update((local.get(kind) or {}).keys())
    for p in (local.get("plugins") or []):
        if p.get("name"):
            segs.add(p["name"].split("@")[0])
    return segs


def _annotate_local_installed(rows, installed_segments: set):
    """Single-pass walk: list → recurse; dict with 'repos' → descend; dict with 'name' → annotate leaf.
    ponytail: category dicts have BOTH `name` AND `repos`, so a `name`-first check would
    annotate the container instead of descending. Prefer the structural `repos` branch."""
    if isinstance(rows, list):
        for r in rows:
            _annotate_local_installed(r, installed_segments)
    elif isinstance(rows, dict):
        if "repos" in rows:
            _annotate_local_installed(rows["repos"], installed_segments)
        elif "name" in rows:
            rows["local_installed"] = rows["name"].split("/")[-1] in installed_segments


def serve(port=8765):
    """Pure JSON API server — Vite (5173) proxies /api/* here.
    Endpoints:
      GET  /api/data    → {hot_now, categories, fetched_at}
      GET  /api/local   → {skills, commands, agents, plugins, clis, ...}
      GET  /api/top     → paginated 1k+ star AI repos
      GET  /api/gain    → repos with star delta ≥ min_delta (24h / 7d)
      GET  /api/workbuddy → workbuddy picks
      POST /api/crawl   → spawn `radar.py crawl` in background
      POST /api/install → clone+symlink a skill
      POST /api/install-cli → wrap a CLI as slash command
      POST /api/local/origin → tag a command/agent/plugin with GitHub URL
      POST /api/local/replace → replace an installed skill with a stronger one
    """
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    class Handler(http.server.BaseHTTPRequestHandler):
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
                try:
                    conn = db.connect()
                    try:
                        hot = db.query_hot_now(conn, limit=40)
                        cats = db.query_categories(conn)
                    finally:
                        conn.close()
                except Exception as e:
                    return self._json({"error": f"db read failed: {e}"}, status=503)
                # ponytail: per-request annotation — the DB doesn't know what's installed locally
                segs = _installed_segments(detect_local_skills())
                _annotate_local_installed(hot, segs)
                _annotate_local_installed(cats, segs)
                return self._json({"hot_now": hot, "categories": cats, "fetched_at": datetime.datetime.now().isoformat()})
            if self.path == "/api/local":
                local = detect_local_skills()
                clis = detect_cli_tools()
                repos_idx = _load_repo_index()
                replacements = find_skill_replacements(local, repos_idx)
                return self._json({
                    "skills": local["skills"],
                    "commands": local["commands"],
                    "agents": local["agents"],
                    "plugins": local["plugins"],
                    "clis": clis,
                    "groups": group_capabilities_by_origin(local),
                    "replacements": replacements,
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
            if self.path == "/api/workbuddy":
                picks_path = DATA / "workbuddy_picks.json"
                picks = []
                if picks_path.exists():
                    try:
                        picks = json.loads(picks_path.read_text())
                    except (OSError, ValueError):
                        picks = []
                return self._json({"picks": picks, "count": len(picks)})
            if self.path.startswith("/api/top"):
                # ponytail: server-paginate from PG (was: read latest.json + slice client-side)
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
                try:
                    conn = db.connect()
                    try:
                        data = db.query_top_5k(conn, page=page, size=size, sort=sort)
                    finally:
                        conn.close()
                except Exception as e:
                    return self._json({"error": f"db read failed: {e}"}, status=503)
                _annotate_local_installed(data.get("repos"), _installed_segments(detect_local_skills()))
                return self._json(data)
            if self.path.startswith("/api/gain"):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                try:
                    min_delta = min(10000, max(0, int(qs.get("min_delta", ["100"])[0])))
                except ValueError:
                    min_delta = 100
                try:
                    page = max(1, int(qs.get("page", ["1"])[0]))
                except ValueError:
                    page = 1
                try:
                    size = min(48, max(1, int(qs.get("size", ["24"])[0])))
                except ValueError:
                    size = 24
                # ponytail: only 24h window — data source is repos.stars_today (from github.com/trending)
                prev_ago, recent_ago = "20 hours", "4 hours"
                try:
                    conn = db.connect()
                    try:
                        data = db.query_gain(conn, prev_ago=prev_ago, recent_ago=recent_ago,
                                              min_delta=min_delta, page=page, size=size)
                    finally:
                        conn.close()
                except Exception as e:
                    return self._json({"error": f"db read failed: {e}"}, status=503)
                _annotate_local_installed(data.get("gainers"), _installed_segments(detect_local_skills()))
                data["range"] = "24h"
                return self._json(data)
            # ponytail: pure API server — UI lives at :5173 (Vite). Anything else is 404.
            self.send_error(404)

        def do_POST(self):
            if self.path == "/api/local/replace":
                try:
                    body = self._read_body()
                    old_name = body.get("old", "").strip()
                    new_name = body.get("new", "").strip()
                    new_url = body.get("url", "").strip()
                    if not old_name or not new_name:
                        raise ValueError("old and new are required")
                    result = replace_skill(old_name, new_name, new_url)
                    self._json({"ok": True, "result": result, "message": f"已用 {new_name} 替换 {old_name}"})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
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
            if self.path == "/api/local/origin":
                try:
                    body = self._read_body()
                    kind = body.get("kind", "").strip()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    desc_zh = body.get("desc_zh", "").strip()
                    desc_en = body.get("desc_en", "").strip()
                    entry = set_capability_origin(kind, name, url, desc_zh, desc_en)
                    self._json({"ok": True, "entry": entry})
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl": crawl()
    elif cmd == "serve": serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "today": today()
    else:
        print(__doc__)
        sys.exit(1)