# -*- coding: utf-8 -*-
"""radar_pkg.core — 常量/分类表/过滤/归一化(无兄弟模块依赖)。
2026-09 架构拆分自 radar.py;共享可变常量(SKILLS_CACHE 等)定义于此,
使用方一律 `from radar_pkg import core` + 属性访问(patch 穿透规约)。"""
import os
import re
from pathlib import Path

# ponytail: 本文件在 radar_pkg/ 下,仓库根是上一级
ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"

# ponytail: 2026-09 — LODESTONE_HOME env override lets multi-user server deploys
# (systemd unit, Docker) point skill-cache to a project-owned path instead of
# $HOME. Default keeps the dev-machine layout ($HOME/.cache/lodestone/) for
# zero-config local runs. 兼容旧名 AI_RADAR_HOME — 老用户 .env 不必改.
_HOME = Path(
    os.environ.get("LODESTONE_HOME")
    or os.environ.get("AI_RADAR_HOME")
    or Path.home() / ".cache" / "lodestone"
)

SKILLS_CACHE = _HOME / "skills"

SKILL_ORIGINS = _HOME / "origins.json"

README_ZH_CACHE = DATA / "readme_zh_cache.json"

# ponytail: 2026-09 — SKILL.md 探测缓存。{owner/repo: {is_skill, probed_at, branch}}。
# 增量：未命中才探测；raw.githubusercontent.com 无 API rate limit，可放心大批量。
SKILL_PROBE_CACHE = DATA / "skill_probe_cache.json"

# ponytail: 2026-09 — LLM 5 维度分析缓存。{owner/repo: {what, problem,
# alternatives, pros, cons, when_to_use, _analyzed_at}}。按 stars 阈值过滤 +
# cache 命中跳过，单 repo LLM 调一次永久复用。
LLM_ANALYSIS_CACHE = DATA / "llm_analysis_cache.json"

# ponytail: 2026-09 — LLM settings UI 持久化（gitignore 中）。crawl 读这文件获取
# provider + endpoint + key + model。
SETTINGS_PATH = DATA / "settings.json"

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

