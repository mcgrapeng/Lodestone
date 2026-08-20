#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + JSON API for the Vue 3 frontend.

Commands:
  radar.py crawl   - fetch trending AI repos from GitHub, write to PG (fallback: data/latest.json)
  radar.py serve   - JSON API on http://localhost:PORT (loopback only; Vite at :5173 proxies /api/* here)
  radar.py today   - print today's top picks in terminal

Reuses `gh` CLI for GitHub auth (avoids token management).
Ponytail: minimum code, stdlib only, Vue UI lives in frontend/.
"""

import json
import subprocess
import sys
import os
import re
import datetime
import time
import http.server
import socketserver
import urllib.request
import urllib.parse
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
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
        "name": "Awesome Lists & Plugins & 资源合集",
        "desc": "精选列表、Claude/Codex 插件市场与插件、教程 — 发现新方向的入口",
        "queries": [
            "awesome-ai in:name stars:>500",
            "awesome-llm in:name stars:>500",
            "awesome-claude in:name stars:>200",
            "topic:claude-plugins stars:>50",
            "topic:claude-plugin stars:>50",
            "topic:claude-plugin-marketplace stars:>20",
            "claude plugins in:name,description stars:>100",
        ],
    },
    {
        "id": "mcp",
        "name": "MCP Servers & Clients",
        "desc": "Model Context Protocol — Claude/工具生态互联协议、服务端与客户端实现",
        "queries": [
            "topic:mcp-server stars:>100",
            "topic:mcp-servers stars:>100",
            "topic:model-context-protocol stars:>100",
            "mcp-server in:name,description stars:>100",
            "model context protocol in:name,description stars:>100",
            "mcp client in:name,description stars:>100",
        ],
    },
    {
        "id": "voice",
        "name": "Voice AI / Realtime",
        "desc": "语音对话、实时音视频、TTS/ASR、低延迟多模态应用（LiveKit / Pipecat / Vocode 系）",
        "queries": [
            "topic:livekit stars:>200",
            "topic:pipecat stars:>100",
            "topic:vocode stars:>100",
            "topic:realtime-ai stars:>100",
            "voice-agent in:name,description stars:>200",
            "realtime-voice in:name,description stars:>100",
        ],
    },
    {
        "id": "browser",
        "name": "Browser Use / Computer Use",
        "desc": "让 LLM 操作浏览器与桌面：浏览器自动化、视觉抓取、Computer-Use agent",
        "queries": [
            "topic:browser-use stars:>200",
            "topic:browser-automation stars:>500",
            "topic:computer-use stars:>100",
            "browser-use in:name,description stars:>200",
            "stagehand in:name stars:>500",
            "playwright-mcp in:name,description stars:>100",
        ],
    },
    {
        # ponytail: HuggingFace Trending Spaces — JSON API (huggingface.co/api/spaces?sort=trending).
        # Sources are populated by `fetch_huggingface_trending()` below, NOT GitHub queries;
        # queries list is kept empty so the standard loop skips it.
        "id": "huggingface",
        "name": "🤗 HuggingFace 热门",
        "desc": "HuggingFace Trending Spaces — 社区里最热门的 AI 应用 demo / agent / 工具",
        "queries": [],  # populated by fetch_huggingface_trending()
    },
]

# ponytail: 5k+ pass — broad queries to catch mainstream AI tools not in category queries
# ponytail: GitHub Search API 422s on `stars:>N topic:X OR topic:Y` (multi-topic OR). Each topic
# gets its own single-topic query. New repos are added slowly enough that 1 query per topic is
# fine — duplicates collapse in the `top_5k_repos` dict.
TOP_5K_QUERIES = [
    # ponytail: 关注 AI 应用开发, 不关注学术研究. 每个 query 一行 (GitHub API 422 on OR-combined).
    # 每个 query 最多 per_page=100, rate limit 30/min, sleep 2s 之间.
    # threshold stars:>500 而非 1000 — 大量有价值的应用工具 500-999 stars 之间, 不应漏.
    # === LLM 应用核心 ===
    "stars:>500 topic:llm",
    "stars:>500 topic:agent",
    "stars:>500 topic:agents",
    "stars:>500 topic:rag",
    "stars:>500 topic:vector-database",
    "stars:>500 topic:embeddings",
    "stars:>500 topic:prompt-engineering",
    "stars:>500 topic:function-calling",
    "stars:>500 topic:tool-use",
    # === Claude / Codex / MCP 生态 ===
    "stars:>500 topic:claude",
    "stars:>500 topic:claude-code",
    "stars:>500 topic:claude-skills",
    "stars:>500 topic:mcp",
    "stars:>500 topic:mcp-server",
    "stars:>500 topic:codex",
    "stars:>500 topic:codex-cli",
    # === AI Coding IDE / Agent / Tools (应用程序员核心关注) ===
    "stars:>500 topic:ai-coding",
    "stars:>500 topic:ai-coding-agent",
    "stars:>500 topic:ai-coding-tools",
    "stars:>500 topic:code-agent",
    "stars:>500 topic:copilot",
    "stars:>500 topic:cursor",
    "stars:>500 topic:cursor-ai",
    "stars:>500 topic:windsurf",
    "stars:>500 topic:aider",
    "stars:>500 topic:cline",
    "stars:>500 topic:continue-dev",
    "stars:>500 topic:ai-ide",
    # === Agent frameworks ===
    "stars:>500 topic:langchain",
    "stars:>500 topic:langgraph",
    "stars:>500 topic:llamaindex",
    "stars:>500 topic:autogen",
    "stars:>500 topic:crewai",
    "stars:>500 topic:smolagents",
    "stars:>500 topic:pydantic-ai",
    "stars:>500 topic:semantic-kernel",
    "stars:>500 topic:haystack",
    "stars:>500 topic:letta",
    # === Memory / RAG 应用 ===
    "stars:>500 topic:agent-memory",
    "stars:>500 topic:llm-memory",
    "stars:>500 topic:mem0",
    "stars:>500 topic:long-term-memory",
    "stars:>500 topic:knowledge-graph",
    "stars:>500 topic:graphrag",
    # === AI Gateway / Observability / Evaluation (生产工具) ===
    "stars:>500 topic:litellm",
    "stars:>500 topic:openrouter",
    "stars:>500 topic:llm-gateway",
    "stars:>500 topic:llm-router",
    "stars:>500 topic:langfuse",
    "stars:>500 topic:phoenix-arize",
    "stars:>500 topic:helicone",
    "stars:>500 topic:llmops",
    "stars:>500 topic:promptfoo",
    "stars:>500 topic:ragas",
    # === Workflow / Orchestration (应用基础设施) ===
    "stars:>500 topic:ai-workflow",
    "stars:>500 topic:workflow-orchestration",
    "stars:>500 topic:agentic-workflow",
    "stars:>500 topic:langflow",
    "stars:>500 topic:flowise",
    "stars:>500 topic:agentic-framework",
    "stars:>500 topic:multi-agent",
    "stars:>500 topic:agent-mesh",
    # === Local LLM / Inference (应用部署) ===
    "stars:>500 topic:ollama",
    "stars:>500 topic:vllm",
    "stars:>500 topic:llama-cpp",
    "stars:>500 topic:local-llm",
    # === Voice / Realtime (新方向) ===
    "stars:>500 topic:livekit",
    "stars:>500 topic:pipecat",
    "stars:>500 topic:vocode",
    "stars:>500 topic:realtime-ai",
    # === 学术 (低优先, 仅 2 个 query) ===
    "stars:>500 topic:fine-tuning",
    "stars:>500 topic:llm-evaluation",
    # === 文字兜底 (catch 没打 topic tag 的项目) ===
    'stars:>500 "AI agent" in:name,description',
    'stars:>500 "LLM app" in:name,description',
    'stars:>500 "Claude Code" in:name,description',
    'stars:>500 "MCP server" in:name,description',
    'stars:>500 "coding agent" in:name,description',
    'stars:>500 "agent framework" in:name,description',
    'stars:>500 "RAG" in:name,description',
    'stars:>500 "vector store" in:name,description',
    'stars:>500 "agent skill" in:name,description',
    # === Awesome 列表 (大量 curated resources, 但 topic 通用) ===
    "stars:>5000 awesome-llm in:name",
    "stars:>5000 awesome-ai in:name",
    "stars:>5000 awesome-claude in:name",
    "stars:>5000 awesome-agents in:name",
]
TOP_5K_LIMIT = 300

# ponytail: HARD AI topics — strict subset. Bare 'ai' is NOT here. Used to require a strong
# AI signal so non-AI repos with just an 'ai' topic (dbeaver, netdata) get filtered out.
AI_TOPIC_HARD = frozenset(
    {
        "llm",
        "llms",
        "gpt",
        "chatgpt",
        "openai",
        "anthropic",
        "claude",
        "claude-code",
        "gemini",
        "deepseek",
        "llama",
        "qwen",
        "mistral",
        "ollama",
        "vllm",
        "transformer",
        "transformers",
        "huggingface",
        "hugging-face",
        "autogen",
        "crewai",
        "langchain",
        "langgraph",
        "llamaindex",
        "rag",
        "embedding",
        "embeddings",
        "vector-database",
        "pgvector",
        "stable-diffusion",
        "comfyui",
        "diffusion-models",
        "text-to-image",
        "text-to-video",
        "image-generation",
        "image2image",
        "whisper",
        "tts",
        "speech-to-text",
        "speech-recognition",
        "voice-cloning",
        "voice-ai",
        "object-detection",
        "computer-vision",
        "nlp",
        "natural-language-processing",
        "artificial-intelligence",
        "copilot",
        "cursor-ai",
        "code-assistant",
        "ai-coding",
        "ai-coding-agent",
        "prompt-engineering",
        "agentic",
        "agentic-ai",
        "autonomous-agent",
        "multi-agent",
        "agent-skills",
        "ai-agent",
        "mcp-server",
        "spring-ai",
        "springai",
    }
)

# ponytail: text-level AI hints — checked in repo name + description when topic check fails.
# Bare ' ai ' (with spaces) catches "personal AI assistant" / "Build with AI" without matching
# 'ai-powered', 'email', 'main', etc.
AI_TEXT_HINTS = frozenset(
    {
        " ai ",
        " llm ",
        " gpt ",
        "chatgpt",
        "openai",
        "anthropic",
        "claude",
        "langchain",
        "huggingface",
        "stable-diffusion",
        "comfyui",
        "voice-cloning",
        "autogen",
        "crewai",
        "langgraph",
        "mcp-server",
        "mcp_server",
        "deepfake",
        "face swap",
        "face-swap",
        "generative",
        "neural network",
        "deep learning",
        "machine learning",
        "natural language",
        "computer vision",
        "object detection",
        "speech recognition",
        "speech-to-text",
        "speech to text",
        "coding agent",
    }
)

# ponytail: high-star noise that would otherwise sneak past the AI whitelist
AI_TOPIC_BLOCKLIST = frozenset(
    {
        "stock",
        "stocks",
        "trading",
        "crypto",
        "nft",
        "forex",
        "porn",
        "ai-porn",
        "ai-girlfriend",
        "adult-content",
        "astrology",
        "fortune-telling",
    }
)


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


TRANSLATE_CACHE = DATA / "zh_cache.json"


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


# ponytail: SKILL.md frontmatter description extractor — stops at next key, closing ---, or EOF
FRONTMATTER_DESC = re.compile(
    r"^description:\s*(.+?)(?=\n[a-z\-]+:|\n---|\Z)", re.MULTILINE | re.DOTALL
)


def translate_text(text, target="zh-CN"):
    """Google Translate free endpoint via urllib — zero deps. Returns '' on failure."""
    if not text or not text.strip():
        return ""
    try:
        params = urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "auto",
                "tl": target,
                "dt": "t",
                "q": text[:500],
            }
        )
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
            val = s[len("description:") :].strip()
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
            capture_output=True,
            text=True,
            timeout=15,
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


# ponytail: local-scan TTL cache — detect_local_skills() walks brew dirs + runs `uv tool list`
# + may hit `gh api` per unmatched skill. /api/* called it 2x per request → cache 60s,
# invalidated by any install/uninstall/origin mutation.
_LOCAL_SCAN_TTL = 60
_local_scan_cache: dict = {"ts": 0.0, "data": None}


def invalidate_local_scan():
    _local_scan_cache["ts"] = 0.0
    _local_scan_cache["data"] = None


def detect_local_skills(force: bool = False):
    """Scan all forms of installed Claude/Codex capabilities.
    Returns: {
      "skills":   {name: {claude, codex, url, desc_zh, desc_en, topics, stars, source}},
      "commands": {name: {claude}},
      "agents":   {name: {claude}},
      "plugins":  [{name, marketplace, version, install_path}],
    }
    Source priority: PG match → sidecar origin → SKILL.md frontmatter → none
    Cached for 60s — pass force=True to rescan (install/uninstall paths auto-invalidate).
    """
    now = time.time()
    if (
        not force
        and _local_scan_cache["data"] is not None
        and now - _local_scan_cache["ts"] < _LOCAL_SCAN_TTL
    ):
        return _local_scan_cache["data"]
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
    for label, d in [
        ("claude", Path.home() / ".claude" / "skills"),
        ("codex", Path.home() / ".codex" / "skills"),
    ]:
        if not d.exists():
            continue
        try:
            for entry in d.iterdir():
                if entry.name.startswith("."):
                    continue
                if not (entry.is_dir() or entry.is_symlink()):
                    continue
                meta = out["skills"].setdefault(
                    entry.name,
                    {
                        "claude": False,
                        "codex": False,
                        "url": None,
                        "desc_zh": None,
                        "desc_en": None,
                        "topics": [],
                        "stars": 0,
                        "source": "none",
                    },
                )
                meta[label] = True
        except OSError:
            pass

    # ponytail: enrich each skill with desc/url from 3 sources (priority: cache > origin > skillmd)
    for name, meta in out["skills"].items():
        if name in by_repo:
            r = by_repo[name]
            meta.update(
                {
                    "url": r.get("url"),
                    "desc_zh": r.get("desc_zh") or r.get("desc"),
                    "desc_en": r.get("desc"),
                    "topics": r.get("topics") or [],
                    "stars": r.get("stars") or 0,
                    "source": "cache",
                }
            )
        elif name in by_origin["skills"]:
            o = by_origin["skills"][name]
            meta["url"] = o.get("url")
            meta["source"] = "origin"
            # ponytail: installed skill not in our PG — fetch stars/topics live from GitHub so the source card shows real ⭐
            full = (
                f"{o.get('owner')}/{o.get('repo')}"
                if o.get("owner") and o.get("repo")
                else None
            )
            if full:
                gh = _gh_repo_meta(full)
                if gh:
                    meta["stars"] = gh.get("stars") or 0
                    meta["topics"] = gh.get("topics") or []
                    meta["desc_en"] = gh.get("description") or meta.get("desc_en")
                    meta["pushed_at"] = gh.get("pushed_at")
        else:
            for skills_root in [
                Path.home() / ".claude" / "skills",
                Path.home() / ".codex" / "skills",
            ]:
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
    to_translate = [
        (name, meta["desc_en"])
        for name, meta in out["skills"].items()
        if meta.get("desc_en") and not meta.get("desc_zh")
    ]
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
                elif src.get("source") == "git" and src.get("url"):
                    # ponytail: handle git-clone marketplace (e.g. claude-plugins-official) — strip .git suffix
                    u = src["url"]
                    if u.endswith(".git"):
                        u = u[:-4]
                    marketplace_urls[mp_name] = u
        except (OSError, ValueError):
            pass
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    # ponytail: read enabledPlugins from settings.json — only show actually-enabled plugins (skip disabled)
    enabled_set: set[str] = set()
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            s = json.loads(settings_path.read_text())
            for k, v in (s.get("enabledPlugins") or {}).items():
                if v is True:
                    enabled_set.add(k)
        except (OSError, ValueError):
            pass
    if plugins_file.exists():
        try:
            data = json.loads(plugins_file.read_text())
            for plugin_key, installs in (data.get("plugins") or {}).items():
                if enabled_set and plugin_key not in enabled_set:
                    continue  # ponytail: skip disabled plugins
                if "@" in plugin_key:
                    name, marketplace = plugin_key.split("@", 1)
                else:
                    name, marketplace = plugin_key, ""
                inst = (
                    max(installs, key=lambda i: i.get("installedAt", ""))
                    if installs
                    else {}
                )
                origin = plugin_origin_by_key.get(plugin_key, {})
                default_url = marketplace_urls.get(marketplace)
                out["plugins"].append(
                    {
                        "name": name,
                        "marketplace": marketplace,
                        "version": inst.get("version", ""),
                        "install_path": inst.get("installPath", ""),
                        "url": origin.get("url") or default_url,
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": origin.get("desc_en"),
                        "enabled": True,
                    }
                )
        except (OSError, ValueError, TypeError):
            pass

    # ponytail: MCP servers (context7 / chrome-devtools-mcp / etc) — settings.json mcpServers
    settings_file = Path.home() / ".claude" / "settings.json"
    if settings_file.exists():
        try:
            s = json.loads(settings_file.read_text())
            out["mcp_servers"] = sorted((s.get("mcpServers") or {}).keys())
        except (OSError, ValueError):
            pass

    # ponytail: CLI integrations grouped by installer — drives the "本机 CLI" card.
    out["clis"] = {}

    # brew binaries (symbolic links under /opt/homebrew/bin)
    brew_bin = Path("/opt/homebrew/bin")
    if brew_bin.exists():
        out["clis"]["brew"] = sorted(
            p.name
            for p in brew_bin.iterdir()
            if not p.name.startswith(".") and (p.is_file() or p.is_symlink())
        )

    # uv tools (parse `uv tool list` — first token per non-separator line)
    try:
        uv_out = subprocess.check_output(
            ["uv", "tool", "list"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        out["clis"]["uv"] = [
            line.strip().split()[0]
            for line in uv_out.splitlines()
            if line.strip() and not line.strip().startswith("-")
        ]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    # cargo extensions (cargo-* binaries in ~/.cargo/bin)
    cargo_bin = Path.home() / ".cargo" / "bin"
    if cargo_bin.exists():
        out["clis"]["cargo"] = sorted(
            p.name for p in cargo_bin.iterdir() if p.name.startswith("cargo-")
        )

    # Homebrew cask GUI apps in /Applications
    apps_dir = Path("/Applications")
    if apps_dir.exists():
        out["clis"]["cask"] = sorted(
            p.stem for p in apps_dir.iterdir() if p.suffix == ".app"
        )

    _local_scan_cache["ts"] = time.time()
    _local_scan_cache["data"] = out
    return out


def install_skill_from_github(name, url):
    """Clone GitHub repo to SKILLS_CACHE/<repo>, symlink to both skills dirs.
    Validates name as 'owner/repo'. Writes/updates sidecar at SKILL_ORIGINS.
    Idempotent. `url` is optional — if empty, derived from name."""
    if (
        not name
        or not all(c.isalnum() or c in "-_." for c in name.replace("/", ""))
        or ".." in name
    ):
        raise ValueError(f"invalid skill name: {name!r}")
    if "/" not in name:
        raise ValueError(f"skill name must be 'owner/repo': {name!r}")
    owner, repo = name.split("/", 1)
    if not all(c.isalnum() or c in "-_." for c in owner) or not all(
        c.isalnum() or c in "-_." for c in repo
    ):
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
            raise ValueError(
                f"url {url!r} does not match name {name!r} — refusing to clone mismatch"
            )

    target = (
        SKILLS_CACHE / f"{owner}__{repo}"
    )  # ponytail: namespace by owner to avoid collisions across different owners with same repo name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()[:200]}")

    for skills_root in [
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
    ]:
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

    invalidate_local_scan()
    return str(target)


def uninstall_skill(name: str) -> dict:
    """Remove a skill: unlink from ~/.claude/skills + ~/.codex/skills, drop cache dir, remove sidecar entry.
    Returns {removed_links: [paths], cache: path_or_null}."""
    if not name or not all(c.isalnum() or c in "-_." for c in name):
        raise ValueError(f"invalid skill name: {name!r}")
    removed = []
    for skills_root in [
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
    ]:
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
    invalidate_local_scan()
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
        sys.stderr.write(
            f"  [warn] replace: uninstall {old_name!r} failed ({e}); rolling back new install\n"
        )
        try:
            uninstall_skill(new_name)
        except Exception as e2:
            sys.stderr.write(
                f"  [ERROR] rollback also failed: {e2}; new still installed at {new_path}\n"
            )
        raise
    return {"new_path": new_path, "old_removed": removed}


# ponytail: generic topics every AI tool has — exclude from "same domain" matching so we don't
# falsely recommend hermes-agent as a replacement for graphify just because both have "claude-code".
# Threshold for "generic" = ≥5 repos in DB share this tag. Picked empirically; tighten if too noisy.
_GENERIC_TOPICS = frozenset(
    {
        # AI/agent meta
        "ai",
        "ai-agents",
        "ai-agent",
        "ai-tools",
        "agent",
        "agents",
        "agentic",
        "agentic-ai",
        "agentic-framework",
        "agentic-workflow",
        "llm",
        "llms",
        "large-language-models",
        "machine-learning",
        "deep-learning",
        "generative-ai",
        "genai",
        "rag",
        # RAG/embedding/data layer buzzwords — shared by every RAG-flavored repo, can't be anchors
        "graphrag",
        "knowledge-graph",
        "embedding",
        "embeddings",
        "vector-database",
        "pgvector",
        "gpt",
        "gpt-4",
        "openai-api",
        # vendor names (every Claude/Codex tool has these)
        "anthropic",
        "claude",
        "claude-code",
        "claude-ai",
        "codex",
        "openai",
        "chatgpt",
        "google",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
        "openclaw",
        # generic IDE/coding tool names
        "opencode",
        "antigravity",
        "kiro",
        "qoder",
        "trae",
        "windsurf",
        "windsurf-ai",
        "cursor",
        "cursor-ai",
        "copilot",
        "command-line",
        # scaffolding
        "skills",
        "agent-skills",
        "skill",
        "obra",
        "superpowers",
        "awesome",
        "awesome-list",
        "awesome-llm-apps",
        "awesome-claude-skills",
        "developer-tools",
        "devtools",
        "tools",
        "cli",
        # languages
        "python",
        "typescript",
        "javascript",
        "rust",
        "go",
        "ruby",
    }
)


def find_skill_replacements(
    local: dict, repos_by_segment: dict, min_anchors: int = 1, min_topic_repos: int = 1
) -> list[dict]:
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
    _RAG_FLAVORED_ANCHORS = frozenset(
        {
            "graphrag",
            "knowledge-graph",
            "rag",
            "vector-database",
            "embedding",
            "embeddings",
            "large-language-models",
            "llm-evaluation",
            "llm-memory",
            "agent-memory",
        }
    )
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
            score = (
                len(anchor_overlap) * 200
                + len(overlap) * 50
                + min(c_stars, 50000) // 100
            )
            reasons = [
                f"共享 vertical anchor：{', '.join(sorted(anchor_overlap))}",
                f"共 {len(overlap)} 个特定 topic：{', '.join(sorted(list(overlap))[:4])}",
                f"⭐ {c_stars:,}" + (f" vs 已装 {inst_stars:,}" if inst_stars else ""),
            ]
            if inst_cat and c_cat and inst_cat == c_cat:
                reasons.append(f"同领域：{inst_cat}")
            candidates.append(
                {
                    "name": r["name"],
                    "url": r["url"],
                    "stars": c_stars,
                    "topics": sorted(c_topics),
                    "desc_zh": r.get("desc_zh"),
                    "desc_en": r.get("description"),
                    "overlap": sorted(overlap),
                    "anchors": sorted(anchor_overlap),
                    "reasons": reasons,
                    "score": score,
                }
            )
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
            mode = (
                "replace"
                if (same_cat and strong_overlap and much_stronger)
                else "alongside"
            )
            out.append(
                {
                    "installed": {
                        "name": name,
                        "url": url,
                        "stars": inst_stars,
                        "topics": sorted(inst_topics),
                        "best_category": inst_cat,
                    },
                    "recommended": {**top, "best_category": top_cat},
                    "alternatives_count": len(candidates),
                    "mode": mode,
                }
            )
    out.sort(key=lambda x: x["recommended"]["score"], reverse=True)
    return out


def set_capability_origin(
    kind: str, name: str, url: str = "", desc_zh: str = "", desc_en: str = ""
):
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
    invalidate_local_scan()
    return bucket.get(name, {})


# ponytail: well-known AI/dev CLI tools worth surfacing to the user
KNOWN_CLIS = [
    "rtk",
    "gh",
    "docker",
    "kubectl",
    "helm",
    "terraform",
    "jq",
    "rg",
    "fd",
    "fzf",
    "tmux",
    "git",
    "curl",
    "ffmpeg",
    "aws",
    "gcloud",
    "az",
    "supabase",
    "vercel",
    "wrangler",
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
        (
            "skills",
            [(n, m) for n, m in (local.get("skills") or {}).items() if m.get("url")],
        ),
        (
            "commands",
            [(n, m) for n, m in (local.get("commands") or {}).items() if m.get("url")],
        ),
        (
            "agents",
            [(n, m) for n, m in (local.get("agents") or {}).items() if m.get("url")],
        ),
        (
            "plugins",
            [
                (f"{p['name']}@{p.get('marketplace', '')}", p)
                for p in (local.get("plugins") or [])
                if p.get("url")
            ],
        ),
    ]
    for kind, items in sources:
        for name, entry in items:
            url = entry.get("url")
            slug = _repo_slug_from_url(url)
            grp = bucket.setdefault(
                url,
                {
                    "url": url,
                    "slug": slug,
                    "name": slug,
                    "counts": {"skills": 0, "commands": 0, "agents": 0, "plugins": 0},
                    "items": [],
                },
            )
            grp["counts"][kind] += 1
            grp["items"].append(
                {
                    "type": kind,
                    "name": entry.get("name") or name,
                    "desc_en": entry.get("desc_en"),
                    "desc_zh": entry.get("desc_zh"),
                    "path": entry.get("path") or entry.get("install_path"),
                    "url": url,
                    "stars": entry.get("stars"),
                    "topics": entry.get("topics") or [],
                }
            )
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
            r = subprocess.run(
                ["which", tool], capture_output=True, text=True, timeout=2
            )
            if r.returncode != 0:
                continue
            path = r.stdout.strip()
            version = ""
            # ponytail: try common version flags, take first line of first successful output
            for flag in ["--version", "-version", "-V", "version"]:
                try:
                    vr = subprocess.run(
                        [path, flag], capture_output=True, text=True, timeout=2
                    )
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
        raise ValueError(
            f"command must be a single executable + safe args: {command!r}"
        )

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
    invalidate_local_scan()
    return str(target)


# ponytail: search failure counter — crawl() reads it to record data-quality signal in crawl_log
GH_SEARCH_STATS = {"failed": 0}
# ponytail: adaptive pacing — 2s baseline between search calls; bumped to 6s after a
# secondary-rate-limit hit so we stop burning 60s backoff sleeps. Resets per process.
_SEARCH_PACE = {"sleep": 2.0}


def _search_pace():
    time.sleep(_SEARCH_PACE["sleep"])


def gh_search(q, per_page=20):
    """Use gh CLI to search repos. Returns list of normalized repo dicts.
    ponytail: rate-limit recovery — sleep 60s + retry once on 403/secondary rate limit.
    Failures bump GH_SEARCH_STATS['failed'] so crawl() can report data quality."""
    cmd = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/repositories",
        "-f",
        f"q={q}",
        "-f",
        "sort=stars",
        "-f",
        "order=desc",
        "-f",
        f"per_page={per_page}",
    ]
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                break
            stderr = r.stderr.strip()
            # ponytail: GitHub secondary rate limit → wait 60s, retry once, then pace slower
            if attempt == 1 and (
                "rate limit" in stderr.lower()
                or "403" in stderr
                or "secondary" in stderr.lower()
            ):
                print(
                    f"  ⏳ rate-limit hit on q={q[:60]!r}; sleeping 60s then retrying",
                    file=sys.stderr,
                )
                _SEARCH_PACE["sleep"] = 6.0
                time.sleep(60)
                continue
            GH_SEARCH_STATS["failed"] += 1
            print(
                f"  ! gh api failed for q={q[:60]!r}: {stderr[:120]}", file=sys.stderr
            )
            return []
        except subprocess.TimeoutExpired:
            GH_SEARCH_STATS["failed"] += 1
            print(f"  ! gh api timeout (>60s) for q={q!r}", file=sys.stderr)
            return []
        except Exception as e:
            GH_SEARCH_STATS["failed"] += 1
            print(f"  ! gh search error: {e}", file=sys.stderr)
            return []
    else:
        GH_SEARCH_STATS["failed"] += 1
        return []

    out = []
    for item in data.get("items", []):
        out.append(
            {
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
            }
        )
    return out


# ponytail: hand-picked repos that escape topic/description search but are obvious AI tools
# (some maintainers never set topics, some are <5k stars at crawl time). Force-include on every
# crawl so the 5k+ view reflects what users actually expect to see.
MANUAL_SEED_REPOS = frozenset(
    {
        # User-curated 2026-07-21 list — these all slipped past TOP_5K_QUERIES at crawl time
        "Egonex-AI/Understand-Anything",  # knowledge-graph IDE (75k stars, claude-code topic)
        "lodestone/hallmark",  # anti-AI-slop design skill
        "Shubhamsaboo/awesome-llm-apps",  # 100+ AI agent apps (125k stars, generic topics)
        "stablyai/orca",  # desktop ADE for parallel coding agents (24k stars)
        "GaoSSR/best-claude-hud",  # Claude HUD plugin
        "lidge-jun/opencodex",  # universal LLM proxy for codex/claude-code
        "lodestone/ai-agent-book",  # 《深入理解 AI Agent》开源书
        "volcengine/OpenViking",  # ByteDance context DB for agents (27k stars)
        "msitarzewski/agency-agents",  # complete AI agency (135k stars, no topics)
        # Safety net
        "all-hands-ai/openhands",  # common 2025 coding agent
    }
)


def gh_fetch_repo(full_name):
    """Fetch a single repo's full metadata. Used for MANUAL_SEED_REPOS."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=30,
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


