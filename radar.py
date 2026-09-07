#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + JSON API for the Vue 3 frontend.

Commands:
  radar.py crawl   - fetch trending AI repos from GitHub, write to PG (fallback: data/latest.json)
  radar.py serve   - JSON API on http://localhost:PORT (loopback only; Vite at :5173 proxies /api/* here)
  radar.py web     - one-shot dashboard: start serve in background (if needed) + open browser
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

# ponytail: .env → os.environ（GH_TOKEN/GITHUB_TOKEN/JINA_API_KEY/FIRECRAWL_API_KEY）。
# gh CLI 原生识别 GH_TOKEN — 是 gh auth login 过期后的非交互替代。
try:
    from env_loader import load_env as _load_env

    _load_env()
except Exception:
    pass

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
            # 2026-09 用户赛道清单：Skills 生态 + 反AI味
            "topic:claude-skills stars:>20",
            "topic:agent-skills stars:>20",
            "skills-hub in:name stars:>50",
            "awesome-agent-skills in:name stars:>100",
            "topic:anti-slop stars:>20",
            "stop-slop in:name,description stars:>20",
            "hermes in:name topic:agent stars:>100",
            # 2026-09 生态地图：Agent SDK / 沙箱隔离
            "openai-agents in:name stars:>500",
            "topic:agent-sdk stars:>100",
            "topic:sandbox topic:agent stars:>100",
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
            # 2026-09 记忆/上下文深挖赛道
            "supermemory in:name stars:>100",
            "memvid in:name stars:>50",
            "topic:context-compression stars:>30",
            "deep-searcher in:name stars:>100",
            "khoj in:name stars:>1000",
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
            # 2026-09 用户赛道清单：内容创作管线
            "fish-speech in:name stars:>1000",
            "F5-TTS in:name stars:>1000",
            "ComfyUI in:name stars:>5000",
            "Fooocus in:name stars:>5000",
            "KrillinAI in:name stars:>500",
            "topic:video-translation stars:>100",
            # 2026-09 生态地图：语音线（中文第一梯队 + 实时对话）
            "FunASR in:name stars:>1000",
            "CosyVoice in:name stars:>1000",
            "LiveKit in:name stars:>1000",
            "topic:realtime-voice stars:>100",
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
            # 2026-09 生态地图「这类项目」：训练/微调/数据工程全方向
            "topic:deepspeed stars:>500",
            "unsloth in:name stars:>500",
            "axolotl in:name stars:>1000",
            "torchtune in:name stars:>500",
            "topic:dpo topic:llm stars:>100",
            "topic:synthetic-data stars:>200",
            "topic:knowledge-distillation topic:llm stars:>100",
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
            # 2026-09 生态地图：国内中转线
            "one-api in:name stars:>1000",
            "new-api in:name topic:llm stars:>500",
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
            # 2026-09 用户赛道清单：学习资源 / 教程 / 雷达
            "ai-agents-for-beginners in:name stars:>1000",
            "hello-agents in:name stars:>500",
            "dive-into-llms in:name stars:>100",
            "topic:llm-course stars:>100",
            "awesome-LLM-AIOps in:name stars:>50",
            "topic:ai-engineering stars:>100",
            "claude plugins in:name,description stars:>100",
        ],
    },
    {
        "id": "mcp",
        "name": "MCP Servers(官方注册表)",
        "desc": "Model Context Protocol 官方注册表 — registry.modelcontextprotocol.io 活跃服务端,按更新时间排序",
        # ponytail: 2026-09 P0 修复 — 旧定义同时挂 source + 9 条 queries,而分发条件是
        # `if not cat["queries"]` 才走 source 分支 → registry 抓取器永不可达(PG 0 行
        # registry 数据)。拆成两类:本类 registry 独占(0 星项不会被 GitHub 结果的
        # [:30] 星标截断挤掉),9 条 GitHub query 挪到 mcp_dev。
        "source": "mcp_registry",
        "queries": [],
    },
    {
        "id": "mcp_dev",
        "name": "MCP 开发与自托管",
        "desc": "MCP 客户端 / SDK / 自托管服务端与开发工具 — GitHub 生态侧(注册表之外)",
        "queries": [
            "topic:mcp-server stars:>100",
            "topic:mcp-servers stars:>100",
            "topic:model-context-protocol stars:>100",
            "topic:mcp-client stars:>50",
            "topic:claude-mcp stars:>50",
            "mcp-server in:name,description stars:>100",
            "model context protocol in:name,description stars:>100",
            "mcp client in:name,description stars:>50",
            "claude mcp in:name,description stars:>50",
        ],
    },
    {
        "id": "voice",
        "name": "Voice AI / Realtime",
        "desc": "语音对话、实时音视频、TTS/ASR、低延迟多模态应用（LiveKit / Pipecat / Vocode 系）",
        "queries": [
            "topic:livekit stars:>100",
            "topic:pipecat stars:>50",
            "topic:vocode stars:>50",
            "topic:realtime-ai stars:>50",
            "topic:voice-agent stars:>100",
            "topic:realtime-voice stars:>50",
            "topic:speech-ai stars:>100",
            "topic:openai-realtime stars:>50",
            "topic:gpt-realtime stars:>50",
            "topic:tts stars:>500",
            "topic:text-to-speech stars:>500",
            "topic:asr stars:>200",
            "voice-agent in:name,description stars:>100",
            "realtime-voice in:name,description stars:>50",
            "openai realtime in:name,description stars:>50",
            "voice ai in:name,description stars:>200",
        ],
    },
    {
        "id": "browser",
        "name": "Browser Use / Computer Use",
        "desc": "让 LLM 操作浏览器与桌面：浏览器自动化、视觉抓取、Computer-Use agent",
        "queries": [
            "topic:browser-use stars:>100",
            "topic:browser-automation stars:>500",
            "topic:computer-use stars:>50",
            "topic:web-automation-agent stars:>50",
            "topic:web-agent stars:>100",
            "browser-use in:name,description stars:>100",
            "computer use in:name,description stars:>50",
            "stagehand in:name stars:>200",
            "playwright-mcp in:name,description stars:>50",
            "browser-mcp in:name,description stars:>50",
            "stagehand-mcp in:name,description stars:>20",
        ],
    },
    {
        # ponytail: HuggingFace Trending Spaces — JSON API (huggingface.co/api/spaces?sort=trending).
        # Sources are populated by `fetch_huggingface_trending()` below, NOT GitHub queries;
        # queries list is kept empty so the standard loop skips it.
        "id": "huggingface",
        "name": "🤗 HuggingFace 热门 Spaces",
        "desc": "HuggingFace Trending Spaces — 社区里最热门的 AI 应用 demo / agent / 工具",
        "queries": [],  # populated by fetch_huggingface_trending()
        "source": "hf_spaces",
    },
    {
        # ponytail: 2026-08 — HuggingFace Trending Models (vs existing Spaces).
        # JSON API (huggingface.co/api/models?sort=likes7d). New category separate
        # from Spaces so the UI can show both — model weights are a distinct signal.
        "id": "hf_models",
        "name": "🤗 HuggingFace 热门 Models",
        "desc": "HuggingFace Trending Models — 7 天 likes 排行（Qwen / Llama / DeepSeek 等）",
        "queries": [],  # populated by fetch_huggingface_models_trending()
        "source": "hf_models",
    },
    {
        # ponytail: 2026-09 — arXiv 最新 AI 论文（官方 Atom API，无 key）。
        # cs.AI / cs.CL / cs.LG 按提交时间倒序；论文没有星标，排序靠提交时间戳。
        "id": "arxiv",
        "name": "📄 arXiv 论文",
        "desc": "最新 AI 研究 — cs.AI / cs.CL / cs.LG 按提交时间（官方 API，非爬取）",
        "queries": [],  # populated by fetch_arxiv_recent()
        "source": "arxiv",
    },
    {
        # ponytail: 2026-09 — 用户生态地图补齐：AI 工程全生命周期方向。
        "id": "inference",
        "name": "⚙️ 推理服务与部署",
        "desc": "vLLM / SGLang / Ollama / LocalAI / Xinference — 模型自部署与推理框架",
        "queries": [
            "topic:vllm stars:>100",
            "topic:sglang stars:>100",
            "topic:localai stars:>100",
            "xinference in:name stars:>500",
            "topic:llm-serving stars:>100",
            "topic:inference-server stars:>100",
        ],
    },
    {
        # ponytail: 2026-09 — 用户赛道清单：代码理解 / 知识图谱。
        "id": "codekg",
        "name": "🕸 代码理解与知识图谱",
        "desc": "codegraph / gitingest / GitNexus / graphify — 代码库的结构化理解与检索",
        "queries": [
            "codegraph in:name stars:>100",
            "gitingest in:name stars:>500",
            "GitNexus in:name stars:>100",
            "graphify in:name stars:>100",
            "topic:code-knowledge-graph stars:>20",
            "Understand-Anything in:name stars:>100",
            "topic:code-intelligence topic:llm stars:>100",
        ],
    },
    {
        "id": "searchweb",
        "name": "🔍 搜索与数据获取",
        "desc": "SearXNG / Firecrawl / Crawl4AI / Browser-Use — agent 的联网与抓取手脚",
        "queries": [
            "topic:searxng stars:>500",
            "firecrawl in:name stars:>500",
            "crawl4ai in:name stars:>300",
            "topic:web-crawler topic:llm stars:>100",
            "topic:browser-automation topic:ai stars:>200",
            # 2026-09 用户赛道清单
            "AnyCrawl in:name stars:>100",
            "scrapling in:name stars:>500",
            "TrendRadar in:name stars:>100",
        ],
    },
    {
        "id": "chatui",
        "name": "💬 聊天前端",
        "desc": "LobeChat / Open WebUI / LibreChat — 自部署模型的成品 UI",
        "queries": [
            "topic:lobechat stars:>500",
            "open-webui in:name stars:>2000",
            "librechat in:name stars:>1000",
            "topic:chatbot-ui stars:>300",
            "topic:llm-ui stars:>100",
            "Kotaemon in:name stars:>500",
            "AnythingLLM in:name stars:>5000",
        ],
    },
    {
        "id": "docparse",
        "name": "📄 文档解析",
        "desc": "MinerU / Docling / Unstructured — PDF→Markdown，RAG 的前置环节",
        "queries": [
            "MinerU in:name stars:>1000",
            "docling in:name stars:>1000",
            "unstructured in:name stars:>3000",
            "topic:document-parsing stars:>200",
            "topic:pdf topic:markdown topic:llm stars:>100",
            # 2026-09 用户赛道清单：翻译线 + OCR
            "marker in:name topic:pdf stars:>1000",
            "BabelDOC in:name stars:>100",
            "PDFMathTranslate in:name stars:>500",
            "LibreTranslate in:name stars:>1000",
            "topic:ocr stars:>200 topic:document",
        ],
    },
    {
        "id": "aiui",
        "name": "🎨 AI UI 组件库",
        "desc": "assistant-ui / CopilotKit / AI Elements / Streamdown — 聊天界面与流式渲染组件",
        "queries": [
            "assistant-ui in:name stars:>500",
            "copilotkit in:name stars:>1000",
            "topic:ai-sdk stars:>300",
            "topic:ai-chatbot topic:react stars:>200",
            "streamdown in:name stars:>300",
        ],
    },
    {
        "id": "security",
        "name": "AI 安全 & 隐私",
        "desc": "Prompt injection 防御、LLM 红队 / Jailbreak 检测、PII 脱敏、模型水印、对齐研究",
        "queries": [
            "topic:prompt-injection stars:>50",
            "topic:llm-security stars:>50",
            "topic:ai-safety stars:>100",
            "topic:red-team stars:>50",
            "topic:ai-alignment stars:>100",
            "topic:llm-firewall stars:>20",
            "topic:prompt-guard stars:>20",
            "topic:ai-guardrails stars:>50",
            "topic:watermark-llm stars:>20",
            "prompt injection in:name,description stars:>50",
            "jailbreak in:name,description stars:>50",
            "llm firewall in:name,description stars:>20",
            "ai guardrails in:name,description stars:>50",
            "model safety in:name,description stars:>100",
        ],
    },
    {
        "id": "robotics",
        "name": "机器人 / Embodied AI",
        "desc": "具身智能、机器人控制、sim-to-real、Open X-Embodiment、机器人学习框架",
        "queries": [
            "topic:embodied-ai stars:>100",
            "topic:robotics stars:>200",
            "topic:robot-learning stars:>100",
            "topic:sim-to-real stars:>50",
            "topic:open-x-embodiment stars:>20",
            "topic:humanoid-robot stars:>50",
            "topic:robot-manipulation stars:>50",
            "topic:vla-model stars:>20",
            "topic:vision-language-action stars:>20",
            "humanoid in:name,description stars:>100",
            "manipulation in:name,description stars:>100",
            "embodied agent in:name,description stars:>50",
            "robot foundation model in:name,description stars:>20",
        ],
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
# ponytail: 2026-09 P1 修复 — 300 时每天只有星标 top300 能入 PG,5k 池"跨天累积"
# 的补偿机制被截断卡死(51-100 名、500-1500 星的大量项目永远进不了库)。
# 800 让 stars:>500 的 unique 几乎全量入库;抓取量不变(数据本就抓回来了,
# 只是不再丢),仅 upsert 行数与首次翻译量增加(有缓存)。
TOP_5K_LIMIT = 800

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
        # ponytail: 2026-09 补齐 topics 变体 — 分类结果启用完整过滤后
        # 这些变体缺了会误伤正经 AI 项目（Qwen-VL / playwright-mcp 实测踩过）
        "mcp",
        "mcp-client",
        "mcp-servers",
        "model-context-protocol",
        "large-language-model",
        "large-language-models",
        "vision-language-model",
        "vision-language-models",
        "vlm",
        "chatbot",
        "chat-bot",
        "ai-chatbot",
        "generative-ai",
        "ai-framework",
        "ai-sdk",
        "ai-agents",
        "ai-applications",
        "local-llm",
        "llm-inference",
        "llama-cpp",
        "text-generation",
        "fine-tuning",
        "fine-tuning-framework",
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
        # ponytail: 2026-09 — lit-llama 这类空 topics 项目的描述信号。
        # 注意不加 "multimodal"：数据工程的 SeaTunnel 描述里有 "multimodal"
        # （数据模态≠AI多模态），实测误伤。
        "language model",
        ".agents",
    }
)