TOP_5K_QUERIES = list(dict.fromkeys([
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
    # ponytail: 2026-09 — 主要 AI 厂商 org 级查询. 新模型/新框架发布时
    # 作者未必立即打 topic 标签,org: 抓全这家厂商所有仓库(含未打 tag 的).
    # 单条 org: 查询 ≠ 主题查询: 一个 query 拉该 org 所有 stars:>500 仓库,
    # 单 query 即覆盖整个厂商生态. 加 30 条 org 只多 5 个 GraphQL 请求,
    # 换来主流 AI 厂商的新仓库 0 延迟覆盖.
    # === 模型权重厂商 (国内 + 海外) ===
    "org:deepseek-ai stars:>100",
    "org:QwenLM stars:>100",
    "org:meta-llama stars:>100",
    "org:mistralai stars:>100",
    "org:OpenBMB stars:>50",
    "org:THUDM stars:>100",
    "org:MiniMax stars:>100",
    "org:baichuan-inc stars:>50",
    "org:moonshotai stars:>50",
    "org:inclusionAI stars:>50",
    "org:OpenGVLab stars:>50",
    "org:Tencent-Hunyuan stars:>50",
    "org:Kwai-Kolors stars:>50",
    # === 海外闭源模型 + Agent 平台 ===
    "org:anthropics stars:>100",      # Claude / MCP SDK / 官方 skill
    "org:openai stars:>100",          # Codex / openai-python / eval
    "org:google-deepmind stars:>100",
    "org:cohere-ai stars:>100",
    "org:Stability-AI stars:>100",
    "org:Black-Forest-Labs stars:>100",  # FLUX
    "org:comfyanonymous stars:>100",     # ComfyUI
    # === 推理 + Agent 框架 ===
    "org:huggingface stars:>100",      # transformers / diffusers / smolagents
    "org:ollama stars:>100",
    "org:vllm-project stars:>100",
    "org:ggerganov stars:>100",        # whisper.cpp / llama.cpp
    "org:ggerganov-face stars:>100",
    "org:ggerganov-ggml stars:>100",
    "org:langchain-ai stars:>100",
    "org:run-llama stars:>100",        # LlamaIndex
    "org:openai-agents stars:>100",    # openai-agents SDK
    "org:crewAIInc stars:>100",        # CrewAI 官方
    "org:NVIDIA stars:>200",           # NeMo / TensorRT-LLM
    # === Awesome 列表 (大量 curated resources, 但 topic 通用) ===
    "stars:>5000 awesome-llm in:name",
    "stars:>5000 awesome-ai in:name",
    "stars:>5000 awesome-claude in:name",
    "stars:>5000 awesome-agents in:name",
    # ponytail: 2026-09 P2 — Chinese AI tool coverage. Project may not tag GitHub topics
    # in English; description is in Chinese. stars:>500 catches mainline, not noise.
    'stars:>500 "LLM 智能体" in:name,description',
    'stars:>500 "知识库" in:name,description',
    'stars:>500 "检索增强" in:name,description',
    'stars:>500 "智能对话" in:name,description',
    'stars:>500 "向量化" in:name,description',
    'stars:>500 "RAG 框架" in:name,description',
    'stars:>500 "大模型应用" in:name,description',
    'stars:>500 "推理引擎" in:name,description',
    'stars:>500 "AI 工具" in:name,description',
    'stars:>500 "embedding 引擎" in:name,description',
    'stars:>500 "智能客服" in:name,description',
    'stars:>500 "AI 助手" in:name,description',
    'stars:>500 "LLM 推理" in:name,description',
    'stars:>500 "向量数据库" in:name,description',
    'stars:>500 "Prompt 工程" in:name,description',
    'stars:>500 "多模态" in:name,description',
    'stars:>500 "深度学习" in:name,description',
    'stars:>500 "机器学习" in:name,description',
    'stars:>500 "模型训练" in:name,description',
    'stars:>500 "模型推理" in:name,description',
    'stars:>500 "AI 推理" in:name,description',
    'stars:>500 "推理框架" in:name,description',
    'stars:>500 "LLM 服务" in:name,description',
    'stars:>500 "大模型" in:name,description',
    'stars:>500 "AI 应用" in:name,description',
    'stars:>500 "AI 平台" in:name,description',
    'stars:>500 "对话系统" in:name,description',
    'stars:>500 "智能体框架" in:name,description',
    'stars:>500 "RAG 系统" in:name,description',
    'stars:>500 "LLM 框架" in:name,description',
    'stars:>500 "生成式 AI" in:name,description',
    'stars:>500 "智能问答" in:name,description',
    'stars:>500 "对话机器人" in:name,description',
    'stars:>500 "向量搜索" in:name,description',
    'stars:>500 "AI 编程" in:name,description',
    'stars:>500 "代码助手" in:name,description',
    'stars:>500 "AI 代码" in:name,description',
    'stars:>500 "代码生成" in:name,description',
    'stars:>500 "智能搜索" in:name,description',
    'stars:>500 "AI 绘画" in:name,description',
    'stars:>500 "图像生成" in:name,description',
    'stars:>500 "AI 写作" in:name,description',
    'stars:>500 "AI 翻译" in:name,description',
    'stars:>500 "AI 推荐" in:name,description',
    'stars:>500 "推荐系统" in:name,description',
    'stars:>500 "AI 搜索" in:name,description',
    'stars:>500 "AI 训练" in:name,description',
    'stars:>500 "模型部署" in:name,description',
    'stars:>500 "LLM 部署" in:name,description',
    'stars:>500 "大模型服务" in:name,description',
    'stars:>500 "智能分析" in:name,description',
    'stars:>500 "AI 客服" in:name,description',
    # ponytail: 2026-09 P2 — Chinese AI company orgs. Single org: query covers the
    # vendor's full repo list (≥ stars threshold). Batch related orgs into one
    # query to save API quota.
    'org:bytedance,org:01.AI,org:zhipuai,org:BAAI,org:FudanNLP,org:RUC-NLPIR stars:>100',
    'org:damo-alibaba,org:modelscope stars:>100',
    'org:Tongyi-MLLM,org:FunAudioLLM,org:alibaba-damo-academy stars:>50',
    'org:datawhalechina,org:MLNLP-CUHKSZ,org:OpenNLPLab stars:>50',
    # 海外主流 AI orgs (新加)
    'org:Vercel,org:replicate,org:ReplicateHQ,org:ai21-labs stars:>100',
    'org:microsoft,org:google-research,org:Meta-AI stars:>100',
    'org:apple,org:salesforce,org:elastic stars:>100',
    'org:redis,org:hashicorp,org:pydantic stars:>100',
    'org:groq,org:anyscale,org:perplexityai stars:>100',
    'org:runwayml,org:Stability-AI,org:Black-Forest-Labs stars:>100',
    'org:midjourney,org:cognitiveservices,org:huggingface stars:>100',
    'org:openai,org:anthropics,org:cohere-ai stars:>100',
    'org:google-deepmind,org:oobabooga,org:ggerganov stars:>100',
    'org:NVIDIA,org:AMD-AIG-AIML,org:CohereForAI stars:>100',
    'org:lmsysorg,org:SkunkworksAI,org:OptimalScale stars:>100',
    'org:langchain-ai,org:run-llama,org:crewAIInc stars:>100',
    'org:BerriAI,org:chroma-core,org:qdrant stars:>100',
    'org:openobserve,org:raga-ai-hub,org:whylabs stars:>100',
    'org:predibase,org:deepset-ai,org:arize-ai stars:>100',
    'org:MongoDB,org:supabase,org:neondatabase stars:>100',
    # awesome 列表拉取的入口 — 给 awesome-lists 源用 query anchor
    'stars:>500 awesome-rag in:readme',
    'stars:>500 awesome-llm in:readme',
    'stars:>500 awesome-llm-tools in:readme',
    'stars:>500 awesome-chinese-llm in:readme',
    'stars:>500 awesome-coding-agent in:readme',
    'stars:>500 awesome-mcp-server in:readme',
    'stars:>500 awesome-rag-agent in:readme',
    'stars:>500 awesome-llm-zh in:readme',
    'stars:>500 awesome-prompt-engineering in:readme',
    # ponytail: 2026-09 P2 — 放宽 topic 过滤, 让 deep-learning / machine-learning
    # 项目 (不显式标 ai topic) 进入 5k 池。5k 池后还会过一次 AI_TOPIC_HARD 过滤。
    'stars:>2000 topic:machine-learning',
    'stars:>1000 topic:machine-learning',
    'stars:>2000 topic:deep-learning',
    'stars:>1000 topic:deep-learning',
    'stars:>1000 topic:neural-network',
    'stars:>1000 topic:data-science',
    'stars:>500 topic:mlops',
    'stars:>500 topic:ml-engineering',
    'stars:>500 topic:pytorch',
    'stars:>500 topic:tensorflow',
    'stars:>500 topic:huggingface',
    'stars:>500 topic:nlp',
    'stars:>500 topic:natural-language-processing',
    'stars:>500 topic:computer-vision',
    'stars:>500 topic:transformer',
    'stars:>500 topic:gpt',
    'stars:>500 topic:llm',
    'stars:>500 topic:chatgpt',
    'stars:>500 topic:openai',
    'stars:>500 topic:claude',
    'stars:>500 topic:anthropic',
    'stars:>500 topic:gemini',
    'stars:>500 topic:llama',
    'stars:>500 topic:qwen',
    'stars:>500 topic:rag',
    'stars:>500 topic:embedding',
    'stars:>500 topic:vector-database',
    'stars:>500 topic:multi-agent',
    'stars:>500 topic:agent',
    'stars:>500 topic:mcp',
]))

