# -*- coding: utf-8 -*-
"""LLM enrichment — 5-dimension decision-supporting analysis per repo.

2026-09: 不是所有项目都支持 LLM；模块化设计，让三种 backend 各自可选：

  - Anthropic Claude (ANTHROPIC_API_KEY)
      POST https://api.anthropic.com/v1/messages
      默认 claude-3-5-haiku-latest（性价比最高的中端模型）

  - OpenAI 兼容 (OPENAI_API_KEY + OPENAI_BASE_URL)
      POST {base}/v1/chat/completions
      默认 gpt-4o-mini；用户可改 base_url 指向任何兼容服务（Together / Groq / Ollama）

  - Ollama 本地 (OLLAMA_HOST, 默认 http://127.0.0.1:11434)
      POST {host}/api/chat
      模型用户自选（llama3 / qwen2.5 / deepseek-coder）

每个 backend 走 stdlib urllib（不引入 SDK 依赖）。backend 自动检测：

  1. ANTHROPIC_API_KEY → Claude
  2. OPENAI_API_KEY → OpenAI 兼容
  3. OLLAMA_HOST 或 127.0.0.1:11434 在线 → Ollama
  4. 都没配 → analyze_repo 返回 None（前端降级到 3 桶 README 摘要）

成本控制：
  - 缓存命中不调 LLM（data/llm_analysis_cache.json）
  - 跳过小项目（stars < 50）— 用户感知不强，省钱
  - 跳过非 GitHub 条目（HF/arXiv/MCP — 没什么可分析的）
  - 单次 prompt 限 1500 token 入参，120 token 输出（haiku ~$0.0008）

输出 schema（强制 JSON）：
  {
    "what": str,            // 这个项目是什么（一句话定位）
    "problem": str,         // 解决什么问题（用户痛点）
    "alternatives": [str],  // 3 个同类竞品名（owner/repo 或产品名），按相关度排序
    "pros": [str],          // 3-5 条优点
    "cons": [str],          // 2-3 条缺点 / 局限
    "when_to_use": str      // 什么场景下选它（一段话）
  }

解析容错：
  - 模型偶发在 JSON 外加 ```json fences，剥掉再 parse
  - 部分字段缺失 → 该字段空串，前端按桶渲染自然隐藏
  - 完全解析失败 → 返 None，不污染缓存
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from radar_pkg import core
from radar_pkg import settings as _settings


_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


def _config() -> tuple[str, dict]:
    """Lazy lookup of active LLM config. Settings file wins; env is fallback."""
    return _settings.active_config()


def _min_stars() -> int:
    """Min stars threshold — settings.min_stars > env LLM_MIN_STARS > default 50."""
    s = _settings.load() or {}
    v = s.get("min_stars")
    if v is not None:
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
    try:
        return int(os.environ.get("LLM_MIN_STARS", "50"))
    except ValueError:
        return 50


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
    """POST JSON → JSON response。stdlib urllib，无 SDK 依赖。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{e.code} {e.reason}: {body[:200]}") from e


def detect_provider() -> str | None:
    """Return active provider name ('anthropic' / 'openai' / 'ollama' / None).
    Settings file is source of truth; env is fallback for users without the UI."""
    s = _settings.load() or {}
    chosen = s.get("provider")
    if chosen in _settings._VALID_PROVIDERS:
        # Settings has a valid provider selected — check it has minimum required fields
        fields = s.get(chosen) or {}
        if chosen == "anthropic" and fields.get("api_key"):
            return "anthropic"
        if chosen == "openai" and fields.get("api_key") and fields.get("base_url"):
            return "openai"
        if chosen == "ollama" and fields.get("host"):
            return "ollama"
        # Settings present but incomplete — fall through to env
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return "ollama"
    except Exception:
        pass
    return None