# ponytail: 2026-09 — 用户精选赛道白名单：这些项目（agent 基建/记忆/爬虫手脚/
# 内容管线）topics 不含 AI 关键词但属于雷达定位内的基础设施，跳过严格 AI 过滤。
CURATED_ALLOWLIST = frozenset(
    {
        # 注意：查询方对 repo name 做 lower() 比对 — 此处必须全小写
        # （曾因 "VoltAgent/..." 大小写不一致导致白名单永不命中）
        "d4vinci/scrapling",
        "lllyasviel/fooocus",
        "letta-ai/letta",
        "supermemoryai/supermemory",
        "memvid/memvid",
        "labring/fastgpt",
        "funstory-ai/babeldoc",
        "swivid/f5-tts",
        "coderamp-labs/gitingest",
        "lordog/dive-into-llms",
        "voltagent/awesome-agent-skills",
        "libretranslate/libretranslate",
        "yt-dlp/yt-dlp",
    }
)

# ponytail: high-star noise that would otherwise sneak past the AI whitelist
# 2026-09：按产品定位收紧 — 只收「AI 应用开发」类项目，股票/金融/交易类
# 即使是 AI 驱动的（如 multi-agent trading framework）也不收。
AI_TOPIC_BLOCKLIST = frozenset(
    {
        "stock",
        "stocks",
        "stock-market",
        "stock-prediction",
        "stock-analysis",
        "trading",
        "trading-bot",
        "tradingview",
        "algorithmic-trading",
        "quantitative-finance",
        "quant-trading",
        "quantconnect",
        "backtesting",
        "finance",
        "fintech",
        "investment",
        "investing",
        "portfolio-optimization",
        "crypto",
        "cryptocurrency",
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

# ponytail: 描述级金融领域短语（精确匹配，避免误伤 quantization/quantum 等 AI 术语）。
# 命中即排除 — TradingAgents/FinRobot 这类「AI 驱动但领域是金融」的项目从这里拦下。
NON_AI_DEV_DESC_BLOCKLIST = re.compile(
    r"(?:trading\s+(?:bot|agent|framework|strategy|system|platform)"
    r"|stock\s+(?:market|price|prediction|trading|analysis)"
    r"|algorithmic\s+trading|quantitative\s+finance|financial\s+market"
    r"|股票|炒股|量化交易|证券|金融行情)",
    re.IGNORECASE,
)


def is_finance_blocked(repo):
    """股票/金融/交易领域检测（topic 精确匹配 + 描述短语匹配）。
    产品定位 = AI 应用开发雷达：这类项目即使 AI 驱动（如 multi-agent trading
    framework）也一律排除。所有来源（分类查询 / 5k 池 / trending）都适用。"""
    topics = [t.lower() for t in (repo.get("topics") or [])]
    if any(t in AI_TOPIC_BLOCKLIST for t in topics):
        return True
    desc = repo.get("description") or repo.get("desc") or ""
    return bool(NON_AI_DEV_DESC_BLOCKLIST.search(desc))


def is_ai_relevant(repo):
    """Strict AI filter — requires at least one HARD topic, OR an AI phrase in name/description.
    ponytail: bare 'ai' topic alone is no longer enough — that caught dbeaver/netdata.
    2026-09：先过金融领域屏蔽（is_finance_blocked），再做 AI 判定。
    注意：分类查询的结果不要用这个函数整体过滤 — category query 本身就是 AI
    信号（topic:llm / topic:langgraph...），只需 is_finance_blocked；严格过滤
    用于来源宽泛的 5k 大池（"stars:>500 xxx" 这类）。"""
    if is_finance_blocked(repo):
        return False
    # ponytail: 用户精选赛道白名单（CURATED_ALLOWLIST 在上方定义）— agent 基建类
    # 项目 topics 无 AI 关键词但属于雷达定位，豁免 AI 相关性判定（金融拦截不豁免）。
    if (repo.get("name") or "").lower() in CURATED_ALLOWLIST:
        return True
    topics = [t.lower() for t in (repo.get("topics") or [])]
    blob_topics = " ".join(topics)
    if any(h in blob_topics for h in AI_TOPIC_HARD):
        return True
    # fallback: name + description must contain a strong AI phrase
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or repo.get("desc") or "").lower()
    text = f" {name} {desc} "
    return any(h in text for h in AI_TEXT_HINTS)


def normalize_git_url(url):
    """去重键：git 仓库地址规范化 — 小写、去 www/.git/尾斜杠，GitHub 归一为 gh://owner/repo。
    任何开源项目一定有 GitHub 地址；非 GitHub（HF/arXiv/registry）原样小写规范化。
    同一仓库的大小写变体（gh://Owner/Repo vs gh://owner/repo）归并为同一个键。"""
    u = (url or "").strip().lower()
    u = re.sub(r"\.git$", "", u).rstrip("/")
    return re.sub(r"^https?://(www\.)?github\.com/", "gh://", u)


TRANSLATE_CACHE = DATA / "zh_cache.json"


_LANG_NAV_WORDS = (
    "English", "Português", "简体中文", "繁体中文", "日本語", "日本语",
    "한국어", "Türkçe", "Русский", "Français", "Deutsch", "Español", "Tiếng Việt",
    # 翻译后的语言名（缓存里的中文版语言行）
    "英语", "葡萄牙语", "日语", "韩语", "土耳其语", "俄语", "法语", "德语", "西班牙语",
)


def _clean_readme_text(md: str, max_chars: int = 600) -> str:
    """README → 干净摘要文本。
    处理真实 README 的脏开头：徽章/语言切换表/导航链接往往占据前几百字符。
    ① 去图片/链接/标题标记/强调/代码标记；② 跳过语言导航段；③ 取第一个 ≥40 字符的实质段落。"""
    if not md:
        return ""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)          # 图片
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)        # 链接 → 文本
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)           # 标题标记
    s = re.sub(r"<[^>]+>", " ", s)                          # HTML 标签（徽章）
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"[`<>|]", " ", s)
    # GFM 警告标记 [!WARNING]/[!警告] 与语言切换括号 [ En 中 Fr 日 ] — 去前缀保留正文
    s = re.sub(
        r"^\s*\[\s*[!！]?\s*(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION|注意|重要|警告|提示)\s*\]\s*",
        "", s, flags=re.M,
    )
    s = re.sub(r"^\s*\[[^\]\n]{0,24}\]\s+(?=\S)", "", s)
    # 段落级选择：跳过徽章/语言行/短导航，取第一个有实质内容的段落
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", s)]
    for p in paragraphs:
        if len(p) < 40:
            continue
        lang_words = sum(1 for w in _LANG_NAV_WORDS if w in p)
        if p.startswith("Language:") or p.startswith("语言") or lang_words >= 3:
            # 语言表与正文并成一段（缓存翻译常见）→ 从最后一个语言词之后截断
            if lang_words >= 3:
                cut = 0
                for w in _LANG_NAV_WORDS:
                    i = p.rfind(w)
                    if i >= 0:
                        cut = max(cut, i + len(w))
                body = p[cut:].lstrip(" |·>—-：:]）)")
                if len(body) >= 40:
                    return body[:max_chars]
            continue
        return p[:max_chars]
    # 全部段落都像导航/太短 → 取最长的一段（正文段几乎总是最长的）
    return (max(paragraphs, key=len) if paragraphs else "")[:max_chars]


def _summary_from_entry(entry: dict, limit: int = 240) -> str:
    """从 readme_zh 缓存条目取摘要 — 句子边界截断，不切半句。"""
    text = _clean_readme_text(entry.get("text") or "", max_chars=limit + 60)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "！", "？", "；", ". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + len(sep)].strip()
    return cut.rsplit(" ", 1)[0].strip()


def _build_summary_zh(repo: dict, cache: dict) -> None:
    """为单个 repo 生成 summary_zh（详细中文描述）。
    缓存命中 → 直接截取；未命中 → 拉 README 首段翻译并写回 cache。
    非 GitHub 条目（HF/arXiv/MCP）用 desc_zh 兜底。失败静默降级。"""
    full_name = repo.get("name") or ""
    fallback = repo.get("desc_zh") or repo.get("desc") or ""
    url = repo.get("url") or ""
    if "/" not in full_name or "github.com" not in url:
        repo["summary_zh"] = fallback
        return
    key = full_name.lower()
    entry = cache.get(key)
    if entry and entry.get("text"):
        summary = _summary_from_entry(entry)
        # 缓存里是英文残留（旧抽屉时代翻译失败的原样缓存）→ 视为未命中重做
        if summary and any("一" <= ch <= "鿿" for ch in summary[:60]):
            repo["summary_zh"] = summary
            return
        cache.pop(key, None)
    fetched = _fetch_readme_from_github(full_name)
    if not fetched:
        repo["summary_zh"] = fallback
        return
    raw_md, source_url = fetched
    clean = _clean_readme_text(raw_md)
    zh = _chunked_translate(clean) if clean else ""
    if zh and _looks_translated(zh, clean):
        cache[key] = {
            "text": zh,
            "source_url": source_url,
            "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "translator": "google-translate-free",
        }
        repo["summary_zh"] = _summary_from_entry(cache[key]) or fallback
    else:
        # 翻译失败不缓存、不展示英文 — 回退中文简介
        repo["summary_zh"] = fallback