TOP_5K_LIMIT = 1200

AI_TOPIC_HARD = frozenset(
    {
        # ponytail: 2026-09 — narrow keywords removed from QUERY search because
        # they over-match (a "mcp-server" topic tag captures generic webservers),
        # but KEPT here in the AI filter — repos explicitly tagged "mcp-server"
        # ARE AI-related by the GitHub topic-tag convention.
        "mcp-server",
        "mcp-servers",
        "agent-skills",
        "agentic",
        "agentic-ai",
        "spring-ai",
        "springai",
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
        "autonomous-agent",
        "multi-agent",
        "ai-agent",
        # ponytail: 2026-09 补齐 topics 变体 — 分类结果启用完整过滤后
        # 这些变体缺了会误伤正经 AI 项目（Qwen-VL / playwright-mcp 实测踩过）
        "mcp",
        "mcp-client",
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
        "machine-learning",
        "deep-learning",
        "neural-network",
        "tensorflow",
        "pytorch",
        "data-science",
        "mlops",
    }
)

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

NON_AI_DEV_DESC_BLOCKLIST = re.compile(
    r"(?:trading\s+(?:bot|agent|framework|strategy|system|platform)"
    r"|stock\s+(?:market|price|prediction|trading|analysis)"
    r"|algorithmic\s+trading|quantitative\s+finance|financial\s+market"
    r"|股票|炒股|量化交易|证券|金融行情)",
    re.IGNORECASE,
)

