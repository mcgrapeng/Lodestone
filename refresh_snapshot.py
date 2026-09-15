#!/usr/bin/env python3
"""Augment data/latest.json with fresh sources + complete every field.

Runs:
  1. MCP Registry fetcher → fill "MCP Servers & Clients" category (was 10)
  2. HF Models fetcher → new "🤗 HuggingFace 热门 Models" category
  3. HF Spaces fetcher → refresh existing category
  4. For every repo: fill lang/topics/facts/best_category/local_installed/trending/is_fresh
  5. Translate any missing desc_zh via Google Translate
  6. Recompute stars_today from trending repos

Idempotent — safe to re-run any time. Writes to data/latest.json.
"""

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from radar import (  # noqa: E402
    DATA, facts_for_repo, translate_batch,
    fetch_huggingface_trending,
)
from sources.mcp_registry import fetch_mcp_registry  # noqa: E402
from sources.huggingface_models import fetch_huggingface_models_trending  # noqa: E402


# Categories whose repos get best_category = "id" — meaning they belong to that bucket.
# Top_5k repos (not in any category) get matched by topic keywords.
CATEGORY_TOPIC_HINTS = {
    "agent": ["agent", "ai-agent", "agents", "claude-code", "claude", "autonomous",
              "multi-agent", "agentic", "skills", "ai-skills"],
    "memory": ["rag", "vector-database", "vector", "embedding", "embeddings",
               "llm-memory", "agent-memory", "pgvector", "long-term-memory",
               "graphrag", "knowledge-graph"],
    "llm": ["llm", "chatbot", "prompt-engineering", "openai", "anthropic",
            "claude-api", "gpt", "chatgpt"],
    "devtool": ["copilot", "ai-coding", "code-agent", "developer-tools"],
    "workflow": ["langgraph", "workflow", "orchestration", "langchain", "pipeline",
                 "agentic-workflow"],
    "multimodal": ["multimodal", "vision", "text-to-video", "vision-language-model"],
    "finetune": ["fine-tuning", "lora", "peft", "llama-factory"],
    "eval": ["llm-evaluation", "benchmark", "ragas", "promptfoo"],
    "ide": ["cursor", "aider", "cline", "continue", "windsurf", "ai-ide"],
    "gateway": ["litellm", "openrouter", "llm-gateway", "llm-router", "llm-proxy"],
    "observability": ["langfuse", "llm-observability", "helicone", "llmops", "phoenix"],
    "awesome": ["awesome-ai", "awesome-llm", "awesome-claude"],
    "mcp": ["mcp", "mcp-server", "model-context-protocol"],
    "voice": ["voice", "tts", "speech", "asr", "livekit", "pipecat", "vocode",
              "realtime-ai"],
    "browser": ["browser-use", "browser-automation", "computer-use", "web-agent"],
    "huggingface": ["huggingface"],
    "hf_models": ["huggingface", "model"],
    "security": ["prompt-injection", "llm-security", "ai-safety", "red-team",
                "ai-alignment", "prompt-guard"],
    "robotics": ["embodied-ai", "robotics", "robot-learning", "sim-to-real",
                 "open-x-embodiment", "humanoid"],
}


def assign_best_category(repo):
    """For 5k+ pool repos (no category), pick best_category by topic match.
    Returns category_id or None."""
    topics = set(t.lower() for t in (repo.get("topics") or []))
    if not topics:
        return None
    best = None
    best_score = 0
    for cat_id, hints in CATEGORY_TOPIC_HINTS.items():
        score = sum(1 for h in hints if h in topics)
        if score > best_score:
            best_score = score
            best = cat_id
    return best


def is_fresh(r, days=14):
    """True if pushed within `days`."""
    pushed = r.get("pushed") or r.get("updated") or ""
    try:
        d = datetime.date.fromisoformat(pushed[:10])
        return (datetime.date.today() - d).days <= days
    except Exception:
        return False