def enrich_summaries(repos: list, max_workers: int = 4) -> int:
    """爬取期为全部 repos 生成详细中文描述（summary_zh）。
    README 拉取 + 翻译 4 线程并发；缓存读写只做一次（整文件）。
    返回生成数量。任何失败不阻塞爬取主流程。"""
    cache: dict = {}
    if README_ZH_CACHE.exists():
        try:
            cache = json.loads(README_ZH_CACHE.read_text())
        except Exception:
            cache = {}
    github_repos = [
        r for r in repos if "github.com" in (r.get("url") or "")
    ]
    print(
        f"[crawl] summaries: {len(github_repos)} GitHub repos "
        f"({sum(1 for r in github_repos if cache.get((r['name'] or '').lower(), {}).get('text'))} cached)"
    )
    lock_free_cache = cache  # dict set/get 在 GIL 下线程安全
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(lambda r: _build_summary_zh(r, lock_free_cache), github_repos))
    # 非 GitHub 条目直接补 desc_zh
    for r in repos:
        if not r.get("summary_zh"):
            r["summary_zh"] = r.get("desc_zh") or r.get("desc") or ""
    try:
        README_ZH_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1)
        )
    except Exception as e:
        print(f"  [warn] summary cache write failed: {e}", file=sys.stderr)
    return sum(1 for r in repos if r.get("summary_zh"))


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
    """Google Translate free endpoint via urllib, falling back to system `curl` when
    Python's SSL cert chain is missing (common on macOS Python builds). Returns '' on failure."""
    if not text or not text.strip():
        return ""
    params = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "auto",
            "tl": target,
            "dt": "t",
            "q": text[:500],
        }
    )
    url = f"https://translate.googleapis.com/translate_a/single?{params}"
    # ponytail: try urllib first (zero deps); fall back to system curl which
    # uses the OS keychain and avoids macOS Python's missing-cert issue.
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        result = "".join(seg[0] for seg in data[0] if seg and seg[0])
        if result:
            return result
    except Exception:
        pass
    try:
        out = subprocess.run(
            [
                "curl", "-q", "-sS", "--max-time", "10",
                "-A", "Mozilla/5.0", url,
            ],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            result = "".join(seg[0] for seg in data[0] if seg and seg[0])
            return result
    except Exception:
        pass
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


# ponytail: 2026-08 — comprehensive Chinese README translation cache.
# Keyed by repo name; value is {text, source_url, fetched_at, translator}.
# Falls back to JSON file when PG unavailable.
README_ZH_CACHE = DATA / "readme_zh_cache.json"


def _fetch_readme_from_github(full_name: str, max_chars: int = 6000) -> tuple[str, str] | None:
    """Fetch README.md from GitHub raw for owner/repo. Returns (text, source_url) or None.
    ponytail: try common README filenames in order — README.md / readme.md / README.rst.
    Cap text at max_chars so Google Translate free endpoint (500 char limit) can chunk."""
    candidates = ["README.md", "readme.md", "README.rst", "README.txt"]
    # ponytail: GitHub raw URL is owner/repo/HEAD/<file>. Use gh CLI to find the
    # default branch first, then raw URL.
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return None
        info = json.loads(r.stdout)
        branch = info.get("default_branch", "main")
    except Exception:
        branch = "main"
    for fname in candidates:
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{fname}"
        # ponytail: macOS Python lacks system certs (same issue as HF fetch).
        # Try urllib first, fall back to system curl which uses OS keychain.
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "lodestone/1.0"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if raw.strip():
                return raw[:max_chars], url
        except Exception:
            pass
        try:
            out = subprocess.run(
                [
                    "curl", "-q", "-sSL", "--max-time", "20",
                    "-A", "lodestone/1.0", url,
                ],
                capture_output=True, text=True, timeout=25,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout[:max_chars], url
        except Exception:
            pass
    return None


def _strip_markdown_to_text(md: str, max_chars: int = 4500) -> str:
    """Strip Markdown to clean prose for translation.
    Aggressively drops noise: code blocks, badges, language tables, empty links, HTML,
    GitHub admonitions. Keeps headings (with # prefix) + bullet list markers so the
    translated text retains some shape."""
    text = md
    # remove fenced code blocks (any language tag)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    # remove images and inline badges — leaves empty `[]()` pairs
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[\s*\]\(\s*\)", "", text)
    # collapse links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # drop pure-shields.io badge lines (image inside link inside link)
    text = re.sub(r"^\s*\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$", "", text, flags=re.MULTILINE)
    # drop GitHub-style admonitions
    text = re.sub(r"^>\s*\[!\w+\].*$", "", text, flags=re.MULTILINE)
    # drop "Language: a | b | c" tables (Google Translate fumbles these)
    text = re.sub(r"^[A-Za-z][A-Za-z\s]*:\s*\|.*$", "", text, flags=re.MULTILINE)
    # drop lines that are mostly `|` separators (table rows)
    text = re.sub(r"^[\s|:-]+$", "", text, flags=re.MULTILINE)
    # drop pure-link lines ("[a](b)") — these are usually nav menus
    text = re.sub(
        r"^[\s\[]*\[([^\]]+)\]\([^)]+\)[\s\]]*$",
        r"\1",
        text,
        flags=re.MULTILINE,
    )
    # collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    # paragraph-level filtering: skip pure-noise paragraphs (badges, nav, separators)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    keep: list[str] = []
    skipped_chars = 0
    noise_threshold = 400  # skip up to ~400 chars of preamble noise (badges / TOC)
    for p in paragraphs:
        # skip pure-separator paragraphs
        if not p or all(c in " \t-*#_=|\n" for c in p):
            continue
        # skip "Language: a | b | c" lines that slipped through
        if re.match(r"^[A-Za-z][\w\s]*:\s*[\w\s|]+$", p) and len(p) < 200:
            continue
        # skip if more than 80% URLs / pipes
        non_text = sum(
            1 for c in p if c in "|[](){}<>#=*_`@"
        )
        if non_text > len(p) * 0.4:
            continue
        # ponytail: skip the noisy preamble (links / nav menus) but keep all real prose
        if skipped_chars < noise_threshold and (
            p.startswith("- ")
            or p.startswith("*[")
            or " | " in p[:200]
        ):
            skipped_chars += len(p)
            continue
        keep.append(p)
        if sum(len(x) for x in keep) > max_chars:
            break
    return "\n\n".join(keep)[:max_chars]


def _chunked_translate(text: str, target: str = "zh-CN") -> str:
    """Translate long text by chunking at sentence boundaries (<= 280 chars per chunk).
    ponytail: Google Translate free endpoint silently returns original text on chunks that
    contain too many URLs / special chars. Smaller chunks + retry-on-suspect-output
    dramatically improves coverage."""
    if not text or not text.strip():
        return ""
    if len(text) <= 280:
        result = translate_text(text, target=target)
        if _looks_translated(result, text):
            return result
        return text  # fallback to original on first failure

    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + 280, len(text))
        if end < len(text):
            boundary = end
            for sep in ("\n\n", "。", ". ", "! ", "? ", "\n"):
                idx = text.rfind(sep, cursor, end)
                if idx > cursor + 60:
                    boundary = idx + len(sep)
                    break
            end = boundary
        chunk = text[cursor:end].strip()
        if chunk:
            translated = translate_text(chunk, target=target)
            if _looks_translated(translated, chunk):
                parts.append(translated)
            else:
                parts.append(chunk)  # graceful degradation
        cursor = end
    return "".join(parts)


def _looks_translated(translated: str, original: str) -> bool:
    """Heuristic: a chunk is 'translated' if it has CJK chars AND less than 60% ASCII overlap
    with the source. Avoids keeping 'echoed English' as a translation result."""
    if not translated:
        return False
    cjk = sum(1 for c in translated if "一" <= c <= "鿿")
    if cjk < max(8, len(translated) * 0.05):
        return False  # < 5% CJK → not translated
    return True


def get_readme_zh(full_name: str, force: bool = False) -> dict:
    """Get or build comprehensive Chinese description for a repo.
    Returns {text, source_url, fetched_at, translator, from_cache}.
    Falls back to short description (translated on the fly) if README fetch fails."""
    if not full_name or "/" not in full_name:
        return {"text": "", "source_url": "", "from_cache": False, "error": "invalid name"}
    cache_key = full_name.lower()

    # Tier 1: PG
    if not force and db._DB_OK:
        try:
            conn = db.connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT readme_zh, readme_zh_source, readme_zh_at FROM repos WHERE name = %s",
                    (full_name,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return {
                        "text": row[0],
                        "source_url": row[1] or "",
                        "fetched_at": row[2].isoformat() if row[2] else "",
                        "translator": "google-translate-free",
                        "from_cache": True,
                    }
            finally:
                conn.close()
        except Exception:
            pass

    # Tier 2: JSON cache
    if not force and README_ZH_CACHE.exists():
        try:
            cache = json.loads(README_ZH_CACHE.read_text())
            entry = cache.get(cache_key)
            if entry and entry.get("text"):
                return {**entry, "from_cache": True}
        except (OSError, ValueError):
            pass

    # Tier 3: fetch + translate
    fetched = _fetch_readme_from_github(full_name)
    if not fetched:
        # ponytail: README fetch failed — return short desc_zh fallback (translated on fly).
        try:
            short_desc = _gh_repo_meta(full_name)
            short = (short_desc or {}).get("description") or ""
            if short:
                zh = translate_text(short) or short
                return {
                    "text": (
                        f"【GitHub 简介 · 中文翻译】\n\n{zh}\n\n"
                        f"（自动翻译，原文出处：https://github.com/{full_name}）"
                    ),
                    "source_url": f"https://github.com/{full_name}",
                    "translator": "google-translate-free",
                    "from_cache": False,
                    "fallback": "short_description",
                }
        except Exception:
            pass
        return {"text": "", "source_url": "", "from_cache": False, "error": "fetch failed"}

    raw_md, source_url = fetched
    clean = _strip_markdown_to_text(raw_md)
    zh_text = _chunked_translate(clean)
    # ponytail: if translation truly failed, return the cleaned English content with
    # an explicit marker so the UI can show "（翻译失败 · 原文）" rather than confused text.
    if not zh_text:
        zh_text = (
            "【自动翻译暂不可用 · 以下为英文原文 · 数据源：" + source_url + "】\n\n" + clean
        )
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    entry = {
        "text": zh_text,
        "source_url": source_url,
        "fetched_at": now_iso,
        "translator": "google-translate-free",
        "from_cache": False,
    }

    # Persist to PG
    if db._DB_OK:
        try:
            conn = db.connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE repos SET readme_zh = %s, readme_zh_source = %s, readme_zh_at = NOW() WHERE name = %s",
                    (zh_text, source_url, full_name),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    # Persist to JSON cache
    try:
        cache = (
            json.loads(README_ZH_CACHE.read_text())
            if README_ZH_CACHE.exists()
            else {}
        )
        cache[cache_key] = entry
        README_ZH_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2)
        )
    except OSError:
        pass
    return entry


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
    # ponytail: per-function cache via monkey-patch attribute. Avoids module-level
    # mutable state and survives reloads. Pyright doesn't know about the runtime
    # attribute set on FunctionType, so silence the false positive here.
    if not hasattr(_gh_repo_meta, "_cache"):
        _gh_repo_meta._cache = {}  # type: ignore[attr-defined]
    cache: dict = _gh_repo_meta._cache  # type: ignore[attr-defined]
    if full_name in cache:
        return cache[full_name]
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            cache[full_name] = None
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
        cache[full_name] = out
        return out
    except Exception:
        cache[full_name] = None
        return None


def _load_repo_index() -> dict:
    """Build repo lookup {segment → repo} from PG. Used for topic/stars enrichment + replacement detection.
    ponytail: cache 30s — /api/local calls this twice per request, with 30s SPA polling the
    SQL hit becomes ~4x per minute for nothing. Mutations (install/uninstall) call
    invalidate_repo_index() to bust the cache immediately."""
    now = time.time()
    cache = _repo_index_cache
    if cache["data"] is not None and now - cache["ts"] < _REPO_INDEX_TTL:
        return cache["data"]
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
                by_repo[rec["name"].split("/")[-1].lower()] = rec
    except Exception:
        pass
    cache["ts"] = now
    cache["data"] = by_repo
    return by_repo


# ponytail: TTL cache for _load_repo_index() — same purpose as _local_scan_cache above.
_REPO_INDEX_TTL = 30
_repo_index_cache: dict = {"ts": 0.0, "data": None}


def invalidate_repo_index():
    _repo_index_cache["ts"] = 0.0
    _repo_index_cache["data"] = None


# ponytail: local-scan TTL cache — detect_local_skills() walks brew dirs + runs `uv tool list`
# + may hit `gh api` per unmatched skill. /api/* called it 2x per request → cache 60s,
# invalidated by any install/uninstall/origin mutation.
# ponytail: threading.Lock because ThreadingHTTPServer may invoke detect_local_skills()
# from multiple worker threads concurrently; without the lock, two threads can both see
# an expired cache and both run the (slow) scan.
import threading

_LOCAL_SCAN_TTL = 60
_local_scan_cache: dict = {"ts": 0.0, "data": None}
_local_scan_lock = threading.Lock()


def invalidate_local_scan():
    with _local_scan_lock:
        _local_scan_cache["ts"] = 0.0
        _local_scan_cache["data"] = None


def _owner_repo_from_url(url: str) -> str | None:
    """https://github.com/owner/repo(.git)/… → 'owner/repo';否则 None。"""
    if not url:
        return None
    from urllib.parse import urlparse

    if "github.com" not in (urlparse(url).netloc or ""):
        return None
    parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner and repo:
        return f"{owner}/{repo}"
    return None