# ponytail: 2026-09 — 通用工具黑名单. 即便有 langchain/openai 等弱 AI topic,
# 如果描述清楚说是通用工具, 一律拒绝. 实测 n8n/yt-dlp/markitdown 借
# "AI capabilities" / "langchain integration" / "openai sdk" 等关键词蒙混
# 进 AI 雷达 — 这是用户期待的「专注 AI 工具」平台的污染.
# 三道闸门: ① finance 屏蔽(已有) ② 黑名单(本次新增) ③ 强 AI 信号
# ponytail: 2026-09 — 通用工具黑名单,topic 级. 比描述正则更可靠:
# 通用工具蹭 langchain/openai/claude topic 时 description 也常带 "AI",
# 但它们的 topic 几乎稳定不变(downloader, youtube-dl, markdown, ...).
# 一票命中即拒;白名单 (CURATED_ALLOWLIST) 仍可旁路.
NON_AI_TOPIC_BLOCKLIST = frozenset(
    {
        # 媒体下载/处理
        "downloader", "video-downloader", "youtube-dl", "yt-dlp",
        "video-converter", "audio-converter", "media-converter",
        "subtitle-downloader", "media-downloader",
        # 文档/Markdown/Office 转换 — markitdown 这类
        "markdown-converter", "pdf-converter", "document-converter",
        "office-document", "file-converter",
        "microsoft-office",  # markitdown / Word 转换工具
        "docx", "pptx", "xlsx",  # Office 文档处理(常见于转换工具)
        # 工作流自动化 (n8n 这类)
        "ipaas", "workflow-automation", "workflow-engine",
        # 包管理 / 版本管理 / CLI 通用工具
        "version-manager", "package-manager", "cli-app",
        # 通用 chat UI 库
        "chat-ui", "chat-component",
        # 通用 GUI 框架
        "gui-framework", "ui-framework",
    }
)

_SEARCH_PACE = {"sleep": 2.0}

GH_SEARCH_STATS = {"failed": 0}

CRAWL_LOCK = DATA / "crawl.lock"

CRAWL_LOCK_STALE_S = 30 * 60

# ponytail: 2026-09 — summarize (LLM 5-bucket) 用独立锁。crawl 与 summarize 是
# 两件事,前端「生成 5 桶」按钮触发 summarize 时不应被运行中的 crawl 阻塞
# （crawl 不再自动跑 LLM,二者只共享 README 缓存）。
SUMMARIZE_LOCK = DATA / "summarize.lock"

SUMMARIZE_LOCK_STALE_S = 30 * 60

# ponytail: 2026-09 — install / uninstall / upgrade 共享一把锁。
# 与 crawl / summarize 并行不互斥(用户可以一边看数据一边升级 skill),
# 但 install 本身必须串行 — 同时两个 Popen 都 git clone 到同目录会断链。
# 同一 PID-aware 模式:crawl_lock_held / summarize_lock_held 都已实现,
# 这里复用 acquire_lock / release_lock + lock_held 三件套,所有锁共享语义。
INSTALL_LOCK = DATA / "install.lock"
INSTALL_LOCK_STALE_S = 30 * 60

# ponytail: 2026-09 — install 进度状态(给前端 UpgradeProgressBanner 轮询)。
# 与 LLM_STATUS_PATH 同款结构:{running, current, total, label, started_at, ...}
INSTALL_STATUS_PATH = DATA / "install_status.json"

# ponytail: 2026-09 — install 事件追加日志(append-only)。每次 install/uninstall/upgrade
# 写一行,UI 可选展示「历史」。文件不存在时首次写入自动建。
INSTALL_LOG_PATH = DATA / "install_log.json"
INSTALL_LOG_MAX = 500  # 环形 buffer,超过截断前半