def load_local_installed_names():
    """Build set of LOWERCASE names (bare repo seg + owner/repo) from detect_local_skills().
    2026-09: 统一小写 + 覆盖全平台(claude/codex/opencode/easycode)+ 插件 bare 名 —
    此前大小写敏感(affaan-m/ECC vs 链接名 ecc)且漏掉 opencode 装的技能与无 url 插件。"""
    try:
        import radar
        local = radar.detect_local_skills(force=True)
        names = set()
        # skills / commands / agents are dicts {name: meta}
        for src in ("skills", "commands", "agents"):
            for n, meta in (local.get(src) or {}).items():
                names.add(n.lower())  # bare repo name
                if isinstance(meta, dict):
                    full = meta.get("origin_full") or radar._owner_repo_from_url(
                        meta.get("url") or ""
                    )
                    if full:
                        names.add(full.lower())
        # plugins is a list — 无 url 的插件(如 ecc@ecc)也贡献 bare 名兜底
        for p in (local.get("plugins") or []):
            if isinstance(p, dict):
                names.add((p.get("name") or "").split("@")[0].lower())
                full = radar._owner_repo_from_url(p.get("url") or "")
                if full:
                    names.add(full.lower())
        return names
    except Exception as e:
        print(f"  [warn] detect_local_skills failed: {e}", file=sys.stderr)
        return set()


def enrich_trending_repos(snap):
    """For each name with stars_today, ensure it has full metadata (lang, topics,
    desc, desc_zh). Pulls from gh API if missing.
    Returns number of repos enriched."""
    from radar import gh_fetch_repo, translate_batch

    # build name → repo index from categories + hot_now
    by_name: dict = {}
    for r in snap.get("hot_now") or []:
        n = r.get("name")
        if n:
            by_name.setdefault(n, r)
    for c in snap.get("categories") or []:
        for r in c.get("repos") or []:
            n = r.get("name")
            if n:
                by_name.setdefault(n, r)

    today_map = snap.get("stars_today") or {}
    enriched = 0
    fresh_meta = []
    # 2026-08 — always try to enrich every trending repo that lacks full
    # metadata. The previous "needs_enrich = (not rec)" check missed cases
    # where rec exists but has empty lang/topics — and skipping that gave
    # us 10 gain cards with no stars/lang/topics.
    for name, st in today_map.items():
        if st <= 0:
            continue
        rec = by_name.get(name)
        # ponytail: re-enrich if rec missing OR any of lang/topics/desc_zh
        # is empty. gh API is cheap (5000/hr) so calling for all trending
        # repos is fine; gains come from newly-surfaced fields.
        if rec and rec.get("lang") and rec.get("lang") != "—" and rec.get("topics") \
           and rec.get("desc_zh"):
            continue
        meta = gh_fetch_repo(name)
        if not meta:
            continue
        meta["stars_today"] = st
        meta["desc"] = meta.get("desc") or meta.get("description") or ""
        meta["desc_zh"] = ""  # filled below
        meta["source"] = "trending_enriched"
        # override existing record (replace stub)
        if rec is not None and name in by_name:
            # in-place update preserves position in lists
            for k, v in meta.items():
                if v or k in ("stars", "lang", "topics", "desc", "desc_zh", "facts"):
                    rec[k] = v
            enriched += 1
        else:
            fresh_meta.append(meta)
            enriched += 1
        print(f"  enriched: {name}")

    if fresh_meta:
        # translate missing desc_zh
        pairs = [(f"{r['name']}::desc", r.get("desc", "")) for r in fresh_meta]
        zh = translate_batch(pairs)
        for r in fresh_meta:
            key = f"{r['name']}::desc"
            r["desc_zh"] = zh.get(key, "") or r.get("desc", "")
            r["facts"] = facts_for_repo(r)
        # merge into hot_now
        snap.setdefault("hot_now", [])
        existing_names = {r["name"] for r in snap["hot_now"]}
        for r in fresh_meta:
            if r["name"] not in existing_names:
                snap["hot_now"].append(r)
    return enriched