def _owner_repo_from_link_target(link: Path) -> str | None:
    """本工具安装的 symlink 指向 SKILLS_CACHE/owner__repo → 'owner/repo'。
    只认缓存目录前缀,不解析任意链接目标。"""
    try:
        target = link.resolve()
        if SKILLS_CACHE.resolve() not in target.parents:
            return None
        stem = target.name  # owner__repo
        if "__" not in stem:
            return None
        owner, _, repo = stem.partition("__")
        if not owner or not repo:
            return None
        if not all(c.isalnum() or c in "-_." for c in owner + repo):
            return None
        return f"{owner}/{repo}"
    except (OSError, RuntimeError):
        return None


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
    with _local_scan_lock:
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

    # skills dirs — 遍历全平台表(2026-09 修复:此前硬编码 claude/codex,
    # 装到 opencode 的 ~250 个技能全部漏检)
    for label, path_expr in _SKILL_PLATFORM_PATHS.items():
        d = Path(path_expr).expanduser()
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
                        **{p: False for p in _SKILL_PLATFORM_PATHS},
                        "url": None,
                        "desc_zh": None,
                        "desc_en": None,
                        "topics": [],
                        "stars": 0,
                        "source": "none",
                    },
                )
                meta[label] = True
                # ponytail: 2026-09 — symlink 指向本工具缓存(SKILLS_CACHE/owner__repo)
                # 时直接还原 owner/repo,零歧义且不依赖 sidecar/PG(实测 ecc 的
                # origins.json 无记录,sidecar 兜不住,链接目标才是事实来源)。
                if entry.is_symlink():
                    full = _owner_repo_from_link_target(entry)
                    if full:
                        meta["origin_full"] = full
        except OSError:
            pass

    # ponytail: enrich each skill with desc/url from 3 sources (priority: cache > origin > skillmd)
    for name, meta in out["skills"].items():
        # ponytail: 2026-09 大小写不敏感 — 目录名/symlink 名与 GitHub repo 名大小写
        # 不必一致(实测 opencode/skills/ecc ↔ affaan-m/ECC);索引键已统一小写。
        if name.lower() in by_repo:
            r = by_repo[name.lower()]
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
                Path(p).expanduser() for p in _SKILL_PLATFORM_PATHS.values()
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
                # ponytail: 2026-09 修复 enabled 误杀 installed — installed_plugins.json
                # 本身就是安装记录;不在 enabledPlugins 只说明「未启用」,不代表「未安装」
                # (实测 ecc@ecc v2.0.0 已装但被此过滤整行跳过,卡片永远不亮)。
                # enabled 如实记录,不再影响是否收录。
                plugin_enabled = not enabled_set or plugin_key in enabled_set
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
                        "enabled": plugin_enabled,
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

    with _local_scan_lock:
        _local_scan_cache["ts"] = time.time()
        _local_scan_cache["data"] = out
    return out


# ponytail: smart install — supports Claude Code + Codex + OpenCode.
# Detects 4 states per target:
#   1) not installed  → full clone + symlink
#   2) already linked to our cache, cache fresh → already up-to-date
#   3) already linked, cache stale       → git pull + re-link
#   4) exists but points elsewhere       → replace with symlink (back up first)
# Returns a structured {target: action: detail} so the UI can show per-CLI status.
# ponytail: skill 平台表 — 安装端与检测端共用同一张表。
# 2026-09 修复「装得到 opencode 却扫不到」的不对称:此前检测端硬编码只扫
# claude/codex 两个目录,凡只装到 opencode 的技能(含本工具 /api/install 装的)
# 一律不显示「已装」。现在两端都从 SKILL_PLATFORMS 取目录。
# config.toml [install.platforms] 可覆盖内置路径或追加自定义平台:
#   [install.platforms]
#   easycode = "~/.easycode/skills"
#   mycli    = "~/skills-mycli"
_SKILL_PLATFORM_PATHS: dict[str, str] = {
    "claude": "~/.claude/skills",
    "codex": "~/.codex/skills",
    "opencode": "~/.config/opencode/skills",
    "easycode": "~/.easycode/skills",
}
try:  # ponytail: config.toml 覆盖/扩展 — 解析失败静默回退内置表(爬虫配置同理)
    import tomllib as _tomllib

    with open(ROOT / "config.toml", "rb") as _f:
        _cfg = _tomllib.load(_f)
    _install_cfg = _cfg.get("install") or {}
    for _k, _v in (_install_cfg.get("platforms") or {}).items():
        if isinstance(_v, str) and _v.strip():
            _SKILL_PLATFORM_PATHS[_k.strip()] = _v.strip()
    # 默认安装平台(前端初始勾选由前端常量定义;此处管 API 不传 targets 时)
    _dt = _install_cfg.get("default_targets")
    if isinstance(_dt, list) and _dt:
        _DEFAULT_INSTALL_TARGETS = tuple(
            t for t in (str(x).strip() for x in _dt) if t in _SKILL_PLATFORM_PATHS
        )
    else:
        _DEFAULT_INSTALL_TARGETS = ("claude",)
except Exception:
    _DEFAULT_INSTALL_TARGETS = ("claude",)

# ponytail: 平台显示名(前端文案/消息用);未知平台回退 CLI 名本身
SKILL_PLATFORM_LABELS = {
    "claude": "Claude Code",
    "codex": "Codex",
    "opencode": "OpenCode",
    "easycode": "EasyCode",
}
SUPPORTED_CLIS = tuple(_SKILL_PLATFORM_PATHS)  # 安装 targets 校验 + 默认顺序


def _skills_root_for(cli: str) -> Path:
    """Map CLI name → skills directory (single source: SKILL_PLATFORM_PATHS)."""
    p = _SKILL_PLATFORM_PATHS.get(cli)
    if not p:
        raise ValueError(
            f"unsupported CLI: {cli!r}. Supported: {', '.join(SUPPORTED_CLIS)}"
        )
    return Path(p).expanduser()


def _git_head_sha(path: Path) -> str | None:
    """Read current HEAD SHA from a git working tree."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _git_pull_fast_forward(path: Path) -> tuple[bool, str]:
    """Fetch + reset to origin/HEAD on a --depth=1 clone. Returns (ok, detail)."""
    try:
        # Unshallow so we can compare against origin; cheap if already shallow.
        # For --depth=1 clones, fetch will get the latest commit only.
        fetch = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if fetch.returncode != 0:
            return False, f"fetch failed: {fetch.stderr.strip()[:120]}"
        reset = subprocess.run(
            ["git", "reset", "--hard", "origin/HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if reset.returncode != 0:
            return False, f"reset failed: {reset.stderr.strip()[:120]}"
        return True, "updated"
    except subprocess.TimeoutExpired:
        return False, "pull timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _git_remote_head_sha(url: str) -> str | None:
    """Query the default branch's HEAD SHA via `git ls-remote` (no clone)."""
    try:
        r = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) == 2 and parts[1] == "HEAD":
                    return parts[0]
    except Exception:
        pass
    return None


def install_skill_from_github(name, url, targets=None, force_update=False):
    """Smart install: clone + symlink + version-aware update.
    Supports Claude Code / Codex / OpenCode skills dirs.
    targets: list of CLI names to install into; default = all three.
    force_update: if True, always git pull even if local cache appears fresh.
    Returns dict {target: {status: 'installed'|'updated'|'up_to_date'|'skipped'|'replaced', detail: str}}.
    """
    if targets is None:
        # ponytail: 2026-09 用户决策 — 默认只装 Claude Code(config.toml [install]
        # default_targets 可改);其余平台由前端勾选显式传入
        targets = list(_DEFAULT_INSTALL_TARGETS)
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
    for t in targets:
        if t not in SUPPORTED_CLIS:
            raise ValueError(
                f"unsupported target CLI: {t!r}. Supported: {SUPPORTED_CLIS}"
            )
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")
    if not url:
        url = f"https://github.com/{name}"
    else:
        from urllib.parse import urlparse

        path = urlparse(url).path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if path != name:
            raise ValueError(
                f"url {url!r} does not match name {name!r} — refusing to clone mismatch"
            )

    target = SKILLS_CACHE / f"{owner}__{repo}"
    cache_state = "fresh"
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
        cache_state = "cloned"
    elif force_update:
        ok, detail = _git_pull_fast_forward(target)
        cache_state = "updated" if ok else "stale"
    else:
        # ponytail: cheap freshness check — compare local HEAD to remote HEAD via
        # ls-remote (no bandwidth). If they match, skip pull.
        local_sha = _git_head_sha(target)
        remote_sha = _git_remote_head_sha(url)
        if local_sha and remote_sha and local_sha == remote_sha:
            cache_state = "fresh"
        else:
            ok, detail = _git_pull_fast_forward(target)
            cache_state = "updated" if ok else "stale"

    out: dict = {"cache": target, "cache_state": cache_state, "targets": {}}
    for cli in targets:
        skills_root = _skills_root_for(cli)
        skills_root.mkdir(parents=True, exist_ok=True)
        link = skills_root / repo
        action = "installed"
        detail = f"linked → {target.name}"
        if link.is_symlink():
            try:
                if link.resolve() == target.resolve():
                    action = "up_to_date" if cache_state in ("fresh", "cloned") else "updated"
                    detail = f"already linked, cache {cache_state}"
                else:
                    # ponytail: symlink exists but points elsewhere — replace
                    backup = link.with_suffix(link.suffix + ".bak")
                    shutil.move(str(link), str(backup))
                    link.symlink_to(target)
                    action = "replaced"
                    detail = f"was pointing to {link.resolve()}; replaced (backup at {backup.name})"
            except OSError as e:
                action = "skipped"
                detail = f"symlink check failed: {e}"
        elif link.exists():
            # ponytail: real dir/file at the path — back it up so we don't blow
            # away user's local skill by accident.
            backup = link.with_suffix(link.suffix + ".bak")
            shutil.move(str(link), str(backup))
            link.symlink_to(target)
            action = "replaced"
            detail = f"was a real dir; backed up to {backup.name}, replaced with symlink"
        else:
            link.symlink_to(target)
        out["targets"][cli] = {"status": action, "detail": detail, "link": str(link)}

    # ponytail: write sidecar so origin URL survives latest.json roll; idempotent update
    try:
        SKILL_ORIGINS.parent.mkdir(parents=True, exist_ok=True)
        origins = {}
        if SKILL_ORIGINS.exists():
            try:
                origins = json.loads(SKILL_ORIGINS.read_text())
            except (OSError, ValueError):
                origins = {}
        origins.setdefault("skills", {})[repo] = {
            "owner": owner,
            "repo": repo,
            "url": url,
            "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "targets": list(targets),
        }
        SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
    except OSError as e:
        sys.stderr.write(f"  [warn] sidecar write failed: {e}\n")

    invalidate_local_scan()
    invalidate_repo_index()
    return out


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
    invalidate_repo_index()
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
            # ponytail: when inst_stars is 0 (PG 没收录的 skill), (inst or 0)*1.5 = 0,
            # making ANY non-zero candidate "much_stronger" — wildly aggressive. Require a
            # minimum baseline of 100 stars on the installed skill before allowing replace.
            baseline = max(100, (inst_stars or 0) * 1.5)
            much_stronger = top["stars"] > baseline
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
    invalidate_repo_index()
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
    invalidate_repo_index()
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
            # ponytail: 2026-08 — on persistent gh api failure, fall back to scraping
            # the github.com search HTML page directly via the engine ladder
            # (httpx → cloudscraper → playwright_stealth → jina). Bypasses the
            # search-API secondary rate limit entirely.
            print(
                f"  ! gh api failed, falling back to HTML scrape: {stderr[:80]}",
                file=sys.stderr,
            )
            return _gh_search_html_fallback(q, per_page=per_page)
        except subprocess.TimeoutExpired:
            print(f"  ! gh api timeout (>60s) for q={q!r}; trying HTML", file=sys.stderr)
            return _gh_search_html_fallback(q, per_page=per_page)
        except Exception as e:
            print(f"  ! gh search error: {e}; trying HTML", file=sys.stderr)
            return _gh_search_html_fallback(q, per_page=per_page)
    else:
        # for/else runs only when the loop completes WITHOUT break — i.e. both
        # attempts failed without raising. Fall back to HTML scrape.
        return _gh_search_html_fallback(q, per_page=per_page)

    # ponytail: success path — gh api returned JSON; build the repo dict list
    # from `items`. Only reached when `break` exited the for-loop on attempt 1
    # or attempt 2 (after a 60s wait, gh api recovered).
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