# LLM 摘要状态 — /api/llm/status 给前端「上次生成于 X · 共 N 张卡」展示。
# 由 summarize_repos() 写,UI 轮询时读。
LLM_STATUS_PATH = DATA / "llm_status.json"

FRONTMATTER_DESC = re.compile(
    r"^description:\s*(.+?)(?=\n[a-z\-]+:|\n---|\Z)", re.MULTILINE | re.DOTALL
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
    """Strict AI filter — three gates (any failure → reject):
      Gate 1: not in finance/crypto blacklist (is_finance_blocked)
      Gate 2: topics don't match NON_AI_TOPIC_BLOCKLIST (通用工具黑名单)
      Gate 3: name is in CURATED_ALLOWLIST (whitelist bypass) OR
               has at least one AI_TOPIC_HARD topic OR
               name+description contains a strong AI_TEXT_HINTS phrase

    ponytail: 2026-09 — three-gate rewrite. 此前只有 ① + ③ → yt-dlp/n8n/markitdown
    这类「蹭 AI topic 标签」的通用工具滑进 hot_now 前 10. Gate 2 用 topic 黑名单
    (download/markdown-converter/workflow-automation 等)拦截,topic 比描述更稳定.
    注意:分类查询的结果不要用这个函数整体过滤 — category query 本身就是 AI
    信号(topic:llm / topic:langgraph...), 只需 is_finance_blocked;严格过滤
    用于来源宽泛的 5k 大池("stars:>500 xxx" 这类)."""
    if is_finance_blocked(repo):
        return False
    # ponytail: 用户精选赛道白名单(CURATED_ALLOWLIST 在上方定义)— agent 基建类
    # 项目 topics 无 AI 关键词但属于雷达定位,豁免 AI 相关性判定(金融拦截不豁免).
    if (repo.get("name") or "").lower() in CURATED_ALLOWLIST:
        return True
    topics = [t.lower() for t in (repo.get("topics") or [])]
    # Gate 2: 通用工具 topic 黑名单. 一票命中即拒 (除白名单外).
    if topics and any(t in NON_AI_TOPIC_BLOCKLIST for t in topics):
        return False
    blob_topics = " ".join(topics)
    # ponytail: 2026-09 P3 修复 — 词边界匹配替代子串匹配。AI_TOPIC_HARD 是硬编码
    # 短 token,未来若加 "ai" / "ml" 这类 2 字母串,旧的子串匹配会误命中任何含
    # "ai" 子串的 topic("available", "tailwind"...)。改用整词包含;topics 数组已
    # 规范化为 token,用 `h in topics` 即可。
    if any(h in topics for h in AI_TOPIC_HARD):
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
        # open-source release: removed "lodestone/hallmark" + "lodestone/ai-agent-book"
        # (personal GitHub repos; open-source seed list shouldn't feature them).
        "Shubhamsaboo/awesome-llm-apps",  # 100+ AI agent apps (125k stars, generic topics)
        "stablyai/orca",  # desktop ADE for parallel coding agents (24k stars)
        "GaoSSR/best-claude-hud",  # Claude HUD plugin
        "lidge-jun/opencodex",  # universal LLM proxy for codex/claude-code
        "volcengine/OpenViking",  # ByteDance context DB for agents (27k stars)
        "msitarzewski/agency-agents",  # complete AI agency (135k stars, no topics)
        # Safety net
        "all-hands-ai/openhands",  # common 2025 coding agent
    }
)
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