def _build_prompt(name: str, readme: str, topics: list[str], lang: str | None) -> str:
    """构造 5-dimension 分析 prompt。中文输出，与卡片其他中文描述一致。
    ponytail: 2026-09 — 5 桶对齐用户需求: 是什么 / 能干什么 / 解决什么问题 /
    同类竞品(每个竞品含优缺点) / 何时选它."""
    # 截断 README 到 ~3000 字符 — Haiku 上下文 200k，限制只为省钱 + 提速
    excerpt = (readme or "")[:3000]
    topic_str = ", ".join(topics or []) or "—"
    lang_str = lang or "?"
    return f"""你是 AI 工具评测助手。基于下面 GitHub 仓库的 README 摘录和主题标签，给出**严格 JSON**（不要 markdown fence，不要解释文字）的 5 维度分析。所有字段中文输出。

仓库：{name}
语言：{lang_str}
主题标签：{topic_str}

README 摘录：
\"\"\"
{excerpt}
\"\"\"

输出 schema（**严格按此 5 个字段输出**）：
{{
  "what": "一句话定位这个项目是什么（30 字内，动词+对象+特色）",
  "can_do": "能干什么：列出 3-5 个具体能力/特性（80 字内，逗号分隔）",
  "problem": "解决什么问题：用户痛点是什么（50 字内）",
  "alternatives": [
    {{"name": "同类项目 1（owner/repo 或产品名）", "pros": "这个竞品的主要优点（30 字内）", "cons": "这个竞品的主要缺点（30 字内）"}},
    {{"name": "同类项目 2", "pros": "...", "cons": "..."}},
    {{"name": "同类项目 3", "pros": "...", "cons": "..."}}
  ],
  "when_to_use": "什么场景下选它（不选它的场景亦可一并提及，60 字内）"
}}

约束：
- alternatives 必须是 GitHub 上真实存在的项目,或行业公认的产品名（不允许编造）
- pros/cons 来自客观事实或 README 描述,不要无中生有;每个竞品的优缺点各 1 句话
- when_to_use 面向决策者（"选它如果 X,选 Y 如果 Z"）
- 只输出 JSON,不要任何前后缀文字"""


