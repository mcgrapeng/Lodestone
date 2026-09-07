# -*- coding: utf-8 -*-
"""radar_pkg.translate — 翻译/README 摘要(持久缓存)。"""
import datetime
import json
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from radar_pkg import core
from radar_pkg.core import _repo_slug_from_url
from radar_pkg.gh import _gh_repo_meta

"""radar_pkg.translate — 由 radar.py 搬移(2026-09 架构拆分)。"""
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
    if core.README_ZH_CACHE.exists():
        try:
            cache = json.loads(core.README_ZH_CACHE.read_text())
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
        core.README_ZH_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1)
        )
    except Exception as e:
        print(f"  [warn] summary cache write failed: {e}", file=sys.stderr)
    return sum(1 for r in repos if r.get("summary_zh"))

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
    cache = json.loads(core.TRANSLATE_CACHE.read_text()) if core.TRANSLATE_CACHE.exists() else {}
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
        core.TRANSLATE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return out

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
    if not force and core.README_ZH_CACHE.exists():
        try:
            cache = json.loads(core.README_ZH_CACHE.read_text())
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
            json.loads(core.README_ZH_CACHE.read_text())
            if core.README_ZH_CACHE.exists()
            else {}
        )
        cache[cache_key] = entry
        core.README_ZH_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2)
        )
    except OSError:
        pass
    return entry