def _parse_github_search_html(html: str) -> list:
    """Parse github.com/search HTML for repository cards.
    ponytail: GitHub's search HTML is JS-rendered for full data, but the SSR'd repo
    cards carry enough signals (name, description, language, stars, topics in
    data-ga-click attributes) for us to extract basic fields. We also pull
    stars from the <a href="/owner/repo/stargazers">123,456</a> pattern.
    """
    out: list[dict] = []
    # ponytail: extract owner/repo from <a class="Link" data-view-component href="/owner/repo">
    for m in re.finditer(
        r'<a[^>]+href="/([\w.-]+)/([\w.-]+)"[^>]*data-view-component[^>]*>([^<]+)</a>',
        html,
    ):
        owner, repo, name_text = m.group(1), m.group(2), m.group(3).strip()
        if not owner or not repo or owner in ("login", "logout", "settings", "notifications"):
            continue
        if repo in ("issues", "pulls", "actions", "projects", "wiki", "security"):
            continue
        # Approximate stars via aria-label or text near stargazers
        stars = 0
        # find next stargazers count in same article block
        block = html[m.start(): m.start() + 4000]
        s_m = re.search(
            r'href="/' + re.escape(owner) + r'/' + re.escape(repo)
            + r'/stargazers"[^>]*>.*?>([\d,\.]+)([kKmMbB]?)\s*</a>',
            block,
            re.DOTALL,
        )
        if s_m:
            num = s_m.group(1).replace(",", "")
            mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(
                s_m.group(2).lower(), 1
            )
            try:
                stars = int(float(num) * mult)
            except ValueError:
                pass
        # description
        d_m = re.search(
            r'<p class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL
        )
        desc = re.sub(r"<[^>]+>", "", d_m.group(1)).strip() if d_m else ""
        # language
        lang_m = re.search(
            r'itemprop="programmingLanguage">([^<]+)<', block
        )
        lang = lang_m.group(1).strip() if lang_m else "—"
        # topics: scrape from the badge list
        topics: list[str] = []
        for t_m in re.finditer(r'class="topic-tag[^"]*"[^>]*>([^<]+)<', block):
            topics.append(t_m.group(1).strip())
        out.append(
            {
                "name": f"{owner}/{repo}",
                "desc": desc[:300],
                "url": f"https://github.com/{owner}/{repo}",
                "stars": stars,
                "forks": 0,
                "lang": lang,
                "topics": topics,
                "updated": "",
                "pushed": "",
                "score": 0.0,
                "source": "github_search_html",
            }
        )
    # dedupe by name
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in out:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        deduped.append(r)
    return deduped


def _gh_search_html_fallback(q: str, per_page: int = 20) -> list:
    """Scrape github.com/search?q=<query>&type=repositories via the tiered engine ladder.
    Used when gh api search is rate-limited. Returns parsed repo dicts.
    ponytail: search HTML is JS-rendered; the SSR'd cards still carry name/desc/lang/stars
    which is enough for trending-style data. Stars are the only missing accurate field — we
    try to extract from the stargazers link pattern; if not found, leave as 0 (caller can
    enrich via gh_fetch_repo later).
    """
    url = (
        f"https://github.com/search?q={urllib.parse.quote(q)}"
        f"&type=repositories&s=stars&o=desc"
    )
    try:
        from scrapers import fetch_html

        html_text, engine = fetch_html(url, strategy="tiered", timeout=45)
    except Exception as e:
        print(f"  ! search-html fallback failed to even import scrapers: {e}", file=sys.stderr)
        GH_SEARCH_STATS["failed"] += 1
        return []
    if not html_text:
        print(f"  ! search-html fallback returned empty (engine={engine})", file=sys.stderr)
        GH_SEARCH_STATS["failed"] += 1
        return []
    parsed = _parse_github_search_html(html_text)
    if parsed:
        print(f"  · search-html via {engine}: {len(parsed)} repos (q={q[:60]!r})", file=sys.stderr)
        return parsed[:per_page]
    GH_SEARCH_STATS["failed"] += 1
    return []