def fetch_huggingface_trending(max_items: int = 30) -> list:
    """HuggingFace Trending Spaces — JSON API (no auth). Returns repo-shaped dicts so the
    rest of the pipeline (translation, upsert, hot_now) works without special-casing.

    ponytail: HF's public API has no literal "trending" sort, but `sort=likes7d` returns
    `trendingScore` (their internal 7-day pop score). We surface that as `stars` so the
    rest of the UI / sorting treats HF spaces uniformly. `likes` becomes total likes (lifetime).

    Source: https://huggingface.co/api/spaces?sort=likes7d&limit=N (public JSON).
    Falls back to system `curl` when Python's SSL certs are missing (macOS Python builds
    commonly lack the cert chain). Returns [] on any error — HF down shouldn't block
    the GitHub crawl."""
    url = f"https://huggingface.co/api/spaces?sort=likes7d&limit={max_items}"
    data = None
    # ponytail: try Python urllib first (zero deps)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        # ponytail: macOS Python often lacks system certs — fall back to system `curl`
        # which uses the OS keychain. Public JSON API, no secrets at risk.
        try:
            out = subprocess.run(
                # ponytail: `-q` skips ~/.curlrc (which appends "HTTP %{http_code}…" that
                # would break json.loads on the captured stdout). Public API, no auth.
                ["curl", "-q", "-sS", "--max-time", "20", "-A", "lodestone/1.0", url],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if out.returncode == 0 and out.stdout.strip():
                data = json.loads(out.stdout)
            else:
                print(
                    f"  [warn] HF trending (curl) failed: {out.stderr.strip()[:120] or e}",
                    file=sys.stderr,
                )
                return []
        except Exception as e2:
            print(
                f"  [warn] HF trending fetch failed: {e}; curl: {e2}", file=sys.stderr
            )
            return []
    out = []
    # ponytail: HF API returns a list on success, a dict ({"error": "..."}) on rate-limit
    # / auth errors. Be defensive — only iterate if it's actually a list.
    items = data if isinstance(data, list) else []
    for s in items[:max_items]:
        sid = s.get("id") or ""
        if "/" not in sid:
            continue
        likes = int(s.get("likes") or 0)
        trend = int(s.get("trendingScore") or 0)
        # ponytail: trendingScore is what makes "trending" — surface as stars (UI badge
        # reads "⭐ N") and keep likes in topics as a secondary signal.
        out.append(
            {
                "name": sid,
                "full_name": sid,
                "url": f"https://huggingface.co/spaces/{sid}",
                "description": (s.get("description") or "").strip()[:500],
                "desc": (s.get("description") or "").strip()[:500],
                "stars": trend,  # 7-day trending score (UI displays as ⭐)
                "forks": 0,
                "lang": "python",  # most HF spaces are Gradio/Streamlit on Python
                "topics": ["huggingface", "space", *(s.get("tags") or [])][:6],
                "updated": (s.get("lastModified") or "")[:10],
                "pushed": (s.get("lastModified") or "")[:10],
                "score": trend,
                "best_category": "huggingface",
                "is_ai_relevant": True,  # HF trending is already AI-curated by the community
                "source": "huggingface_trending",
                "hf_likes": likes,  # kept for the drawer
            }
        )
    print(f"  ✓ HuggingFace: {len(out)} trending spaces", file=sys.stderr)
    return out


def fetch_recent_active_repos(max_repos: int = 30, days_back: int = 7) -> list:
    """Fallback for github.com/trending scrape — use gh search API by recent push + AI topics.
    ponytail: github.com/trending HTML is JS-rendered, urllib can't see the repo list. Use the
    search API instead: pushed:>N days ago + AI topic + stars sort. This gives us "recently
    active high-star AI repos", which is the closest proxy for trending.
    """
    # compute cutoff date
    import datetime as _dt

    cutoff = (_dt.date.today() - _dt.timedelta(days=days_back)).isoformat()
    queries = [
        f"stars:>500 pushed:>{cutoff} topic:ai",
        f"stars:>500 pushed:>{cutoff} topic:llm",
        f"stars:>500 pushed:>{cutoff} topic:claude-code",
        f"stars:>500 pushed:>{cutoff} topic:mcp-server",
    ]
    seen = set()
    out = []
    for q in queries:
        try:
            hits = gh_search(q, per_page=20)
        except Exception as e:
            print(f"  ! recent-active query failed: {q}: {e}", file=sys.stderr)
            continue
        for r in hits:
            n = r.get("name")
            if not n or n in seen:
                continue
            seen.add(n)
            r["source"] = "recent_active"
            r["stars_today"] = None  # we don't have a true daily delta
            out.append(r)
            if len(out) >= max_repos:
                break
        if len(out) >= max_repos:
            break
    return out


def fetch_github_trending(since: str = "daily", max_repos: int = 30):
    """Scrape github.com/trending and enrich each entry with full data via gh_fetch_repo.

    Why: search-by-stars misses fresh AI tools that haven't crossed 5k yet but are trending today.
    HTML sources, in order (see scrapers/ — optional real-browser engines ported from youzi):
      1. firecrawl → crawl4ai → playwright (JS-rendered DOM, any subset installed works)
      2. plain urllib (stdlib, original path)
      3. all failed → fetch_recent_active_repos (search-API proxy for trending)
    Returns normalized repo dicts (same shape as gh_search output) with extra 'source' marker.
    """
    url = f"https://github.com/trending?since={since}"
    html_text, engine = "", "none"
    # tier 1: real scrapers — optional package; missing/broken → urllib still works.
    # ponytail: strategy="parallel" — every available engine races under one wall-clock
    # deadline; the longest meaningful HTML wins. Lets fast engines short-circuit and
    # slow ones enrich when needed (firecrawl+crawl4ai+playwright complement each other
    # rather than stopping at the first success).
    try:
        from scrapers import fetch_html

        html_text, engine = fetch_html(url, strategy="parallel")
    except ImportError:
        pass
    # tier 2: stdlib urllib
    if not html_text:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html_text = (
                urllib.request.urlopen(req, timeout=30)
                .read()
                .decode("utf-8", errors="replace")
            )
            engine = "urllib"
        except Exception as e:
            print(
                f"  ! github trending scrape failed ({e}); falling back to recent-active search",
                file=sys.stderr,
            )
            return fetch_recent_active_repos(max_repos=max_repos)
    else:
        print(f"  · trending html via {engine}")

    seeds = []
    seen = set()
    for art in re.findall(
        r'<article class="Box-row">(.+?)</article>', html_text, re.DOTALL
    ):
        # ponytail: href can be relative (/owner/repo) OR absolute (https://github.com/owner/repo)
        # depending on which GitHub variant the engine was served — accept both
        h2 = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="(?:(?:https://github\.com)?/)?([^"]+)"', art
        )
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
        stars_m = re.search(r"([\d,]+)\s*</span>\s*</a>\s*</span>", art)
        stars = int(stars_m.group(1).replace(",", "")) if stars_m else 0
        desc_m = re.search(r'<p class="col-9[^"]*"[^>]*>(.+?)</p>', art, re.DOTALL)
        desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
        # ponytail: github shows "X stars today" — that's the literal 24h delta we want for /api/gain
        today_m = re.search(r"([\d,]+)\s*stars\s*today", art)
        stars_today = int(today_m.group(1).replace(",", "")) if today_m else None
        seeds.append(
            {
                "name": name,
                "desc": desc,
                "stars": stars,
                "lang": lang,
                "stars_today": stars_today,
            }
        )
        if len(seeds) >= max_repos:
            break

    # ponytail: engine returned a page the regex can't parse (layout change / bot-check page
    # served raw) — search-API proxy beats an empty trending list
    if not seeds:
        print(
            f"  ! trending page parsed to 0 repos (engine={engine}); using recent-active search",
            file=sys.stderr,
        )
        return fetch_recent_active_repos(max_repos=max_repos)

    # Enrich each seed via gh_fetch_repo (core API, 5000/hr) — NOT gh_search, which would
    # burn 60 search-rate-limit slots (30/min) and trip secondary limits.
    out = []
    for s in seeds:
        r = gh_fetch_repo(s["name"])
        if r:
            r["source"] = "github_trending"
            # ponytail: carry over the "X stars today" parsed from the trending HTML so
            # upsert_repos can persist the 24h delta.
            r["stars_today"] = s.get("stars_today")
            out.append(r)
        else:
            # fallback: synthesize minimal dict (no topics → will fail is_ai_relevant, dropped)
            out.append(
                {
                    "name": s["name"],
                    "url": f"https://github.com/{s['name']}",
                    "desc": s["desc"],
                    "stars": s["stars"],
                    "forks": 0,
                    "lang": s["lang"],
                    "topics": [],
                    "source": "github_trending",
                    "stars_today": s.get("stars_today"),
                    "updated": "",
                    "pushed": "",
                    "score": 0,
                }
            )
    return out