def _extract_json(text: str) -> dict | None:
    """从模型输出提取 JSON。容忍 markdown fence / 前后缀文字。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    # 直接尝试
    try:
        return json.loads(text)
    except Exception:
        pass
    # 找第一个 { 到最后一个 } 之间的内容
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def _normalize(d: dict | None) -> dict:
    """把模型输出规整成 5d schema（缺字段填空串/空数组）。"""
    if not isinstance(d, dict):
        return {
            "what": "",
            "can_do": "",
            "problem": "",
            "alternatives": [],
            "when_to_use": "",
        }
    alts_raw = d.get("alternatives") or []
    alts_norm = []
    for a in alts_raw[:5]:
        if isinstance(a, dict):
            alts_norm.append(
                {
                    "name": str(a.get("name") or "").strip()[:100],
                    "pros": str(a.get("pros") or "").strip()[:200],
                    "cons": str(a.get("cons") or "").strip()[:200],
                }
            )
        elif isinstance(a, str) and a.strip():
            alts_norm.append({"name": a.strip()[:100], "pros": "", "cons": ""})
    return {
        "what": str(d.get("what") or "").strip()[:200],
        "can_do": str(d.get("can_do") or "").strip()[:400],
        "problem": str(d.get("problem") or "").strip()[:200],
        "alternatives": alts_norm,
        "when_to_use": str(d.get("when_to_use") or "").strip()[:400],
    }


# =========================================================================
# 各 backend 实现
# =========================================================================
def _call_anthropic(prompt: str, *, max_tokens: int = 800) -> str:
    """Claude Messages API. Reads api_key + model from settings."""
    _, fields = _config()
    api_key = fields.get("api_key", "")
    if not api_key:
        raise RuntimeError("anthropic api_key not configured")
    model = fields.get("model", "claude-3-5-haiku-latest")
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    resp = _post_json(
        _ANTHROPIC_URL,
        payload,
        {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
    )
    parts = resp.get("content") or []
    texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
    return "\n".join(texts)


def _call_openai(prompt: str, *, max_tokens: int = 800) -> str:
    """OpenAI Chat Completions API (custom base_url). Reads from settings."""
    _, fields = _config()
    api_key = fields.get("api_key", "")
    if not api_key:
        raise RuntimeError("openai api_key not configured")
    base = fields.get("base_url", "https://api.openai.com/v1").rstrip("/")
    model = fields.get("model", "gpt-4o-mini")
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    resp = _post_json(
        f"{base}/chat/completions",
        payload,
        {"Authorization": f"Bearer {api_key}"},
    )
    choices = resp.get("choices") or []
    return (choices[0].get("message") or {}).get("content", "")


def _call_ollama(prompt: str, *, max_tokens: int = 800) -> str:
    """Ollama /api/chat. Reads host + model from settings."""
    _, fields = _config()
    host = fields.get("host", "http://127.0.0.1:11434").rstrip("/")
    model = fields.get("model", "llama3.1")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": max_tokens},
        "format": "json",
    }
    resp = _post_json(f"{host}/api/chat", payload, {})
    return (resp.get("message") or {}).get("content", "")


def _dispatch(prompt: str) -> dict | None:
    """检测 backend 并调一次。失败返 None（不抛）。"""
    provider = detect_provider()
    if not provider:
        return None
    try:
        if provider == "anthropic":
            raw = _call_anthropic(prompt)
        elif provider == "openai":
            raw = _call_openai(prompt)
        else:  # ollama
            raw = _call_ollama(prompt)
        return _normalize(_extract_json(raw))
    except Exception as e:
        print(f"  [llm] {provider} call failed: {e}", file=sys.stderr)
        return None


# =========================================================================
# 缓存 + 编排
# =========================================================================
def _load_cache() -> dict:
    if not core.LLM_ANALYSIS_CACHE.exists():
        return {}
    try:
        return json.loads(core.LLM_ANALYSIS_CACHE.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        core.LLM_ANALYSIS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        core.LLM_ANALYSIS_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1)
        )
    except OSError as e:
        print(f"  [warn] llm cache write failed: {e}", file=sys.stderr)


def analyze_one(
    name: str,
    *,
    readme: str = "",
    topics: list | None = None,
    lang: str | None = None,
    stars: int = 0,
    cache: dict | None = None,
    force: bool = False,
) -> dict | None:
    """单 repo LLM 分析。cache=None 时用全局文件缓存。
    跳过条件：stars < _min_stars() / 缓存命中 / 非 GitHub。
    失败返 None（前端降级到 3 桶 README 摘要）。"""
    if not name or "/" not in name:
        return None
    if stars < _min_stars() and not force:
        return None
    cache = cache if cache is not None else _load_cache()
    key = name.lower()
    if not force and key in cache:
        return cache[key]
    prompt = _build_prompt(name, readme, topics or [], lang)
    result = _dispatch(prompt)
    if result:
        cache[key] = result
        cache[key]["_analyzed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return result


def analyze_many(repos: list, max_workers: int = 4) -> int:
    """批量分析：并发探测 + 调 LLM + 落盘。返回成功数量。
    输入 repos: list of {name, readme, topics, lang, stars}。"""
    provider = detect_provider()
    if not provider:
        print(
            "  [llm] no provider configured (set ANTHROPIC_API_KEY or OPENAI_API_KEY or start Ollama); skipping"
        )
        return 0
    print(f"  · llm analysis: provider={provider} model={_provider_model(provider)}")
    cache = _load_cache()
    todo = []
    threshold = _min_stars()
    for r in repos:
        name = r.get("name") or ""
        if "/" not in name:
            continue
        if (r.get("stars") or 0) < threshold:
            continue
        if not (r.get("readme") or ""):
            continue
        todo.append(r)
    if not todo:
        print(
            f"  · llm analysis: no eligible repos (need stars≥{threshold} + README)"
        )
        return 0
    print(
        f"  · llm analysis: {len(todo)} repos to analyze (cache: {sum(1 for r in todo if r['name'].lower() in cache)})"
    )
    completed = 0
    n_ok = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(
                analyze_one,
                r["name"],
                readme=r.get("readme", ""),
                topics=r.get("topics") or [],
                lang=r.get("lang"),
                stars=r.get("stars") or 0,
                cache=cache,
            ): r["name"]
            for r in todo
            if r["name"].lower() not in cache
        }
        for fut in as_completed(futs):
            try:
                ok = bool(fut.result())
            except Exception:
                ok = False
            if ok:
                n_ok += 1
            completed += 1
            if completed % 25 == 0:
                _save_cache(cache)
                print(f"    ... {completed}/{len(todo)} done, {n_ok} ok")
    _save_cache(cache)
    print(f"  ✓ llm analysis: {n_ok}/{len(todo)} ok")
    return n_ok


def _provider_model(provider: str) -> str:
    _, fields = _config()
    return {
        "anthropic": fields.get("model", "claude-3-5-haiku-latest"),
        "openai": fields.get("model", "gpt-4o-mini"),
        "ollama": fields.get("model", "llama3.1"),
    }.get(provider, "?")


if __name__ == "__main__":
    # CLI 调试：python3 -m radar_pkg.llm_analyze owner/repo
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cache = _load_cache()
    for name in sys.argv[1:]:
        # 调试模式：force=True 不走 stars 阈值检查
        result = analyze_one(name, cache=cache, force=True)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"  {name}: no result")
    _save_cache(cache)