# ponytail: hand-picked repos that escape topic/description search but are obvious AI tools
# (some maintainers never set topics, some are <5k stars at crawl time). Force-include on every
# crawl so the 5k+ view reflects what users actually expect to see.
MANUAL_SEED_REPOS = frozenset(
    {
        # User-curated 2026-07-21 list — these all slipped past TOP_5K_QUERIES at crawl time
        "Egonex-AI/Understand-Anything",  # knowledge-graph IDE (75k stars, claude-code topic)
        # 2026-09-06 用户赛道清单 — agent 基建/记忆/内容管线等精选项目，强制收录
        "letta-ai/letta",               # MemGPT 分层记忆
        "supermemoryai/supermemory",    # 记忆 API
        "memvid/memvid",              # 单文件视频记忆
        "labring/FastGPT",              # 知识库平台
        "funstory-ai/BabelDOC",            # 学术文档翻译
        "D4Vinci/Scrapling",            # 自适应爬虫（agent 手脚）
        "SWivid/F5-TTS",                # 语音合成
        "lllyasviel/Fooocus",           # 图像生成
        "coderamp-labs/gitingest",      # 代码库 → LLM 文本
        "VoltAgent/awesome-agent-skills", # skills 聚合清单
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


def fetch_huggingface_trending(max_items: int = 30, sort: str = "likes7d") -> list:
    """HuggingFace Trending Spaces — JSON API (no auth). Returns repo-shaped dicts so the
    rest of the pipeline (translation, upsert, hot_now) works without special-casing.

    ponytail: HF's public API has no literal "trending" sort, but `sort=likes7d` returns
    `trendingScore` (their internal 7-day pop score). We surface that as `stars` so the
    rest of the UI / sorting treats HF spaces uniformly. `likes` becomes total likes (lifetime).

    2026-09: sort 白名单与 sources/huggingface_models.py 共用（两个 HF fetcher
    一套规则），非法值回退 likes7d。

    Source: https://huggingface.co/api/spaces?sort=likes7d&limit=N (public JSON).
    Falls back to system `curl` when Python's SSL certs are missing (macOS Python builds
    commonly lack the cert chain). Returns [] on any error — HF down shouldn't block
    the GitHub crawl."""
    try:
        from sources.huggingface_models import VALID_SORTS
    except Exception:
        VALID_SORTS = ("trending", "likes7d", "downloads", "downloads7d", "updated")
    if sort not in VALID_SORTS:
        print(f"  [warn] HF spaces: invalid sort {sort!r}, falling back to likes7d", file=sys.stderr)
        sort = "likes7d"
    url = f"https://huggingface.co/api/spaces?sort={sort}&limit={max_items}"
    data = None
    # ponytail: 2026-09 — httpx 优先（自带 certifi 证书链）。本机实测 urllib 100%
    # SSL: CERTIFICATE_VERIFY_FAILED（macOS Python 缺系统证书链），curl 走系统
    # 代理偶发 Connection reset — 两级都塌导致 Spaces 分类连续两次爬到 0 条。
    try:
        import httpx

        r = httpx.get(
            url, timeout=20, headers={"User-Agent": "lodestone/1.0"}, follow_redirects=True
        )
        if r.status_code == 200 and r.text.strip():
            data = r.json()
    except Exception:
        pass
    # ponytail: httpx 已拿到数据就别再走旧路径 — 旧路径 urllib 失败后 curl 再失败
    # 会 return []，把 httpx 的成功结果一起丢掉（Spaces 连续 0 条的根因之二）。
    if data is None:
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
    # 2026-09 P3: topic:ai → 硬 topic 组。裸 'ai' 是宽 topic(is_ai_relevant 也不认),
    # 捞回来的多是非 AI 项目又被过滤掉,兜底几乎白跑。
    queries = [
        f"stars:>300 pushed:>{cutoff} topic:llm",
        f"stars:>300 pushed:>{cutoff} topic:ai-agent",
        f"stars:>300 pushed:>{cutoff} topic:claude-code",
        f"stars:>300 pushed:>{cutoff} topic:mcp-server",
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


def fetch_github_trending(since: str = "daily", max_repos: int = 30, language: str | None = None):
    """Scrape github.com/trending and enrich each entry with full data via gh_fetch_repo.

    Why: search-by-stars misses fresh AI tools that haven't crossed 5k yet but are trending today.
    HTML sources, in order (see scrapers/ — 4-engine tiered ladder, 2026-09):
      1. httpx → cloudscraper → playwright_stealth → jina (light→heavy→cloud,
         quality-gated: each tier must return a REAL trending page or we escalate)
      2. plain urllib (stdlib, original path)
      3. all failed → fetch_recent_active_repos (search-API proxy for trending)
    language: None = 全语言混合页;"python"/"typescript"/... = 语言子页(GitHub
    trending 无翻页,语言变体是唯一扩容手段 — 每页固定 25 条,max_repos>25 无效)。
    Returns normalized repo dicts (same shape as gh_search output) with extra 'source' marker.
    """
    lang_path = f"/{language}" if language else ""
    url = f"https://github.com/trending{lang_path}?since={since}"
    html_text, engine = "", "none"
    # tier 1: real scrapers — optional package; missing/broken → urllib still works.
    # ponytail: strategy="tiered" — engines escalate light→heavy; each result must
    # pass the quality gate (≥5 Box-row articles for trending) before it's accepted,
    # so a bot-check page from httpx escalates to cloudscraper instead of winning.
    try:
        from scrapers import fetch_html

        html_text, engine = fetch_html(url, strategy="tiered")
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

    # ponytail: 2026-09 — GraphQL 批量搜索。全部 GitHub query（20 分类 ~119 条 +
    # 5k+ pass 85 条）先收集、去重、分批并行执行（分类批 6×first:30，5k 批
    # 8×first:50；失败批对半拆分重试）。实测搜索阶段 ~12 分钟（串行 REST）→
    # ~3 分钟（2026-09 全量验证：204 query 中 189 个走 GraphQL，15 个 REST 兜底）。
    # GraphQL 彻底失败的 query 回退 REST gh_search（自适应 pace + HTML 兜底）。
    _search_t0 = time.monotonic()
    _all_gh_queries = [q for cat in CATEGORIES for q in cat.get("queries", [])]
    _batch: dict[str, list] = {}
    _new_star_queries: list[str] = []  # GraphQL 不可用时保持空(新星通道仅依赖 GraphQL)
    _new_star_cutoff = (
        datetime.date.today() - datetime.timedelta(days=14)
    ).isoformat()
    try:
        from sources.github_graphql import gh_search_batch

        print(
            f"[crawl] GraphQL batch search: {len(_all_gh_queries)} category queries "
            f"+ {len(TOP_5K_QUERIES)} 5k+ queries…"
        )
        _batch.update(
            gh_search_batch(_all_gh_queries, per_page=30, batch_size=6)
        )
        _batch.update(
            gh_search_batch(
                TOP_5K_QUERIES, per_page=50, batch_size=8, follow_page2=True
            )
        )
        # ponytail: 2026-09 P1 修复 — 低星新星通道。全部 5k 池查询 stars:>500、
        # 分类查询大多 stars:>100+，"刚开源、<500 星、没上 trending"的项目有
        # 真空期（实测 PG 中 stars<500 且无分类的行 = 0）。近 14 天 created +
        # 硬 topic + stars:>50 专门捞这批；走独立通道并入（不参与星标截断）。
        _new_star_queries = [
            f"stars:>50 created:>{_new_star_cutoff} topic:{t}"
            for t in ("llm", "ai-agent", "mcp-server", "claude-code", "ai-coding")
        ]
        _batch.update(
            gh_search_batch(_new_star_queries, per_page=30, batch_size=6)
        )
    except Exception as e:
        print(
            f"  [warn] GraphQL batch unavailable ({e}); REST serial fallback "
            f"({len(_all_gh_queries) + len(TOP_5K_QUERIES)} queries, slow)",
            file=sys.stderr,
        )

    def _query_repos(q: str, per_page: int = 20) -> list:
        """批量结果优先；GraphQL 没覆盖到的 query 回退 REST gh_search。"""
        if q in _batch:
            return _batch[q]
        _search_pace()  # rate limit: 30 search req/min — adaptive sleep between ALL search calls
        try:
            repos = gh_search(q, per_page=per_page)
        except Exception as e:
            print(f"  [warn] query '{q}' failed: {e}", file=sys.stderr)
            repos = []
        _batch[q] = repos
        return repos

    for cat in CATEGORIES:
        seen = set()
        repos = []
        # ponytail: empty `queries` = non-GitHub source category. Dispatch by the
        # `source` field so adding new sources (HF Spaces, HF Models, MCP Registry,
        # ...) is a single line. Keeps the rest of the pipeline (translation,
        # hot_now, upsert, JSON snapshot) working uniformly.
        if not cat["queries"]:
            src = cat.get("source")
            if src == "hf_spaces":
                repos = fetch_huggingface_trending(max_items=30)
            elif src == "hf_models":
                try:
                    from sources.huggingface_models import fetch_huggingface_models_trending
                    repos = fetch_huggingface_models_trending(max_items=30)
                except Exception as e:
                    print(f"  [warn] HF models fetcher failed: {e}", file=sys.stderr)
                    repos = []
            elif src == "mcp_registry":
                try:
                    from sources.mcp_registry import fetch_mcp_registry
                    repos = fetch_mcp_registry(max_items=30)
                except Exception as e:
                    print(f"  [warn] MCP registry fetcher failed: {e}", file=sys.stderr)
                    repos = []
            elif src == "arxiv":
                try:
                    from sources.arxiv_papers import fetch_arxiv_recent
                    repos = fetch_arxiv_recent(max_items=30)
                except Exception as e:
                    print(f"  [warn] arXiv fetcher failed: {e}", file=sys.stderr)
                    repos = []
            # else: an unknown source type — drop with warning so silent data loss is loud
            if not repos and src:
                print(
                    f"  [warn] category {cat['id']!r}: source {src!r} returned 0 items",
                    file=sys.stderr,
                )
        else:
            for q in cat["queries"]:
                for r in _query_repos(q, per_page=30):
                    # ponytail: 2026-09 — 分类结果过完整 AI 过滤。宽 query
                    # （topic:workflow-orchestration 等）会带进 airflow/nvm 这类
                    # 非 AI 项目；AI_TOPIC_HARD 已补齐变体（vision-language-model/
                    # mcp/...）避免误伤 Qwen-VL/playwright-mcp。
                    if not is_ai_relevant(r):
                        continue
                    ukey = normalize_git_url(r.get("url")) or r["name"]
                    if ukey in seen:
                        continue
                    seen.add(ukey)
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
    print(f"[crawl] 5k+ pass ({len(TOP_5K_QUERIES)} queries)…")
    # ponytail: 2026-09 P2 — 池内合并键统一小写:GitHub full_name 大小写随改名
    # 变化,精确比较会产生大小写变体漏合并(单次 crawl 内 normalize_git_url 已
    # 小写,这里对齐同一语义;repo["name"] 原样保留供显示)。
    top_5k_repos = {}
    for q in TOP_5K_QUERIES:
        try:
            for r in _query_repos(q, per_page=100):
                if not is_ai_relevant(r):
                    continue
                top_5k_repos.setdefault(r["name"].lower(), r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}")

    print(
        f"  ✓ 5k+ pass: {len(top_5k_repos)} repos after AI filter "
        f"(search phase {time.monotonic() - _search_t0:.0f}s)"
    )

    # ponytail: manual seed — guaranteed inclusion of well-known AI tools that escape topic search
    for full_name in MANUAL_SEED_REPOS:
        if full_name.lower() in top_5k_repos:
            continue
        r = gh_fetch_repo(full_name)
        if not r or not is_ai_relevant(r):
            continue
        top_5k_repos[full_name.lower()] = r
        print(f"  ✓ manual seed: {full_name} ({r['stars']} ⭐)")

    # ponytail: GitHub trending — catches fresh AI tools with <5k stars that are hot today.
    # Pull BOTH daily and weekly — daily = today's buzz, weekly = rising stars the daily
    # doesn't yet show. Dedupe on name so a repo on both lists is counted once.
    # 2026-09 P2 — daily 加语言子页(python/typescript/rust/go,各 25 条):GitHub
    # trending 无翻页、全语言混合页每天只捞出 ~22 个 AI 项目,语言变体是唯一
    # 扩容手段。6 路并发(各走分级引擎阶梯),失败一路不拖累其余。
    _trend_routes = [
        ("daily", None),
        ("weekly", None),
        ("daily", "python"),
        ("daily", "typescript"),
        ("daily", "rust"),
        ("daily", "go"),
    ]
    print(
        f"[crawl] GitHub trending ({len(_trend_routes)} routes: daily/weekly × all-lang + python/ts/rust/go)…"
    )
    trending_daily, trending_weekly, _trend_lang = [], [], []
    with ThreadPoolExecutor(max_workers=len(_trend_routes)) as _tex:
        _futs = {
            _tex.submit(fetch_github_trending, since, 30, lang): (since, lang)
            for since, lang in _trend_routes
        }
        for _fut, (_since, _lang) in _futs.items():
            try:
                _res = _fut.result()
            except Exception as e:
                print(
                    f"  [warn] trending {_since}/{_lang or 'all'} failed: {e}",
                    file=sys.stderr,
                )
                continue
            if _lang is None:
                if _since == "daily":
                    trending_daily = _res
                else:
                    trending_weekly = _res
            else:
                _trend_lang.extend(_res)
    trending_seen, trending = set(), []
    for r in trending_daily + trending_weekly + _trend_lang:
        if r["name"].lower() in trending_seen:
            continue
        trending_seen.add(r["name"].lower())
        trending.append(r)
    for r in trending:
        # ponytail: 合入 5k 池前过 AI 过滤 — 池子其他入口都过滤，这里不过滤
        # 会让 nvm（87k⭐ 的 Node 版本管理器）这种非 AI 热门项目直接冲进 hot_now 头部。
        if is_ai_relevant(r) and r["name"].lower() not in top_5k_repos:
            top_5k_repos[r["name"].lower()] = r
    trending_ai = [r for r in trending if is_ai_relevant(r)]
    print(
        f"  ✓ trending: {len(trending_daily)} daily + {len(trending_weekly)} weekly + "
        f"{len(_trend_lang)} lang-variant → {len(trending)} unique → {len(trending_ai)} AI-relevant → merged into 5k+ pool"
    )
    # ponytail: keep trending SEPARATELY so the 300-row TOP_5K_LIMIT truncation below can't
    # drop their stars_today. Trending repos are low-star by definition (the whole point is
    # "new today" / "rising this week") — they'd otherwise be at the bottom of the 300-row slice.
    top_5k_sorted = sorted(
        top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True
    )[:TOP_5K_LIMIT]

    # Detect local skills — cached 60s; crawl marks which repos are already installed
    # 2026-09: 与 serve/refresh 路径对齐 — 复用 _installed_segments(skills origin +
    # marketplace + 插件 origin)并小写化,而非裸技能目录名大小写敏感匹配
    local = detect_local_skills()
    installed_full = {s.lower() for s in _installed_segments(local)}
    installed_segs = {
        *installed_full,
        *(s.split("/")[-1] for s in installed_full),
        *(p["name"].split("@")[0].lower() for p in (local.get("plugins") or []) if p.get("name")),
    }
    print(f"[crawl] local installed (full/seg): {len(installed_segs)}")

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
    # The TOP_5K_LIMIT truncation above drops low-star trending repos — re-add them
    # so the stars_today field always reaches the DB / JSON snapshot.
    for r in trending_ai:
        if r["name"].lower() not in {p["name"].lower() for p in to_persist}:
            r["best_category"] = None
            to_persist.append(r)

    # ponytail: 2026-09 P1 — 新星通道并入(同 trending 补回逻辑:不参与星标截断;
    # 已在分类/5k/trending 里的不会重复并入;键统一小写防大小写变体漏判)。
    new_stars: dict[str, dict] = {}
    for q in _new_star_queries:
        for r in _batch.get(q) or []:
            if not is_ai_relevant(r):
                continue
            new_stars.setdefault(r["name"].lower(), r)
    _ns_existing = {p["name"].lower() for p in to_persist}
    for r in new_stars.values():
        if r["name"].lower() not in _ns_existing:
            r["best_category"] = None
            to_persist.append(r)
    print(
        f"  ✓ new-star pass: {len(new_stars)} low-star repos (created>{_new_star_cutoff if _new_star_queries else '—'})"
    )
    # ponytail: 去重规则 = git 完整仓库地址（normalize_git_url 归一化：小写/
    # 去 .git/去尾斜杠/gh:// 前缀）。同一仓库从 GitHub 搜索、trending、MCP
    # registry 多路进来只会留一份（分类归属仍是多对多）。
    # 2026-09：trending 标记在去重时打上 — JSON 快照此前 0 标记，前端「趋势」
    # tab 一直在显示按星标排序的兜底数据，与 github.com/trending 对不上。
    _trending_names = {r["name"].lower() for r in trending_ai}
    seen = set()
    deduped = []
    for r in to_persist:
        ukey = normalize_git_url(r.get("url")) or r["name"]
        if ukey in seen:
            continue
        seen.add(ukey)
        r["is_ai_relevant"] = is_ai_relevant(r)
        if r["name"].lower() in _trending_names:
            r["trending"] = True
        deduped.append(r)

    # ponytail: translate once, cache forever — descriptions don't change day-to-day
    print("[crawl] translating to Chinese…")
    pairs = [(f"{r['name']}::desc", r.get("desc", "")) for r in deduped]
    zh = translate_batch(pairs)
    for r in deduped:
        r["desc_zh"] = zh.get(f"{r['name']}::desc", "") or r.get("desc_zh", "")
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = (
            r["name"].lower() in installed_segs
            or r["name"].split("/")[-1].lower() in installed_segs
        )
        # 精选赛道标记 — hot_now 保底浮出用（CURATED_ALLOWLIST + 手工种子）
        r["curated"] = (r["name"].lower() in CURATED_ALLOWLIST) or (
            r["name"] in MANUAL_SEED_REPOS
        )

    # ponytail: 2026-09 — 详细中文描述（README 首段翻译，缓存复用）。
    # 取代抽屉里的按需「中文详介」— 数据随快照就绪，前端零等待。
    try:
        n_sum = enrich_summaries(deduped)
        print(f"  ✓ summaries: {n_sum}/{len(deduped)} repos with zh summary")
    except Exception as e:
        print(f"  [warn] summary enrichment failed: {e}", file=sys.stderr)
        for r in deduped:
            r.setdefault("summary_zh", r.get("desc_zh") or "")

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
            # ponytail: 2026-09 — cat_pairs 必须按 deduped 过滤。分类循环收集的
            # 关联在全局去重后可能指向被丢弃的条目(实测 MCP registry 项的
            # websiteUrl 归一化后与别的条目撞键被 dedup 丢弃),外键约束会让
            # 整个入库事务回滚 → JSON fallback,PG 数据停在旧 crawl。
            _persisted_names = {r["name"] for r in deduped}
            db.replace_categories(
                conn,
                [(n, c) for n, c in cat_pairs if n in _persisted_names],
            )
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
        # ponytail: hot_now = 星标 Top-40 + 精选赛道项目保底（用户清单里的项目
        # 必须可见 — 此前只在 5k 池里，按星标排不进前 40 就整页不可见）。
        "hot_now": (
            lambda top40: top40
            + [
                r
                for r in deduped
                if r.get("curated")
                and r["name"] not in {x["name"] for x in top40}
            ]
        )(
            sorted(deduped, key=lambda r: r.get("stars", 0), reverse=True)[:40]
        ),
        "categories": cat_results,
        # 2026-09：trending 专区数据 — 今日上榜的完整列表（带 stars_today），
        # 前端「趋势」tab 直接消费，不再用 hot_now 兜底。
        "trending": sorted(
            [r for r in deduped if r.get("trending")],
            key=lambda r: -(r.get("stars_today") or 0),
        ),
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
      0. local skills 目录 origin — meta.url(PG 索引/sidecar)或 origin_full
         (symlink 目标 SKILLS_CACHE/owner__repo 还原)。2026-09 修复:此前 skills
         目录完全不参与本函数,凡以技能(非插件)形式装的卡片永远标不出「已装」。
      1. plugin cache .git/config origin (when plugin was git-installed, e.g. obra/superpowers)
      2. plugin's marketplace source repo (when plugin lives in the marketplace repo,
         source is './' relative to marketplace — use marketplace URL as the source)
      3. known_marketplaces.json (covers the marketplace URL itself)
    """
    segs = set()

    # ponytail: 2026-09 — skills 目录 origin(三路:origin_full > url > 跳过)
    for _name, meta in (local.get("skills") or {}).items():
        full = (meta or {}).get("origin_full") or _owner_repo_from_url(
            (meta or {}).get("url") or ""
        )
        if full:
            segs.add(full)

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

        def _json(self, data, status=200, etag=False):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            tag = None
            if etag:
                # ponytail: 2026-09 — ETag 协商。前端 30s 轮询 /api/data（~600KB/次），
                # 304 让未变化的响应零传输。no-store 阻止浏览器自动缓存，所以由
                # 前端手动带 If-None-Match（见 frontend/src/lib/api.ts）。
                tag = '"' + __import__("hashlib").md5(body).hexdigest()[:16] + '"'
                if (self.headers.get("If-None-Match") or "").strip() == tag:
                    self.send_response(304)
                    self.send_header("ETag", tag)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if tag:
                self.send_header("ETag", tag)
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self):
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        # ponytail: /zp 一键体验 — serve 不再是纯 API：非 /api 的 GET 直接托管
        # frontend/dist 构建产物（前端 BASE='' 同源相对路径，无需 Vite）。
        # 开发模式仍走 `cd frontend && npm run dev`（热更新）。
        _STATIC_TYPES = {
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
        }

        def _serve_static(self):
            root = (ROOT / "frontend" / "dist").resolve()
            if not (root / "index.html").is_file():
                self.send_error(
                    503,
                    "frontend/dist not built — run `cd frontend && npm install && npm run build`",
                )
                return
            path = urllib.parse.urlparse(self.path).path
            if path.startswith("/assets/"):
                f = (root / path.lstrip("/")).resolve()
                # ponytail: path-traversal guard — /assets/../radar.py 不许读源码
                if root not in f.parents or not f.is_file():
                    self.send_error(404)
                    return
                body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", self._STATIC_TYPES.get(f.suffix, "application/octet-stream"))
                self.send_header("Content-Length", str(len(body)))
                # ponytail: 文件名带 hash → 内容变名字变，可放心长缓存
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(body)
                return
            # SPA 兜底：其余路径（含 /）都回 index.html，路由由前端接管
            body = (root / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

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
                            },
                            etag=True,
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
                            # 视觉审查修复：JSON 回退模式此前丢掉 stars_today，
                            # 前端「今日上榜」永远显示 0（与卡片 +2206 当场矛盾）。
                            "stars_today": snap.get("stars_today") or {},
                            # 2026-09：trending 专区列表（趋势 tab 消费）
                            "trending": snap.get("trending") or [],
                        },
                        etag=True,
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
            # ponytail: /api/stats — lightweight digest for the 📊 RTK-style token economy
            # panel + ecosystem breakdown. Computed from PG (or JSON snapshot fallback).
            if self.path == "/api/stats":
                try:
                    stats = {"by_lang": {}, "by_topic": {}, "total_repos": 0, "total_stars": 0}
                    pg_failed = False
                    # ponytail: 2026-08 — language allowlist. The repo `lang`
                    # field can hold non-language tags leaked from upstream
                    # sources ("Transformers", "Mcp server", "Model" — these
                    # are HF library_name / registry pseudo-langs, not programming
                    # languages). Filter to a curated set so by_lang counts
                    # programming languages only.
                    LANG_ALLOWLIST = {
                        "Python", "JavaScript", "TypeScript", "Java", "C++", "C",
                        "C#", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin",
                        "Scala", "Shell", "HTML", "CSS", "Lua", "Dart", "Elixir",
                        "Haskell", "OCaml", "R", "Julia", "Racket", "Erlang",
                        "Groovy", "Perl", "Nim", "Crystal", "Zig", "V", "Odin",
                        "Vue", "Svelte", "CoffeeScript", "Hack",
                        "F#", "Clojure", "Common Lisp", "Emacs Lisp", "Scheme",
                        "Tcl", "Vala", "Verilog", "VHDL", "Solidity", "Move",
                        "Dockerfile", "Makefile",
                        "Markdown", "HTML+ERB", "PLpgSQL",
                    }
                    if db._DB_OK:
                        try:
                            conn = db.connect()
                            try:
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT lang, COUNT(*), SUM(stars) FROM repos "
                                    "WHERE is_ai_relevant AND lang IS NOT NULL "
                                    "AND lang = ANY(%s) "
                                    "GROUP BY lang",
                                    (list(LANG_ALLOWLIST),),
                                )
                                for row in cur.fetchall():
                                    stats["by_lang"][row[0]] = {"count": row[1], "stars": int(row[2] or 0)}
                                cur.execute("SELECT t, COUNT(*) FROM (SELECT unnest(topics) AS t FROM repos WHERE is_ai_relevant) x GROUP BY t ORDER BY COUNT(*) DESC LIMIT 20")
                                for row in cur.fetchall():
                                    stats["by_topic"][row[0]] = row[1]
                                cur.execute("SELECT COUNT(*), SUM(stars) FROM repos WHERE is_ai_relevant")
                                row = cur.fetchone()
                                stats["total_repos"] = row[0]
                                stats["total_stars"] = int(row[1] or 0)
                            finally:
                                conn.close()
                        except Exception as e:
                            # 2026-08 — PG installed but unreachable. Fall through to
                            # JSON snapshot path so /api/stats doesn't return empty
                            # when the credentials are wrong / DB is down.
                            pg_failed = True
                            stats["db_error"] = str(e)
                    if (not db._DB_OK) or pg_failed:
                        # ponytail: JSON fallback (no PG OR PG failed)
                        latest = DATA / "latest.json"
                        if latest.exists():
                            snap = json.loads(latest.read_text())
                            counts: dict[str, int] = {}
                            for cat in snap.get("categories", []):
                                for x in cat.get("repos", []):
                                    # normalize lang casing — 'Python' and 'python' should merge
                                    raw = (x.get("lang") or "—").strip()
                                    key = raw if raw == "—" else raw[:1].upper() + raw[1:].lower()
                                    # 2026-08 — filter to programming languages only;
                                    # upstream tags like "Transformers", "Mcp server"
                                    # would otherwise show in by_lang. Compare case-
                                    # insensitively since the allowlist uses Title Case
                                    # but data may come in any case.
                                    if key != "—" and key not in LANG_ALLOWLIST and key.lower() not in {l.lower() for l in LANG_ALLOWLIST}:
                                        continue
                                    counts[key] = counts.get(key, 0) + 1
                            # sort by count desc, keep top 15
                            sorted_langs = sorted(counts.items(), key=lambda x: -x[1])[:15]
                            stats["by_lang"] = {k: {"count": v, "stars": 0} for k, v in sorted_langs}
                            # ponytail: same dedup logic for topics — lowercase normalize
                            topic_counts: dict[str, int] = {}
                            for cat in snap.get("categories", []):
                                for x in cat.get("repos", []):
                                    for t in (x.get("topics") or []):
                                        tk = t.strip().lower()
                                        if tk:
                                            topic_counts[tk] = topic_counts.get(tk, 0) + 1
                            sorted_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:30]
                            stats["by_topic"] = {k: v for k, v in sorted_topics}
                            stats["total_repos"] = snap.get("total_unique", 0)
                            stats["total_stars"] = sum(r.get("stars", 0) for r in snap.get("hot_now", []))
                            if pg_failed:
                                stats["note"] = "PG unreachable — showing JSON snapshot"
                    self._json(stats)
                except Exception as e:
                    self._json({"error": str(e)}, status=500)
                return

            # ponytail: comprehensive Chinese README on demand.
            # GET /api/repo/<owner>/<repo>/readme[?force=1]
            # Returns {text, source_url, fetched_at, translator, from_cache}.
            if self.path.startswith("/api/repo/") and self.path.endswith("/readme"):
                try:
                    inner = self.path[len("/api/repo/") : -len("/readme")].strip("/")
                    parsed_q = urllib.parse.urlparse(self.path)
                    qs = urllib.parse.parse_qs(parsed_q.query)
                    force = qs.get("force", ["0"])[0] in ("1", "true", "yes")
                    full_name = urllib.parse.unquote(inner)
                    result = get_readme_zh(full_name, force=force)
                    if result.get("error") and not result.get("text"):
                        return self._json(result, status=404)
                    return self._json(
                        {
                            "ok": True,
                            "repo": full_name,
                            "text": result.get("text", ""),
                            "source_url": result.get("source_url", ""),
                            "fetched_at": result.get("fetched_at", ""),
                            "translator": result.get("translator", ""),
                            "from_cache": result.get("from_cache", False),
                            "fallback": result.get("fallback", ""),
                        }
                    )
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)}, status=500)

            if self.path == "/api/scrapers/status":
                # ponytail: exposes the {engine: available} map for the 🛠 引擎
                # panel in the UI. Cached via scrapers.status() which itself caches
                # the underlying is_available() calls.
                try:
                    from scrapers import status as _scraper_status

                    self._json(_scraper_status())
                except ImportError:
                    self._json({"error": "scrapers module unavailable"}, status=503)
                return
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
                # ponytail: fallback — paginate all repos from latest.json in-memory.
                # Filter to 1k+ stars to mirror PG query_top_5k's star gate so the
                # JSON-only mode doesn't show 50-star repos in the "1k+ 主流" view.
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
                    # 2026-08 — drop the ≥1000 ⭐ filter. The "1k+ 主流 AI 项目"
                    # view should show ALL mainstream AI tools / skills / plugins
                    # regardless of star count (a fresh trending MCP server with
                    # 200 stars is still mainstream). The category filter at the
                    # front-end side is the right way to gate; the API should
                    # return the full pool.
                    repos_1k = list(by_name.values())
                    # ponytail: pin MANUAL_SEED_REPOS to the front so they show up regardless of stars rank
                    # (lidge-jun/opencodex = 3264⭐ is in MANUAL_SEED but doesn't make top 48 by stars)
                    seen = set(r["name"] for r in repos_1k)
                    pinned_first = []
                    for full_name in MANUAL_SEED_REPOS:
                        if full_name in seen:
                            pinned_first.append(by_name[full_name])
                            seen.discard(full_name)
                    rest = [r for r in repos_1k if r["name"] in seen]
                    if sort == "stars":
                        sort_key = lambda r: r.get("stars", 0)
                        reverse = True
                    elif sort == "recent":
                        sort_key = lambda r: r.get("pushed", "") or ""
                        reverse = True
                    elif sort == "name":
                        sort_key = lambda r: (r.get("name") or "").lower()
                        reverse = False
                    else:
                        sort_key = lambda r: r.get("stars", 0)
                        reverse = True
                    repos = pinned_first + sorted(rest, key=sort_key, reverse=reverse)
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
                # ponytail: 26h/44h (was 20h/4h) — the original 4h recent window never captured
                # a daily-crawl row (crawls are 24h apart), so the snapshot_gain CTE was always
                # empty. 26h gives us "today's snapshot", 44h gives us "yesterday's snapshot" —
                # this works for any cadence from 2×/day to once/2days.
                prev_ago, recent_ago = "44 hours", "26 hours"
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

            # ponytail: code-graph endpoints — integrate graphify + code-review-graph
            # for installed skills so the UI can render rich relationship visualizations.
            if self.path.startswith("/api/graph/"):
                try:
                    slug = urllib.parse.unquote(
                        self.path[len("/api/graph/") :]
                    ).strip("/")
                    owner_repo = slug
                    if "/" not in owner_repo:
                        idx = _load_repo_index()
                        if slug in idx:
                            owner_repo = idx[slug].get("name", "")
                    if "/" not in owner_repo:
                        # ponytail: fall back to local scan — installed skills without
                        # a PG entry should still be resolvable for graph viz.
                        local = detect_local_skills()
                        for s, meta in (local.get("skills") or {}).items():
                            if s == slug:
                                if meta.get("url"):
                                    owner_repo = _repo_slug_from_url(meta["url"])
                                else:
                                    owner_repo = f"local/{slug}"
                                break
                    if "/" not in owner_repo:
                        return self._json(
                            {"error": f"unknown skill: {slug}"}, status=404
                        )
                    owner, repo = owner_repo.split("/", 1)
                    candidates = [
                        SKILLS_CACHE / f"{owner}__{repo}",
                        SKILLS_CACHE / repo,
                        Path.home() / ".claude" / "skills" / repo,
                        Path.home() / ".codex" / "skills" / repo,
                    ]
                    skill_dir = next(
                        (p for p in candidates if p.exists()), None
                    )
                    if not skill_dir:
                        return self._json(
                            {"error": f"skill {owner_repo} not installed locally"},
                            status=404,
                        )
                    graph_path = skill_dir / "graphify-out" / "graph.json"
                    # ponytail: graceful path — if no graph.json exists, try building it
                    # in-place via `graphify update <skill_dir>` (uses tree-sitter, no LLM).
                    # If still nothing (e.g. SKILL.md-only skills), return an actionable 200.
                    if not graph_path.exists():
                        build = subprocess.run(
                            ["graphify", "update", str(skill_dir), "--no-cluster"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        # build.returncode may be 0 even when no code was found
                    if graph_path.exists():
                        r = subprocess.run(
                            [
                                "graphify",
                                "explain",
                                slug,
                                "--graph",
                                str(graph_path),
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if r.returncode == 0:
                            return self._json(
                                {
                                    "ok": True,
                                    "skill": owner_repo,
                                    "source": "graphify",
                                    "explanation": r.stdout.strip(),
                                }
                            )
                    # ponytail: fallback — return install metadata so the UI can still
                    # render *something* useful (stars, topics, readme hint) when the
                    # skill has no code to graph (most Claude Code skills are SKILL.md only).
                    idx = _load_repo_index()
                    repo_meta = idx.get(slug) or {}
                    return self._json(
                        {
                            "ok": True,
                            "skill": owner_repo,
                            "source": "metadata",
                            "explanation": (
                                "此 skill 主要由 SKILL.md 组成（无 Python/TS 代码可做图谱分析）。"
                                "可用的元数据："
                                + (
                                    f"\n  • 描述：{repo_meta.get('description', '')[:160]}"
                                    if repo_meta.get("description")
                                    else ""
                                )
                                + (
                                    f"\n  • ⭐ {repo_meta.get('stars', 0):,}"
                                    if repo_meta.get("stars")
                                    else ""
                                )
                                + (
                                    f"\n  • Topics: {', '.join(repo_meta.get('topics') or [])[:120]}"
                                    if repo_meta.get("topics")
                                    else ""
                                )
                                + (
                                    f"\n  • URL: {repo_meta.get('url')}"
                                    if repo_meta.get("url")
                                    else ""
                                )
                            ).strip(),
                            "repo": repo_meta,
                        }
                    )
                except subprocess.TimeoutExpired:
                    return self._json({"error": "graphify timeout"}, status=504)
                except Exception as e:
                    return self._json({"error": str(e)}, status=500)

            if self.path.startswith("/api/crg/"):
                try:
                    slug = urllib.parse.unquote(
                        self.path[len("/api/crg/") :]
                    ).strip("/")
                    owner_repo = slug
                    if "/" not in owner_repo:
                        idx = _load_repo_index()
                        if slug in idx:
                            owner_repo = idx[slug].get("name", "")
                    if "/" not in owner_repo:
                        local = detect_local_skills()
                        for s, meta in (local.get("skills") or {}).items():
                            if s == slug:
                                if meta.get("url"):
                                    owner_repo = _repo_slug_from_url(meta["url"])
                                else:
                                    owner_repo = f"local/{slug}"
                                break
                    if "/" not in owner_repo:
                        return self._json(
                            {"error": f"unknown skill: {slug}"}, status=404
                        )
                    owner, repo = owner_repo.split("/", 1)
                    candidates = [
                        SKILLS_CACHE / f"{owner}__{repo}",
                        SKILLS_CACHE / repo,
                        Path.home() / ".claude" / "skills" / repo,
                        Path.home() / ".codex" / "skills" / repo,
                    ]
                    skill_dir = next(
                        (p for p in candidates if p.exists()), None
                    )
                    if not skill_dir:
                        return self._json(
                            {"error": f"skill {owner_repo} not installed locally"},
                            status=404,
                        )
                    r = subprocess.run(
                        ["code-review-graph", "status"],
                        cwd=str(skill_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        return self._json(
                            {
                                "ok": True,
                                "skill": owner_repo,
                                "source": "crg",
                                "stats": r.stdout.strip(),
                            }
                        )
                    # ponytail: graceful — CRG needs a built graph; if status fails (no
                    # graph yet), suggest the build step in the response.
                    return self._json(
                        {
                            "ok": True,
                            "skill": owner_repo,
                            "source": "metadata",
                            "stats": "",
                            "note": (
                                "此 skill 尚未建立 CRG 图谱。运行 "
                                f"`cd {skill_dir} && code-review-graph build` 后重试。"
                                if r.stderr
                                else ""
                            ),
                            "warnings": r.stderr.strip()[:300] if r.stderr else "",
                        }
                    )
                except subprocess.TimeoutExpired:
                    return self._json({"error": "crg timeout"}, status=504)
                except Exception as e:
                    return self._json({"error": str(e)}, status=500)

            # ponytail: 非 /api 的 GET → 托管 frontend/dist（`radar.py web` 一键开浏览器即用）
            self._serve_static()

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
                    # ponytail: smart multi-CLI install — targets list lets user pick
                    # claude / codex / opencode. Default = all three.
                    raw_targets = body.get("targets")
                    if raw_targets:
                        targets = [t.strip() for t in raw_targets if t.strip()]
                    else:
                        targets = None
                    force_update = bool(body.get("force_update", False))
                    result = install_skill_from_github(
                        name, url, targets=targets, force_update=force_update
                    )
                    # ponytail: build a per-CLI human-readable status string
                    statuses = [
                        f"  · {cli}: {info['status']} ({info['detail']})"
                        for cli, info in result["targets"].items()
                    ]
                    msg = f"{name}\n" + "\n".join(statuses)
                    invalidate_local_scan()  # 「已装」徽标立即生效，不等 60s TTL
                    self._json(
                        {
                            "ok": True,
                            "message": msg,
                            "cache": str(result["cache"]),
                            "cache_state": result["cache_state"],
                            "targets": result["targets"],
                        }
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/update":
                # ponytail: 2026-09 — 更新 = install 的 force_update 变体
                # （git fetch + reset --hard origin/HEAD，不重新 clone）。
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    result = install_skill_from_github(
                        name, url, targets=body.get("targets"), force_update=True
                    )
                    statuses = [
                        f"  · {cli}: {info['status']} ({info['detail']})"
                        for cli, info in result["targets"].items()
                    ]
                    invalidate_local_scan()
                    self._json(
                        {
                            "ok": True,
                            "message": f"{name} 已更新\n" + "\n".join(statuses),
                            "cache_state": result["cache_state"],
                            "targets": result["targets"],
                        }
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/uninstall":
                # ponytail: 2026-09 — 卸载闭环：删软链接 + 缓存目录可选保留。
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    result = uninstall_skill(name)
                    invalidate_local_scan()
                    self._json({"ok": True, "message": f"{name} 已卸载", "result": result})
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
                # ponytail: fire-and-forget background crawl so UI doesn't block.
                # Log fd must be closed BEFORE Popen takes ownership so the parent doesn't
                # leak it on every /api/crawl request (long-running dev server accumulates fds).
                log_fd = os.open(DATA / "crawl.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "crawl"],
                    cwd=str(Path(__file__).parent.resolve()),
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
                return self._json(
                    {"ok": True, "message": "crawl started in background"}
                )
            self.send_error(404)

    # ponytail: bind loopback ONLY — this API can git-clone into your skills dirs;
    # exposing it to the LAN would let anyone on the network install skills.
    # ponytail: port auto-fallback — if the requested port is busy (another lodestone
    # instance, stale process, OS-assigned random port from a previous dev run, ...),
    # walk forward until we find a free one. dev.cjs parses the [serve-port] marker
    # to learn the actual port so Vite's proxy target stays in sync.
    import errno as _errno
    actual_port = port
    httpd = None
    for offset in range(50):
        try_port = port + offset
        try:
            httpd = socketserver.ThreadingTCPServer(("127.0.0.1", try_port), Handler)
        except OSError as e:
            if e.errno == _errno.EADDRINUSE:
                continue
            raise
        actual_port = try_port
        break
    if httpd is None:
        raise SystemExit(f"no free port in [{port}..{port + 49}] for radar.py serve")

    with httpd:
        url = f"http://localhost:{actual_port}"
        if actual_port != port:
            print(
                f"[serve] requested port {port} busy, bound to {actual_port} instead",
                file=sys.stderr,
            )
        # ponytail: machine-parseable port line for dev.cjs — keep the format stable.
        print(f"[serve-port] {actual_port}", flush=True)
        print(
            f"[serve] {url}  (loopback only · API: /api/data /api/local /api/top /api/install /api/crawl · Ctrl-C to stop)"
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] stopped")


def web(port=8765):
    """一键打开仪表盘：已在跑就直接开浏览器；否则后台拉起 serve 再开。
    /zp 的默认入口 — 免去手动 serve + 开浏览器两步。"""
    import webbrowser

    def radar_alive(p: int) -> bool:
        # ponytail: 不只探端口 — / 返回 HTML（带静态托管的新版 serve）且
        # /api/data 可达才是 lodestone；旧版纯 API 或无关服务都不算，
        # 端口被占时自动落到下一端口新起一个
        # ponytail: ProxyHandler({}) 强制直连 — 用户 shell 常挂全局代理（7890），
        # urlopen 默认走代理会把 loopback 健康检查挂死
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"http://127.0.0.1:{p}/", timeout=1) as r:
                if r.status != 200 or "html" not in (r.headers.get("Content-Type") or ""):
                    return False
            with opener.open(f"http://127.0.0.1:{p}/api/data", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    alive = next((p for p in range(port, port + 50) if radar_alive(p)), None)
    if alive is None:
        # ponytail: detached spawn，与 /api/crawl 同款 — start_new_session 脱离
        # /zp 的 Bash 会话，本命令返回后 serve 继续活着
        log_fd = os.open(DATA / "serve.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "serve", str(port)],
            cwd=str(Path(__file__).parent.resolve()),
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        os.close(log_fd)  # ponytail: Popen 已 dup — 父进程立刻关，防 fd 泄漏
        for _ in range(100):  # 10s 上限等端口就绪（serve 端口被占会顺延）
            alive = next((p for p in range(port, port + 50) if radar_alive(p)), None)
            if alive:
                break
            time.sleep(0.1)
        if alive is None:
            raise SystemExit(f"serve did not come up — see {DATA / 'serve.log'}")
    # ponytail: 显式 127.0.0.1 而非 localhost — macOS 浏览器可能优先解析 IPv6 ::1，
    # 若 ::1 同端口被别的服务占着（本机就发生过：synapse 文档服务在 *:8765），
    # localhost 会打开错页面。serve 只绑 IPv4 loopback，127.0.0.1 必定命中。
    url = f"http://127.0.0.1:{alive}"
    print(f"⚡ Lodestone → {url}")
    webbrowser.open(url)


def audit():
    """数据质量审计 — 去重 / 金融过滤 / 来源分布 / AI 相关性抽样。
    供人工或 /loop 定期复查：`./radar.py audit`。"""
    latest = DATA / "latest.json"
    if not latest.exists():
        print("no data/latest.json — run ./radar.py crawl first")
        return
    d = json.loads(latest.read_text())
    all_repos = list(d.get("hot_now", []))
    for c in d.get("categories", []):
        all_repos.extend(c.get("repos", []))

    print(f"=== 数据质量审计 · {d.get('fetched_at', '?')} · {len(all_repos)} 条（含跨分类重复计数）")

    # 1) 去重规则：git 完整仓库地址
    keys: dict[str, list[str]] = {}
    for r in all_repos:
        k = normalize_git_url(r.get("url")) or r["name"]
        keys.setdefault(k, []).append(r["name"])
    cross = {k: v for k, v in keys.items() if len(set(v)) > 1}
    print(f"1) 跨条目 URL 重复: {len(cross)} {'✓' if not cross else '✗'}")
    for k, v in list(cross.items())[:10]:
        print(f"   {k} ← {sorted(set(v))}")

    # 2) 金融/交易残留
    fin = sorted({r["name"] for r in all_repos if is_finance_blocked(r)})
    print(f"2) 金融/交易残留: {len(fin)} {'✓' if not fin else '✗'} {fin[:8]}")

    # 3) 来源分布（四个主源 + 辅助源）
    from collections import Counter

    src = Counter(r.get("source", "?") for r in all_repos)
    print("3) 来源分布:")
    for s, n in src.most_common(10):
        print(f"   {s:<28} {n}")

    # 4) GitHub 条目 AI 相关性抽样（5k 池口径的严格过滤在入库时已做；
    #    这里抽样检查分类条目里有没有明显不相关的）
    gh = [r for r in all_repos if normalize_git_url(r.get("url")).startswith("gh://")]
    weak = [
        r["name"]
        for r in gh
        if not is_ai_relevant(r) and not any(
            t in AI_TOPIC_BLOCKLIST for t in (x.lower() for x in (r.get("topics") or []))
        )
    ]
    # 注：分类条目允许过严格过滤（topics 变体），这里只报告数量供人工抽查
    print(f"4) GitHub 条目未过严格 AI 过滤（分类口径允许，供抽查）: {len(weak)}/{len(gh)}")
    for n in weak[:8]:
        print(f"   {n}")

    # 5) 分类规模健康度
    cats = d.get("categories", [])
    tiny = [(c["id"], len(c.get("repos", []))) for c in cats if len(c.get("repos", [])) < 5]
    print(f"5) 分类数 {len(cats)} · 过小分类(<5): {tiny or '无 ✓'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl":
        crawl()
    elif cmd == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "web":
        web(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "today":
        today()
    elif cmd == "audit":
        audit()
    else:
        print(__doc__)
        sys.exit(1)