# ponytail: crawl 文件锁 — O_CREAT|O_EXCL 原子创建；>30min 视为崩溃残留可抢占。
# CLI 与 /api/crawl 共用，防止并发 crawl 互相触发 GitHub secondary rate limit。
CRAWL_LOCK = DATA / "crawl.lock"
CRAWL_LOCK_STALE_S = 30 * 60


def acquire_crawl_lock() -> bool:
    """True = acquired (caller must release); False = another crawl is running."""
    try:
        fd = os.open(CRAWL_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - CRAWL_LOCK.stat().st_mtime > CRAWL_LOCK_STALE_S:
                CRAWL_LOCK.unlink(missing_ok=True)
                return acquire_crawl_lock()
        except OSError:
            pass
        return False


def release_crawl_lock():
    CRAWL_LOCK.unlink(missing_ok=True)


def crawl_lock_held() -> bool:
    """Non-acquiring check for the API layer (returns 409 instead of spawning)."""
    if not CRAWL_LOCK.exists():
        return False
    try:
        if time.time() - CRAWL_LOCK.stat().st_mtime > CRAWL_LOCK_STALE_S:
            return False
    except OSError:
        return False
    return True


def crawl():
    """Fetch all categories, dedupe, save. File-locked — one crawl at a time."""
    if not acquire_crawl_lock():
        print("[crawl] another crawl is already running — aborting", file=sys.stderr)
        return {"ok": False, "error": "crawl already running"}
    try:
        return _crawl_inner()
    finally:
        release_crawl_lock()


def _crawl_inner():
    """Fetch all categories, dedupe, save."""
    today = datetime.date.today().isoformat()
    GH_SEARCH_STATS["failed"] = 0
    print(f"[crawl] {today} — {len(CATEGORIES)} categories")
    try:
        from scrapers import status as scraper_status

        avail = [k for k, v in scraper_status().items() if v]
        print(
            f"[crawl] scrapers: {', '.join(avail) if avail else 'none (urllib only)'}"
        )
    except ImportError:
        print("[crawl] scrapers: none (scrapers/ package missing; urllib only)")
    cat_results = []

    for cat in CATEGORIES:
        seen = set()
        repos = []
        # ponytail: empty `queries` = non-GitHub source category (e.g. HuggingFace). Skip the
        # gh_search loop and call the dedicated fetcher instead. Keeps the rest of the pipeline
        # (translation, hot_now, upsert, JSON snapshot) working uniformly.
        if not cat["queries"]:
            if cat["id"] == "huggingface":
                repos = fetch_huggingface_trending(max_items=30)
        else:
            for q in cat["queries"]:
                _search_pace()  # rate limit: 30 search req/min — adaptive sleep between ALL search calls
                for r in gh_search(q):
                    if r["name"] in seen:
                        continue
                    seen.add(r["name"])
                    repos.append(r)
        # sort by stars desc
        repos.sort(key=lambda x: x["stars"], reverse=True)
        repos = repos[:30]
        cat_results.append(
            {
                "id": cat["id"],
                "name": cat["name"],
                "desc": cat["desc"],
                "count": len(repos),
                "repos": repos,
            }
        )
        print(f"  ✓ {cat['name']}: {len(repos)} repos")

    # ponytail: 5k+ pass — catch mainstream AI tools not matched by category queries
    print(f"[crawl] 5k+ pass ({len(TOP_5K_QUERIES)} queries, sleep 2s between)...")
    top_5k_repos = {}
    for q in TOP_5K_QUERIES:
        _search_pace()  # rate limit: 30 req/min, adaptive after rate-limit hits
        try:
            for r in gh_search(q, per_page=100):
                if not is_ai_relevant(r):
                    continue
                top_5k_repos.setdefault(r["name"], r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}")

    print(f"  ✓ 5k+ pass: {len(top_5k_repos)} repos after AI filter")

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
    print(
        f"  ✓ trending: {len(trending_daily)} daily + {len(trending_weekly)} weekly → {len(trending)} unique → {len(trending_ai)} AI-relevant → merged into 5k+ pool"
    )
    # ponytail: keep trending SEPARATELY so the 300-row TOP_5K_LIMIT truncation below can't
    # drop their stars_today. Trending repos are low-star by definition (the whole point is
    # "new today" / "rising this week") — they'd otherwise be at the bottom of the 300-row slice.
    top_5k_sorted = sorted(
        top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True
    )[:TOP_5K_LIMIT]

    # Detect local skills — cached 60s; crawl marks which repos are already installed
    local = detect_local_skills()
    installed_skills = set((local.get("skills") or {}).keys())
    print(f"[crawl] local skills detected: {len(installed_skills)}")

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
    # ponytail: trending repos get stars_today which is the entire signal for /api/gain.
    # The TOP_5K_LIMIT=300 truncation above drops low-star trending repos — re-add them
    # so the stars_today field always reaches the DB / JSON snapshot.
    for r in trending_ai:
        if r["name"] not in {p["name"] for p in to_persist}:
            r["best_category"] = None
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
        r["local_installed"] = r["name"].split("/")[-1] in installed_skills

    failed = GH_SEARCH_STATS["failed"]
    if failed:
        print(
            f"  [warn] {failed} GitHub queries failed this run — data may be incomplete",
            file=sys.stderr,
        )

    # ponytail: write everything to Postgres in one transaction; ANY PG failure (pg8000
    # missing, PG down) falls back to JSON so /api/data + today() still work.
    import db

    if db._DB_OK:
        conn = None
        try:
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
                "UPDATE crawl_log SET finished_at = NOW(), repos_seen = %s, repos_added = %s,"
                " repos_updated = %s, queries_failed = %s WHERE id = %s",
                (len(deduped), n_inserted, n_updated, failed, crawl_id),
            )
            conn.commit()
            print(
                f"[crawl] saved → postgres ai_radar ({n_inserted} added, {n_updated} updated, {len(deduped)} unique this run)"
            )
            return {
                "total_unique": len(deduped),
                "crawl_id": crawl_id,
                "queries_failed": failed,
            }
        except Exception as e:
            print(
                f"  [warn] PG write failed ({e}); falling back to JSON snapshot",
                file=sys.stderr,
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    snapshot = {
        "date": datetime.date.today().isoformat(),
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_unique": len(deduped),
        "hot_now": sorted(deduped, key=lambda r: r.get("stars", 0), reverse=True)[:40],
        "categories": cat_results,
        # ponytail: stars_today carried over from trending scrape — /api/gain uses this when
        # no PG; previously empty because the field lived only on PG rows, not JSON snapshots.
        "stars_today": {
            r["name"]: r["stars_today"]
            for r in trending
            if r.get("stars_today") is not None
        },
    }
    latest_file = DATA / "latest.json"
    latest_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"[crawl] saved → {latest_file} ({len(deduped)} repos, JSON mode)")
    return {"total_unique": len(deduped), "fallback": "json", "queries_failed": failed}


