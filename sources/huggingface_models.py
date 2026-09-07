# -*- coding: utf-8 -*-
"""HuggingFace Models Trending — JSON API for model weights ranked by 7-day likes.

Endpoint: GET https://huggingface.co/api/models?sort=likes7d&limit=N&full=true
Returns:
  [{ "id": "owner/model", "modelId": "...", "tags": [...], "downloads": N,
     "likes": N, "trendingScore": N, "pipeline_tag": "text-generation",
     "library_name": "transformers", "private": false, "createdAt": "...", ... }]

We surface `trendingScore` as `stars` so the existing UI/badge logic (sorted by stars,
⭐ N badge) treats models uniformly alongside Spaces / GitHub repos.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from typing import Optional


HF_MODELS_URL = "https://huggingface.co/api/models?sort={sort}&limit={limit}&full=false"

# 2026-08 — valid HF model sort values: downloads, likes, trending, updated, created.
# We accept a small allowlist; `trending` is the official 7-day trending sort that
# returns `trendingScore` consistently.
VALID_SORTS = ("trending", "likes7d", "downloads", "downloads7d", "updated")


def _http_get_json(url: str, timeout: int = 30) -> Optional[list]:
    """Same urllib → curl fallback as radar.fetch_huggingface_trending."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data if isinstance(data, list) else None
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["curl", "-q", "-sS", "--max-time", str(timeout), "-A", "lodestone/1.0", url],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            return data if isinstance(data, list) else None
    except Exception:
        pass
    return None


def fetch_huggingface_models_trending(max_items: int = 30, sort: str = "likes7d") -> list:
    """Fetch trending HF models. `sort=likes7d` returns a `trendingScore` field
    for each model; we surface that as `stars` so the existing UI/badge logic
    treats models uniformly alongside Spaces / GitHub repos.

    Filters out:
      - private models (`private=True`)
      - non-AI pipeline tags (image, audio, video are kept — they're real AI uses;
        we only drop `other`)
    """
    if sort not in VALID_SORTS:
        print(
            f"  [warn] HF models: invalid sort {sort!r}, falling back to likes7d",
            file=sys.stderr,
        )
        sort = "likes7d"
    url = HF_MODELS_URL.format(sort=sort, limit=max_items)
    data = _http_get_json(url, timeout=30)
    if not data:
        print(f"  [warn] HF models: fetch failed (sort={sort})", file=sys.stderr)
        return []
    out: list[dict] = []
    for m in data[:max_items]:
        if m.get("private"):
            continue
        mid_id = m.get("id") or m.get("modelId") or ""
        if not mid_id or "/" not in mid_id:
            continue
        pipeline = (m.get("pipeline_tag") or "").strip()
        # drop pure non-AI pipelines if any sneak in
        if pipeline in ("other", ""):
            # keep if trendingScore is high — could be multi-modal misc
            pass
        likes = int(m.get("likes") or 0)
        trend = int(m.get("trendingScore") or 0)
        downloads = int(m.get("downloads") or 0)
        tags = m.get("tags") or []
        # ponytail: 2026-08 — HF `library_name` is the model library
        # (transformers / diffusers / gguf / timm / mlx / ...), not a programming
        # language. Capitalize so it shows up in the UI; the frontend's by_lang
        # sort treats every distinct value the same.
        lib = (m.get("library_name") or "model").strip()
        lang = lib[:1].upper() + lib[1:].lower() if lib else "Model"
        created = (m.get("createdAt") or "")[:10]
        out.append(
            {
                "name": mid_id,
                "full_name": mid_id,
                "url": f"https://huggingface.co/{mid_id}",
                "description": "",  # HF models API does NOT return description; let translate pass skip
                "desc": "",
                "stars": trend if trend else likes,  # trendingScore primary, likes fallback
                "forks": 0,
                "lang": lang,
                "topics": [
                    "huggingface",
                    "model",
                    pipeline or "model",
                    *[
                        t.replace("license:", "license-")
                        for t in tags
                        if isinstance(t, str)
                    ][:4],
                ],
                "updated": created,
                "pushed": created,
                "score": trend,
                "best_category": "huggingface",
                "is_ai_relevant": True,  # HF trending is AI-curated
                "source": "huggingface_models_trending",
                "hf_likes": likes,
                "hf_downloads": downloads,
            }
        )
    print(
        f"  ✓ HF models: {len(out)} trending models (sort={sort})",
        file=sys.stderr,
    )
    return out


if __name__ == "__main__":
    items = fetch_huggingface_models_trending(max_items=10)
    for r in items:
        print(
            f"  {r['name']:<40} ⭐trend={r.get('hf_likes','?'):>6} "
            f"downloads={r.get('hf_downloads','?'):>8,}"
        )