def main():
    latest = DATA / "latest.json"
    snap = json.loads(latest.read_text())
    print(f"[refresh] loaded {latest.name}: {snap.get('total_unique')} repos")

    # 1. Pull fresh sources
    print("[refresh] pulling fresh sources...")
    mcp = fetch_mcp_registry(max_items=30)
    print(f"  MCP: {len(mcp)} servers")
    hf_spaces = fetch_huggingface_trending(max_items=30)
    print(f"  HF Spaces: {len(hf_spaces)} spaces")
    hf_models = fetch_huggingface_models_trending(max_items=30)
    print(f"  HF Models: {len(hf_models)} models")

    # 2. Build new categories list (replace mcp / huggingface, ADD hf_models)
    new_cats = []
    cat_by_id = {c["id"]: c for c in snap.get("categories", [])}
    # MCP — replace with fresh MCP registry results
    cat_by_id["mcp"] = {"id": "mcp", "name": "MCP Servers & Clients",
                        "desc": cat_by_id.get("mcp", {}).get("desc",
                                                            "Model Context Protocol — 官方注册表 + GitHub 实现"),
                        "repos": mcp, "count": len(mcp)}
    # HF Spaces — replace
    cat_by_id["huggingface"] = {"id": "huggingface",
                                "name": "🤗 HuggingFace 热门 Spaces",
                                "desc": cat_by_id.get("huggingface", {}).get(
                                    "desc", "HuggingFace Trending Spaces — 社区精选 AI 应用 demo"),
                                "repos": hf_spaces, "count": len(hf_spaces)}
    # HF Models — new
    cat_by_id["hf_models"] = {"id": "hf_models",
                              "name": "🤗 HuggingFace 热门 Models",
                              "desc": "HuggingFace Trending Models — 7 天 likes 排行（Qwen / Llama / DeepSeek 等）",
                              "repos": hf_models, "count": len(hf_models)}
    new_cats = list(cat_by_id.values())

    # 3. Build unified repo set + dedupe
    all_repos = {}  # name -> repo
    cat_pairs = []
    for c in new_cats:
        for r in c["repos"]:
            all_repos.setdefault(r["name"], r)
            cat_pairs.append((r["name"], c["id"]))
    # also include the hot_now original (may include trending scraped entries)
    for r in snap.get("hot_now", []):
        all_repos.setdefault(r["name"], r)

    # 4. Compute stars_today from trending scraping (already in hot_now sub-set)
    stars_today = snap.get("stars_today", {}) or {}
    for r in all_repos.values():
        if r.get("stars_today") is not None and r["stars_today"] > 0:
            stars_today[r["name"]] = r["stars_today"]
    # Build trending set
    trending_names = {n for n, v in stars_today.items() if v}

    # 5. local_installed detection
    installed_names = load_local_installed_names()
    print(f"  local_installed: {len(installed_names)} names")

    # 5b. Enrich trending repos missing metadata (gh_fetch_repo + translate)
    n_enriched = enrich_trending_repos(snap)
    print(f"  enriched: {n_enriched} trending repos with full metadata")
    # merge newly enriched into all_repos
    for r in snap.get("hot_now") or []:
        all_repos.setdefault(r["name"], r)

    # 6. Augment every repo with derived fields
    for r in all_repos.values():
        # lang: already present from gh_api, leave alone
        # topics: already present, leave alone
        # best_category: assign to 5k+ pool
        if not r.get("best_category"):
            r["best_category"] = assign_best_category(r)
        # local_installed — 大小写不敏感匹配(installed_names 已统一小写)
        r["local_installed"] = (
            r["name"].lower() in installed_names
            or r["name"].split("/")[-1].lower() in installed_names
        )
        # trending
        r["trending"] = r["name"] in trending_names
        # fresh
        r["is_fresh"] = is_fresh(r)
        # facts
        r["facts"] = facts_for_repo(r)

    # 7. Translate missing desc_zh + synthesize summary_zh
    # ponytail: 2026-08 — for repos with empty desc (HF Spaces/Models API doesn't
    # return descriptions), synthesize a placeholder from the name so the
    # translate_batch has *something* to translate; the cache makes repeat
    # translations free on subsequent runs.
    pairs = []
    for r in all_repos.values():
        desc = r.get("desc", "")
        if not desc:
            # synthesize from repo name — `owner/Repo-Name-thing` → "Repo Name thing"
            base = r["name"].split("/")[-1].replace("-", " ").replace("_", " ")
            desc = f"{base} — AI / ML project"
            r["desc"] = desc
        # 2026-08 — also re-translate if desc_zh is empty, identical to desc
        # (translation failed last time), or pure-ASCII (likely English when it
        # should be Chinese). This catches stale English values left over from
        # earlier runs.
        existing_zh = (r.get("desc_zh") or "").strip()
        if (
            not existing_zh
            or existing_zh == desc.strip()
            or (existing_zh and all(ord(c) < 128 for c in existing_zh.replace(" ", "")))
        ):
            pairs.append((f"{r['name']}::desc", desc))
    zh = translate_batch(pairs)
    for r in all_repos.values():
        key = f"{r['name']}::desc"
        existing_zh = (r.get("desc_zh") or "").strip()
        same_as_desc = existing_zh == (r.get("desc", "") or "").strip()
        looks_english = existing_zh and all(
            ord(c) < 128 for c in existing_zh.replace(" ", "")
        )
        if not existing_zh or same_as_desc or looks_english:
            r["desc_zh"] = zh.get(key, "") or r.get("desc", "")
    missing_zh = sum(1 for r in all_repos.values() if not r.get("desc_zh"))
    print(f"  desc_zh: {len(all_repos) - missing_zh}/{len(all_repos)} translated")

    # ponytail: 2026-08 — also produce a one-sentence Chinese summary
    # (summary_zh). Take the first sentence of desc_zh (up to ~80 chars), trim
    # trailing punctuation, and ensure it ends with a Chinese period.
    for r in all_repos.values():
        zh_full = r.get("desc_zh", "") or r.get("desc", "")
        if not zh_full:
            r["summary_zh"] = ""
            continue
        # take first sentence: split on Chinese/English period/exclamation/question
        import re as _re
        first = _re.split(r"[。．.!！？?]", zh_full)[0].strip()
        if not first:
            first = zh_full[:60].strip()
        # cap at ~80 chars
        if len(first) > 80:
            first = first[:77] + "…"
        r["summary_zh"] = first
    summary_n = sum(1 for r in all_repos.values() if r.get("summary_zh"))
    print(f"  summary_zh: {summary_n}/{len(all_repos)}")

    # 8. hot_now: top 40 by stars + ALL trending repos (so /api/gain cards survive)
    by_stars_sorted = sorted(
        all_repos.values(), key=lambda r: r.get("stars", 0), reverse=True
    )
    hot_now = by_stars_sorted[:40]
    # ponytail: 2026-08 — preserve every trending repo even when its stars
    # don't make top-40 (some trending repos are <100k stars; they fall off the
    # pure-by-stars cutoff and /api/gain cards become empty stubs).
    seen_names = {r["name"] for r in hot_now}
    for r in by_stars_sorted:
        if r["name"] in trending_names and r["name"] not in seen_names:
            hot_now.append(r)
            seen_names.add(r["name"])
    # Cap at 50 (40 by-stars + ~10 trending boost)
    hot_now = hot_now[:50]

    # 9. Rebuild categories: each cat's repos come from all_repos (with augmentations)
    for c in new_cats:
        c["repos"] = [all_repos[r["name"]] for r in c["repos"]]

    # 10. Write snapshot
    new_snap = {
        "date": datetime.date.today().isoformat(),
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_unique": len(all_repos),
        "hot_now": hot_now,
        "categories": new_cats,
        "stars_today": stars_today,
        "trending_count": len(trending_names),
        "bootstrap": False,
    }
    latest.write_text(json.dumps(new_snap, ensure_ascii=False, indent=2))
    print(f"\n[refresh] wrote {latest.name}:")
    print(f"  total_unique: {new_snap['total_unique']}")
    print(f"  hot_now: {len(hot_now)}")
    print(f"  categories: {len(new_cats)}")
    print(f"  stars_today: {len(stars_today)} repos with +delta")
    print(f"  local_installed: {sum(1 for r in all_repos.values() if r.get('local_installed'))}")
    print(f"  desc_zh: {len(all_repos) - missing_zh}/{len(all_repos)}")
    for c in new_cats:
        n = len(c["repos"])
        marker = "🆕" if c["id"] in ("hf_models", "mcp", "huggingface") else "  "
        print(f"    {marker} [{c['id']:<14}] {c['name']:<40} {n:>3} repos")


if __name__ == "__main__":
    main()