def atomic_json_write(path, payload) -> None:
    """ponytail: 2026-09 — 集中原子写。tmp + replace 防两类数据丢失:
    1. 进程被杀中途截断 → tmp 留下垃圾,.json 仍是上一次完整数据
    2. 并发 writer A 写到一半被 B 覆盖 → A 丢 B 写完,B 写完不丢
    替代原 7 处 `Path(path).write_text(json.dumps(...))` 直写。"""
    import json
    from pathlib import Path as _P
    p = _P(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    tmp.replace(p)


# ponytail: 2026-09 — install / upgrade / uninstall 共用锁三件套。
# 与 crawl_lock_held / summarize_lock_held 同模式(PID alive + 30min stale),
# 抽成参数化函数减少重复。返回 bool 表示锁当前是否 held。
# ponytail: 2026-09 — PID-aware link(2) 锁。原子性靠 OS 层 link(2) 而不是 O_EXCL,
# 防止 30min stale 撞锁时链式踩踏(原实现释放时不验证 PID,任何进程都能删任何 lock)。
# 锁文件 = 指向 PID file 的硬链,holder 进程死后 OS 自动清理。
def _pid_alive(pid: int) -> bool:
    import os as _os
    if pid <= 0: return False
    try: _os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True  # 进程存在但无权限,算活


def _parse_pid_from_lock(lock_path) -> int:
    import re
    # 文件名格式: install.lock.<PID>;lock_path.name = "install.lock"
    # 当 O_EXCL 写时只写数字 (旧路径),文件名 .<pid> 是新路径。
    try:
        text = lock_path.read_text().strip()
        return int(text)
    except (ValueError, OSError):
        pass
    # 尝试文件名后缀
    m = re.search(r"\.(\d+)$", lock_path.name)
    return int(m.group(1)) if m else 0


def acquire_named_lock(lock_path, stale_s: int) -> bool:
    """True = acquired; False = another lock-holder is active (or holder alive).
    旧实现:O_EXCL + 文件内容 PID;新实现:link(2) 原子创建(在锁文件 inode 不存在时)。
    stale 检测同时清理死 PID 子锁文件(防止锁泄漏)。
    ponytail: 锁文件内容写 PID — link(2) 复用 inode 后文件名虽不直接带 pid,
    但 read_text() 仍能解析。release 时按文件名后缀 OR 内容 PID 都兼容。"""
    import os as _os, time as _t
    pid = _os.getpid()
    pidfile = lock_path.with_name(f"{lock_path.name}.{pid}")
    # ponytail: 先清理任何 stale 的子锁文件(死 PID 或超时),为 link(2) 扫清场地。
    try:
        for old in list(lock_path.parent.glob(f"{lock_path.name}.*")):
            try:
                # 跳过主锁文件本身 — 主锁文件名是 install.lock (无 .<pid> 后缀),
                # glob 不会匹到 (require literal "." between lock and pid).
                if old == lock_path:
                    continue
                old_pid = int(old.name.rsplit(".", 1)[1])
                age = _t.time() - old.stat().st_mtime
                if not _pid_alive(old_pid) or age > stale_s:
                    old.unlink(missing_ok=True)
            except (ValueError, OSError):
                old.unlink(missing_ok=True)
    except OSError:
        pass
    # link(2) 原子创建主锁 + 写 PID 进 inode。已有则失败。
    try:
        pidfile.write_text(str(pid))
        _os.link(str(pidfile), str(lock_path))
        pidfile.unlink(missing_ok=True)
        return True
    except FileExistsError:
        # 锁已存在 — 三种 steal 条件:
        #   (A) holder_pid > 0 + 进程已死 → 安全偷
        #   (B) holder_pid > 0 + 进程活 + age > stale_s → D-state,信号收不到但锁很久没动,偷
        #   (C) holder_pid == 0 → 内容损坏(不知真假死活),保守不偷,等真死或 30min 过期
        holder_pid = _parse_pid_from_lock(lock_path)
        try:
            age = _t.time() - lock_path.stat().st_mtime
        except OSError:
            age = 0
        if holder_pid == 0:
            # ponytail: 内容损坏的锁不偷 — 万一真有别的进程在用(只是 metadata 损坏),
            # 我们偷了会跟他 race。安全起见等 stale 后再试。
            if age > stale_s:
                lock_path.unlink(missing_ok=True)
                return acquire_named_lock(lock_path, stale_s)
            return False
        if _pid_alive(holder_pid):
            # 进程活但可能 D-state — 只在超 stale_s 时偷
            if age > stale_s:
                lock_path.unlink(missing_ok=True)
                return acquire_named_lock(lock_path, stale_s)
            return False
        # 进程死了 — 偷
        lock_path.unlink(missing_ok=True)
        return acquire_named_lock(lock_path, stale_s)


def release_named_lock(lock_path) -> None:
    """只删自己 PID 的锁(防止链式踩踏)。"""
    import os as _os
    pid = _os.getpid()
    pidfile = lock_path.with_name(f"{lock_path.name}.{pid}")
    # 兼容旧锁(无 .<pid> 后缀,只写数字):删 lock_path 自身
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass
    pidfile.unlink(missing_ok=True)


def named_lock_held(lock_path, stale_s: int) -> bool:
    """Non-acquiring probe。mtime 内 = True;mtime 超 = 看 PID 活否。"""
    import os as _os
    import time as _t
    if not lock_path.exists():
        return False
    try:
        st_mtime = lock_path.stat().st_mtime
    except OSError:
        return False
    if _t.time() - st_mtime <= stale_s:
        return True
    try:
        pid = int(lock_path.read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        _os.kill(pid, 0)
        return True
    except OSError:
        return False


# ponytail: 2026-09 — install 进度状态写盘。analyze_many 风格的 _write_progress
# 但通用化 — 任何 install 操作都能调。可选字段:label (e.g. "升级 anthropic/skills"),
# current/total,started_at,finished_at。
def write_install_status(**fields) -> None:
    """与 _write_llm_status 同款 atomic,带 updated_at 自动戳。"""
    import datetime as _dt
    import json as _json
    payload = {}
    if INSTALL_STATUS_PATH.exists():
        try:
            payload = _json.loads(INSTALL_STATUS_PATH.read_text())
        except Exception:
            payload = {}
    payload.update(fields)
    payload["updated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    atomic_json_write(INSTALL_STATUS_PATH, payload)


# ponytail: 2026-09 — upgradable cache(/api/local 给前端展示 "可升级" 用)。
# compute_upgradable 要 N 次 ls-remote,100 个 skill 串行 ~5-15s/个 = 25min。
# stale-while-revalidate:cache 文件 mtime < 5min 直接返回,过期触发后台线程刷新
# 旧 cache 同时返 — UI 永远秒开,后台静默刷新,下次刷新拿到最新。
UPGRADABLE_CACHE_PATH = DATA / "upgradable_cache.json"
UPGRADABLE_CACHE_TTL_S = 5 * 60  # 5 min


def read_upgradable_cache_or_none() -> dict | None:
    """返回 upgradable 字典(若 cache 存在且 < TTL),否则 None。"""
    import json as _json
    import time as _t
    if not UPGRADABLE_CACHE_PATH.exists():
        return None
    try:
        age = _t.time() - UPGRADABLE_CACHE_PATH.stat().st_mtime
        if age > UPGRADABLE_CACHE_TTL_S:
            return None
        return _json.loads(UPGRADABLE_CACHE_PATH.read_text())
    except (OSError, ValueError):
        return None


# ponytail: 2026-09 — 返回 cache 元信息(age / mtime / entries)给前端 banner。
# 之前 /api/local 只返 upgradable_map dict,前端不知道 cache 是新的还是 6h 前的,
# 也无法显示"正在算"等中间态。
def read_upgradable_cache_meta() -> dict:
    """返回 {exists, mtime, age_s, total, computing, last_trigger_at}。"""
    import time as _t
    info = {
        "exists": False,
        "mtime": None,
        "age_s": None,
        "total": 0,
        "computing": False,
        "last_trigger_at": None,
    }
    if not UPGRADABLE_CACHE_PATH.exists():
        return info
    try:
        st = UPGRADABLE_CACHE_PATH.stat()
        cache = _t.time() - st.st_mtime
        info.update({
            "exists": True,
            "mtime": st.st_mtime,
            "age_s": cache,
        })
        try:
            data = __import__("json").loads(UPGRADABLE_CACHE_PATH.read_text())
            info["total"] = len(data)
        except Exception:
            pass
    except OSError:
        pass
    return info


# ponytail: 2026-09 — compute 状态标记。Popen 起来时 /api/local/refresh 写
# `computing=True`,跑完(成功/失败)写 `computing=False` + updated_at。
# 跨进程:Popen 进程死亡但 computing=True 残留 → 看 PID 活否,死了就清掉
# (与 install_lock 同模式,防 daemon 死锁了状态)。
_REFRESH_STATUS_PATH = DATA / "refresh_status.json"


def set_refresh_status(**fields) -> None:
    payload = {}
    if _REFRESH_STATUS_PATH.exists():
        try:
            payload = __import__("json").loads(_REFRESH_STATUS_PATH.read_text())
        except Exception:
            payload = {}
    payload.update(fields)
    payload["updated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    atomic_json_write(_REFRESH_STATUS_PATH, payload)


def read_refresh_status() -> dict:
    if not _REFRESH_STATUS_PATH.exists():
        return {}
    try:
        return __import__("json").loads(_REFRESH_STATUS_PATH.read_text())
    except Exception:
        return {}


def write_upgradable_cache(payload: dict) -> None:
    try:
        atomic_json_write(UPGRADABLE_CACHE_PATH, payload)
    except OSError:
        pass  # 缓存写失败不影响主流程


# ponytail: 2026-09 P3 — 单条 skill 升级/卸载后立刻让 cache 反映新状态,而不是
# 等 daemon 5 min 周期。调用方:install.upgrade_one 成功分支 + uninstall_skill。
def invalidate_upgradable_cache_for(name: str) -> None:
    """把 cache 里该 skill 标为 up_to_date(或直接删除),写回。"""
    cache = read_upgradable_cache_or_none()
    if cache is None:
        return
    if name in cache:
        cache[name]["upgradable"] = False
        cache[name]["reason"] = "up_to_date"
        cache[name]["local_sha"] = (
            cache[name].get("remote_sha")
            or cache[name].get("local_sha")
        )
    else:
        # 不在 cache(刚装的 skill)— 删它不影响,daemon 下次会算
        return
    write_upgradable_cache(cache)


_UPGRADABLE_DAEMON_STARTED: set = set()


def start_upgradable_refresh_daemon(interval_s: int = 300) -> None:
    """后台 daemon 线程 — 每 interval_s 秒重算一次 upgradable 并写 cache。

    ponytail: 2026-09 — dedup 用稳定字符串 key,而非 id(skills)。前者每次 /api/local
    调用都新建 dict → id 永远不同 → daemon线程无限泄漏,触发 GitHub 60/hr 限流,
    整个 upgradable 系统静默失效。
    ponytail: 2026-09 — 每次循环内 re-detect 拿最新 skills,而非闭包捕获首次调用,
    否则新装的 skill 永远不进 cache。
    """
    import threading as _thr
    import time as _t

    cache_key = "local-skills-v1"
    if cache_key in _UPGRADABLE_DAEMON_STARTED:
        return
    _UPGRADABLE_DAEMON_STARTED.add(cache_key)

    def _loop():
        from radar_pkg.detect import detect_local_skills
        from radar_pkg.install import compute_upgradable
        def _cb(cur, total, name):
            # ponytail: 2026-09 — daemon 跑 compute 时也上报进度,前端 banner
            # 不只在手动 refresh 时显示「5/292」,daemon 自动周期跑也有。
            try:
                set_refresh_status(
                    computing=True, current=cur, total=total,
                    current_name=name,
                )
            except Exception:
                pass
        while True:
            try:
                local = detect_local_skills()
                # 仅在确实要写进度时启用 callback(否则默认空函数开销 0)
                skills = local.get("skills") or {}
                payload = compute_upgradable(skills, progress_callback=_cb)
                write_upgradable_cache(payload)
            except Exception:
                pass
            finally:
                # ponytail: 不管成功失败,daemon 跑完一轮必须 computing=False。
                # 之前漏了 finally,导致 daemon 跑完后 computing 永远 true。
                try:
                    set_refresh_status(computing=False, current_name="")
                except Exception:
                    pass
            _t.sleep(interval_s)

    _thr.Thread(target=_loop, daemon=True, name="upgradable-refresher").start()


def read_install_status() -> dict:
    """Mirror of _write_llm_status read side。"""
    import json as _json
    if INSTALL_STATUS_PATH.exists():
        try:
            return _json.loads(INSTALL_STATUS_PATH.read_text())
        except Exception:
            return {}
    return {}


def append_install_log(entry: dict) -> None:
    """追加到 INSTALL_LOG_PATH(append-only 环形)。失败静默,日志不该破坏主流程。"""
    import datetime as _dt
    import json as _json
    entry = {"at": _dt.datetime.now().isoformat(timespec="seconds"), **entry}
    try:
        if INSTALL_LOG_PATH.exists():
            try:
                data = _json.loads(INSTALL_LOG_PATH.read_text())
            except Exception:
                data = []
        else:
            data = []
        data.append(entry)
        if len(data) > INSTALL_LOG_MAX:
            data = data[-INSTALL_LOG_MAX:]
        atomic_json_write(INSTALL_LOG_PATH, data)
    except Exception:
        pass