def today():
    """Print today's top picks to terminal. PG first, latest.json fallback."""
    if db._DB_OK:
        try:
            conn = db.connect()
            try:
                hot = db.query_hot_now(conn, limit=15)
                cats = db.query_categories(conn)
            finally:
                conn.close()
            print(f"\n⚡ Lodestone · {datetime.date.today().isoformat()} · PG\n")
            print("🔥 Top 15 Hot Now:")
            for i, r in enumerate(hot, 1):
                print(
                    f"  {i:2}. {r['name']:<42} ⭐ {r['stars']:>6,}  {r.get('lang') or '—'}"
                )
                if r.get("description"):
                    print(f"      {r['description'][:90]}")
            print("\n📂 Categories:")
            for cat in cats:
                print(f"  · {cat['name']:<45} {cat['count']} repos")
            return
        except Exception as e:
            print(
                f"[today] PG read failed ({e}); falling back to latest.json",
                file=sys.stderr,
            )
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
    print("\n📂 Categories:")
    for cat in snap["categories"]:
        print(f"  · {cat['name']:<35} {cat['count']} repos")


def _installed_segments(local: dict) -> set:
    """Flatten detect_local_skills() output to a set of FULL owner/repo names.
    ponytail: use full names only — bare segments like "skills" cause false positives.
    Sources:
      1. local skills/commands/agents → wrap as 'local/<name>'
      2. plugin cache .git/config origin (when plugin was git-installed, e.g. obra/superpowers)
      3. plugin's marketplace source repo (when plugin lives in the marketplace repo,
         source is './' relative to marketplace — use marketplace URL as the source)
      4. known_marketplaces.json (covers the marketplace URL itself)
    """
    segs = set()
    for kind in ("skills", "commands", "agents"):
        for k in (local.get(kind) or {}).keys():
            segs.add(f"local/{k}")

    # ponytail: load marketplace source map once
    mp_source: dict[str, str] = {}
    known_mp = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if known_mp.exists():
        try:
            mp_data = json.loads(known_mp.read_text())
            for mp_name, info in (mp_data or {}).items():
                src = info.get("source") or {}
                repo = ""
                if src.get("source") == "github" and src.get("repo"):
                    repo = src["repo"]
                elif src.get("source") == "git" and src.get("url"):
                    u = src["url"].rstrip("/")
                    if u.endswith(".git"):
                        u = u[:-4]
                    repo = u.replace("https://github.com/", "").rstrip("/")
                if repo:
                    mp_source[mp_name] = repo
                    segs.add(repo)
        except (OSError, ValueError):
            pass

    # ponytail: each plugin's effective source repo = cache .git/config origin OR its marketplace URL
    for p in local.get("plugins") or []:
        mp_name = p.get("marketplace", "")
        ip = Path(p.get("install_path", ""))
        git_origin = None
        gc = ip / ".git" / "config"
        if gc.exists():
            try:
                for line in gc.read_text().splitlines():
                    m = re.match(
                        r"\s*url\s*=\s*(https?://github\.com/[^/]+/[^/]+?)(?:\.git)?\s*$",
                        line,
                    )
                    if m:
                        git_origin = (
                            m.group(1).replace("https://github.com/", "").rstrip("/")
                        )
                        break
            except OSError:
                pass
        if git_origin:
            segs.add(git_origin)
        elif mp_name in mp_source:
            segs.add(mp_source[mp_name])
    return segs


def _annotate_local_installed(rows, installed_segments: set, plugin_segs: set = None):
    """Single-pass walk: list → recurse; dict with 'repos' → descend; dict with 'name' → annotate leaf.
    ponytail: category dicts have BOTH `name` AND `repos`, so a `name`-first check would
    annotate the container instead of descending. Prefer the structural `repos` branch.
    ponytail: `plugin_segs` adds bare plugin-name segs (e.g. "ecc", "superpowers") so we
    match GitHub hot_now like `affaan-m/ECC` against the installed ecc plugin.
    """
    if isinstance(rows, list):
        for r in rows:
            _annotate_local_installed(r, installed_segments, plugin_segs)
    elif isinstance(rows, dict):
        if "repos" in rows:
            _annotate_local_installed(rows["repos"], installed_segments, plugin_segs)
        elif "name" in rows:
            full_lower = {s.lower() for s in installed_segments if "/" in s}
            name_lower = rows["name"].lower()
            seg_only = name_lower.split("/")[-1]
            seg_match = plugin_segs is not None and seg_only in plugin_segs
            rows["local_installed"] = name_lower in full_lower or seg_match


def _build_plugin_segs(local: dict) -> set:
    """Return bare plugin-name segs (e.g. 'ecc', 'superpowers') for hot_now seg matching.
    ponytail: plugin-name segs are specific enough (each Claude plugin has a unique name)
    that they don't need blacklist filtering — unlike 'skills' which would collide.
    """
    return {
        p["name"].split("@")[0].lower()
        for p in (local.get("plugins") or [])
        if p.get("name")
    }


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

        # ponytail: security — this server can clone repos into your skills dirs.
        # Browsers always send Origin on cross-origin POSTs, so a non-local Origin
        # header = another website trying drive-by installs → reject. Local curl /
        # same-origin Vite proxy send none and pass.
        def _origin_forbidden(self) -> bool:
            origin = (self.headers.get("Origin") or "").strip().lower()
            if not origin:
                return False
            return not origin.startswith(
                ("http://localhost", "http://127.0.0.1", "http://[::1]")
            )

        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
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
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            hot = db.query_hot_now(conn, limit=40)
                            cats = db.query_categories(conn)
                        finally:
                            conn.close()
                        # ponytail: per-request annotation — the DB doesn't know what's installed locally
                        local_sk = detect_local_skills()
                        segs = _installed_segments(local_sk)
                        plugin_segs = _build_plugin_segs(local_sk)
                        _annotate_local_installed(hot, segs, plugin_segs)
                        _annotate_local_installed(cats, segs, plugin_segs)
                        return self._json(
                            {
                                "hot_now": hot,
                                "categories": cats,
                                "fetched_at": datetime.datetime.now().isoformat(),
                            }
                        )
                    except Exception as e:
                        print(
                            f"  [warn] /api/data db read failed: {e}; falling back to data/latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — read latest.json (PG-unavailable mode or DB transient error)
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    hot = snap.get("hot_now") or []
                    cats = snap.get("categories") or []
                    local_sk = detect_local_skills()
                    segs = _installed_segments(local_sk)
                    plugin_segs = _build_plugin_segs(local_sk)
                    _annotate_local_installed(hot, segs, plugin_segs)
                    _annotate_local_installed(cats, segs, plugin_segs)
                    return self._json(
                        {
                            "hot_now": hot,
                            "categories": cats,
                            "fetched_at": snap.get("fetched_at"),
                        }
                    )
                return self._json(
                    {
                        "hot_now": [],
                        "categories": [],
                        "fetched_at": None,
                        "note": "no data — run ./radar.py crawl",
                    }
                )
            if self.path == "/api/local":
                local = detect_local_skills()
                legacy_clis = detect_cli_tools()
                repos_idx = _load_repo_index()
                replacements = find_skill_replacements(local, repos_idx)
                # ponytail: merge detect_local_skills clis (brew/uv/cargo/cask) with legacy 14 CLI list
                merged_clis = dict(legacy_clis)
                for group, items in (local.get("clis") or {}).items():
                    if not items:
                        continue
                    merged_clis[group] = (
                        items  # e.g. {"brew": [...834 names...], "uv": [...]}
                    )
                return self._json(
                    {
                        "skills": local["skills"],
                        "commands": local["commands"],
                        "agents": local["agents"],
                        "plugins": local["plugins"],
                        "clis": merged_clis,
                        "mcp_servers": local.get("mcp_servers") or [],
                        "groups": group_capabilities_by_origin(local),
                        "replacements": replacements,
                        "counts": {
                            "skills": len(local["skills"]),
                            "commands": len(local["commands"]),
                            "agents": len(local["agents"]),
                            "plugins": len(local["plugins"]),
                            "clis": sum(
                                len(v) if isinstance(v, list) else 1
                                for v in merged_clis.values()
                            ),
                            "mcp_servers": len(local.get("mcp_servers") or []),
                        },
                        "total": (
                            len(local["skills"])
                            + len(local["commands"])
                            + len(local["agents"])
                            + len(local["plugins"])
                            + sum(
                                len(v) if isinstance(v, list) else 1
                                for v in merged_clis.values()
                            )
                            + len(local.get("mcp_servers") or [])
                        ),
                    }
                )
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
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            data = db.query_top_5k(
                                conn, page=page, size=size, sort=sort
                            )
                        finally:
                            conn.close()
                        local_sk = detect_local_skills()
                        _annotate_local_installed(
                            data.get("repos"),
                            _installed_segments(local_sk),
                            _build_plugin_segs(local_sk),
                        )
                        return self._json(data)
                    except Exception as e:
                        print(
                            f"  [warn] /api/top db read failed: {e}; falling back to latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — paginate all repos from latest.json in-memory
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    all_repos = list(snap.get("hot_now") or []) + [
                        r
                        for c in (snap.get("categories") or [])
                        for r in c.get("repos") or []
                    ]
                    # dedupe by name, keep highest stars
                    by_name = {}
                    for r in all_repos:
                        n = r.get("name")
                        if not n:
                            continue
                        if n not in by_name or r.get("stars", 0) > by_name[n].get(
                            "stars", 0
                        ):
                            by_name[n] = r
                    # ponytail: pin MANUAL_SEED_REPOS to the front so they show up regardless of stars rank
                    # (lidge-jun/opencodex = 3264⭐ is in MANUAL_SEED but doesn't make top 48 by stars)
                    seen = set(by_name.keys())
                    pinned_first = []
                    for full_name in MANUAL_SEED_REPOS:
                        if full_name in seen:
                            pinned_first.append(by_name[full_name])
                            seen.discard(full_name)
                    rest = [r for k, r in by_name.items() if k in seen]
                    repos = pinned_first + sorted(
                        rest,
                        key=lambda r: r.get("stars", 0)
                        if sort == "stars"
                        else -(r.get("stars_today") or 0),
                        reverse=True,
                    )
                    total = len(repos)
                    start = (page - 1) * size
                    page_repos = repos[start : start + size]
                    local_sk = detect_local_skills()
                    _annotate_local_installed(
                        page_repos,
                        _installed_segments(local_sk),
                        _build_plugin_segs(local_sk),
                    )
                    return self._json(
                        {
                            "repos": page_repos,
                            "total": total,
                            "page": page,
                            "size": size,
                            "pages": max(1, (total + size - 1) // size),
                        }
                    )
                return self._json(
                    {"error": "no data — run ./radar.py crawl"}, status=503
                )
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
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            data = db.query_gain(
                                conn,
                                prev_ago=prev_ago,
                                recent_ago=recent_ago,
                                min_delta=min_delta,
                                page=page,
                                size=size,
                            )
                        finally:
                            conn.close()
                        local_sk = detect_local_skills()
                        _annotate_local_installed(
                            data.get("gainers"),
                            _installed_segments(local_sk),
                            _build_plugin_segs(local_sk),
                        )
                        data["range"] = "24h"
                        # ponytail: cold start — gain needs consecutive daily crawls (stars_today
                        # from trending + ≥20h of snapshots). Tell the user instead of an empty tab.
                        if not data.get("gainers"):
                            data["note"] = (
                                "暂无 24h 增长数据：需连续多天定时 crawl 积累 stars 快照，或当日 GitHub trending 页无 AI 项目。"
                            )
                        return self._json(data)
                    except Exception as e:
                        print(
                            f"  [warn] /api/gain db read failed: {e}; falling back to latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — compute gainers from latest.json stars_today.
                # Primary source: the top-level `stars_today` map (carried over from trending
                # scrape; populated even when category repos don't carry the field).
                # Secondary source: any per-repo `stars_today` on hot_now / category entries.
                # Tertiary fallback: recent_activity (pushed_at <7d proxy) so the tab is
                # never empty when there's at least fresh data.
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    today_map = dict(snap.get("stars_today") or {})
                    all_repos = list(snap.get("hot_now") or []) + [
                        r
                        for c in (snap.get("categories") or [])
                        for r in c.get("repos") or []
                    ]
                    # ponytail: index all repos by name so we can backfill desc/topics/etc
                    # for the trending repos that are only in today_map (not in any category).
                    by_name: dict = {}
                    for r in all_repos:
                        n = r.get("name")
                        if not n:
                            continue
                        if n not in by_name or r.get("stars", 0) > by_name[n].get(
                            "stars", 0
                        ):
                            by_name[n] = r
                    # ponytail: build gainers — every name with a positive stars_today wins.
                    gainers = []
                    for n, st in today_map.items():
                        if st <= 0:
                            continue
                        rec = by_name.get(n) or {
                            "name": n,
                            "stars": 0,
                            "topics": [],
                            "description": "",
                            "desc_zh": "",
                            "lang": "—",
                        }
                        gainers.append(
                            {
                                **rec,
                                "stars_today": st,
                                "delta_24h": st,
                                "source": "json_snapshot",
                            }
                        )
                    # ponytail: rank by delta desc, filter to AI-relevant / has topics.
                    # Fallback to recent_activity if today_map is empty.
                    if not gainers:
                        cutoff = (
                            datetime.date.today() - datetime.timedelta(days=7)
                        ).isoformat()
                        for r in all_repos:
                            pushed = r.get("pushed", "")
                            if pushed and pushed[:10] >= cutoff:
                                rec = dict(r)
                                rec["recent_activity"] = r.get("stars", 0)
                                gainers.append(rec)
                        if not gainers:
                            return self._json(
                                {
                                    "gainers": [],
                                    "total": 0,
                                    "page": page,
                                    "size": size,
                                    "pages": 1,
                                    "range": "24h",
                                    "note": "stars_today 与 recent_active 都缺失. 跑 `radar.py crawl` 补回.",
                                    "action": "crawl",
                                }
                            )
                    # ponytail: rank by delta desc, paginate, annotate local-installed
                    gainers.sort(
                        key=lambda r: -(
                            (r.get("delta_24h") or 0) + (r.get("recent_activity") or 0)
                        )
                    )
                    total = len(gainers)
                    start = (page - 1) * size
                    page_gainers = gainers[start : start + size]
                    local_sk = detect_local_skills()
                    _annotate_local_installed(
                        page_gainers,
                        _installed_segments(local_sk),
                        _build_plugin_segs(local_sk),
                    )
                    return self._json(
                        {
                            "gainers": page_gainers,
                            "total": total,
                            "page": page,
                            "size": size,
                            "pages": max(1, (total + size - 1) // size),
                            "range": "24h",
                            "note": None,
                        }
                    )
                return self._json(
                    {"error": "no data — run ./radar.py crawl"}, status=503
                )
            # ponytail: pure API server — UI lives at :5173 (Vite). Anything else is 404.
            self.send_error(404)

        def do_POST(self):
            if self._origin_forbidden():
                self._json({"ok": False, "error": "forbidden origin"}, status=403)
                return
            if self.path == "/api/local/replace":
                try:
                    body = self._read_body()
                    old_name = body.get("old", "").strip()
                    new_name = body.get("new", "").strip()
                    new_url = body.get("url", "").strip()
                    if not old_name or not new_name:
                        raise ValueError("old and new are required")
                    result = replace_skill(old_name, new_name, new_url)
                    self._json(
                        {
                            "ok": True,
                            "result": result,
                            "message": f"已用 {new_name} 替换 {old_name}",
                        }
                    )
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
                    self._json(
                        {"ok": True, "message": f"已创建 /{name} 命令", "path": path}
                    )
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
                # ponytail: file-lock guard — 409 instead of spawning a doomed subprocess
                if crawl_lock_held():
                    return self._json(
                        {"ok": False, "error": "crawl already running"}, status=409
                    )
                # ponytail: fire-and-forget background crawl so UI doesn't block
                subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "crawl"],
                    cwd=str(Path(__file__).parent.resolve()),
                    stdout=open(DATA / "crawl.log", "ab"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                return self._json(
                    {"ok": True, "message": "crawl started in background"}
                )
            self.send_error(404)

    # ponytail: bind loopback ONLY — this API can git-clone into your skills dirs;
    # exposing it to the LAN would let anyone on the network install skills.
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://localhost:{port}"
        print(
            f"[serve] {url}  (loopback only · API: /api/data /api/local /api/top /api/install /api/crawl · Ctrl-C to stop)"
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] stopped")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl":
        crawl()
    elif cmd == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "today":
        today()
    else:
        print(__doc__)
        sys.exit(1)
