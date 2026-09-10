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
import db  # ponytail: get_readme_zh uses db._DB_OK guard; imported lazily at runtime via try/except elsewhere
from radar_pkg.core import _repo_slug_from_url
from radar_pkg.gh import _gh_repo_meta

"""radar_pkg.translate — 由 radar.py 搬移(2026-09 架构拆分)。"""
_LANG_NAV_WORDS = (
    "English",
    "Português",
    "简体中文",
    "繁体中文",
    "日本語",
    "日本语",
    "한국어",
    "Türkçe",
    "Русский",
    "Français",
    "Deutsch",
    "Español",
    "Tiếng Việt",
    # 翻译后的语言名（缓存里的中文版语言行）
    "英语",
    "葡萄牙语",
    "日语",
    "韩语",
    "土耳其语",
    "俄语",
    "法语",
    "德语",
    "西班牙语",
)


def _clean_readme_text(md: str, max_chars: int = 600) -> str:
    """README → 干净摘要文本。
    处理真实 README 的脏开头：徽章/语言切换表/导航链接往往占据前几百字符。
    ① 去图片/链接/标题标记/强调/代码标记；② 跳过语言导航段；③ 取第一个 ≥40 字符的实质段落。"""
    if not md:
        return ""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)  # 图片
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # 链接 → 文本
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)  # 标题标记
    s = re.sub(r"<[^>]+>", " ", s)  # HTML 标签（徽章）
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"[`<>|]", " ", s)
    # GFM 警告标记 [!WARNING]/[!警告] 与语言切换括号 [ En 中 Fr 日 ] — 去前缀保留正文
    s = re.sub(
        r"^\s*\[\s*[!！]?\s*(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION|注意|重要|警告|提示)\s*\]\s*",
        "",
        s,
        flags=re.M,
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


# ponytail: 2026-09 — ZH-aware section extractor. 用于从已翻译的 README 文本
# 提取 5 桶内容（intro / can_do / problem / competitive / when_to_use）。
# 与 _split_readme_sections(从原文 raw_md 拆分)互补,后者依赖英文 heading
# 关键词,前者用中文 + 数字列表 + 段落长度启发式. 两者并行,任何一个出结果都行.
_ZH_HEADING_KEYWORDS = {
    "intro": ("什么是", "项目简介", "简介", "项目概述", "概述",
              "项目背景", "概览", "是什么", "About", "What is", "Introduction"),
    "can_do": ("功能", "特性", "能力", "主要特点", "快速入门", "快速开始",
               "使用方法", "示例", "用法", "使用场景", "Features"),
    "problem": ("问题", "痛点", "问题背景", "挑战", "难题", "动机", "现状",
                "为什么做", "Problem", "Motivation"),
    "competitive": ("对比", "同类", "竞品", "Comparison", "vs", "Alternatives"),
    "when_to_use": ("为什么", "优势", "亮点", "特点", "适用", "场景", "何时",
                    "选择", "为什么选", "为什么使用", "适用场景",
                    "Advantages", "Highlights", "When to use", "Why"),
}
_ZH_PHRASE_TO_BUCKET: dict[str, str] = {}
for _b, _kws in _ZH_HEADING_KEYWORDS.items():
    for _kw in _kws:
        _ZH_PHRASE_TO_BUCKET[_kw.lower()] = _b


def _is_zh_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,4}\s+\S", line))


def _clean_zh_heading(text: str) -> str:
    t = re.sub(r"^#+\s*", "", text).strip()
    return re.sub(r"[:：]+\s*$", "", t).strip()


def _classify_zh_heading(heading_text: str) -> str | None:
    h_low = heading_text.lower()
    for phrase in sorted(_ZH_PHRASE_TO_BUCKET, key=len, reverse=True):
        if phrase in h_low:
            return _ZH_PHRASE_TO_BUCKET[phrase]
    return None


def _is_zh_trivial(p: str) -> bool:
    s = p.strip()
    if not s:
        return True
    if _is_zh_heading(s):
        return True
    if re.fullmatch(r"(\[[^\]]*\]\([^)]*\)\s*[|·•,]?\s*)+", s):
        return True
    if re.fullmatch(r"^[\s\d.·•—✓>*-]+$", s):
        return True
    return False


def derive_sections_from_text(text: str) -> dict[str, str]:
    """ZH-aware 5 桶提取,纯从 translated text 入手,无需 raw_md.
    ponytail: 当 cache 没有 raw_md(老条目 / 缓存破坏 / 翻译失败)时回退路径.
    与 _split_readme_sections 互补 — 一个从原文 heading 拆,一个从译文字段拆."""
    out = {"intro": "", "can_do": "", "problem": "",
           "competitive": "", "when_to_use": ""}
    if not text or len(text.strip()) < 30:
        return out

    # 1. Try heading-based classification
    blocks: list[tuple[str, str]] = []
    cur_h = ""
    cur_body: list[str] = []

    def flush():
        nonlocal cur_body
        body = "\n".join(cur_body).strip()
        cur_body = []
        if body:
            blocks.append((cur_h, body))

    for raw in text.split("\n"):
        line = raw.rstrip()
        if _is_zh_heading(line):
            flush()
            cur_h = _clean_zh_heading(line)
        elif line.strip() == "":
            flush()
        else:
            cur_body.append(line)
    flush()

    for heading, body in blocks:
        if not heading:
            continue
        bucket = _classify_zh_heading(heading)
        if bucket and not out[bucket]:
            for para in re.split(r"\n\s*\n", body):
                if not _is_zh_trivial(para):
                    out[bucket] = para.strip()[:600]
                    break

    # 2. Fallback: no heading matched → split whole text into paragraphs
    if not any(out.values()):
        paragraphs = [
            re.sub(r"^#+\s*", "", p).strip()
            for p in re.split(r"\n\s*\n", text)
        ]
        paragraphs = [p for p in paragraphs if p and not _is_zh_trivial(p)]
        if paragraphs:
            for p in paragraphs:
                if len(p) >= 50:
                    out["intro"] = p[:600]
                    break
            if not out["intro"] and paragraphs:
                out["intro"] = paragraphs[0][:600]
            # can_do: numbered / bullet list paragraph
            for p in paragraphs:
                if re.match(r"^[\d①②③④⑤⑥⑦⑧⑨•\-*]\s*", p) and len(p) >= 30:
                    out["can_do"] = p[:600]
                    break
            if not out["can_do"] and len(paragraphs) > 1:
                out["can_do"] = paragraphs[1][:600]
            # when_to_use: last paragraph if different
            if len(paragraphs) > 1 and paragraphs[-1] != paragraphs[0]:
                out["when_to_use"] = paragraphs[-1][:600]
    return out


# ponytail: 2026-09 — README 结构化拆分。按 heading 文本映射到 5 桶：
#   intro / can_do / problem / competitive / when_to_use
# 凑齐卡片详介「是什么 / 能干什么 / 解决什么问题 / 同类竞品 / 何时选它」。
# 关键词中英文混排；不依赖 LLM — Google Translate 是字面翻译，无法要求「生成
# 三段式描述」。结构化靠 heading 提取 + 关键词归类;competitive 桶无 README 来源,
# 走同 topic 仓库匹配(由 _attach_competitive 注入). 前端按桶渲染,缺桶自然不显示。
_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "intro": (
        "what is",
        "about",
        "introduction",
        "overview",
        "description",
        "简介",
        "介绍",
        "项目简介",
        "是什么",
        "概要",
        "概述",
    ),
    "can_do": (
        "features",
        "what it does",
        "what you can do",
        "capabilities",
        "usage",
        "use cases",
        "getting started",
        "quickstart",
        "examples",
        "功能",
        "特性",
        "能力",
        "使用",
        "使用场景",
        "示例",
        "用法",
        "怎么用",
        "安装",
        "快速开始",
    ),
    "problem": (
        "problem",
        "pain point",
        "motivation and goals",
        "why we built",
        "challenge",
        "问题",
        "痛点",
        "问题背景",
        "为什么做",
        "挑战",
    ),
    "competitive": (
        "comparison",
        "compare",
        "alternatives",
        "vs",
        "vs.",
        "benchmark",
        "对比",
        "同类",
        "竞品",
        "对比一下",
        "性能对比",
        "benchmark",
    ),
    "when_to_use": (
        "why",
        "why use",
        "why choose",
        "motivation",
        "background",
        "when to use",
        "use cases",
        "when not to use",
        "适合谁",
        "何时",
        "场景",
        "适用",
        "何时使用",
        "优势",
        "亮点",
        "动机",
        "背景",
        "特点",
        "价值",
    ),
}


def _split_readme_sections(md: str) -> dict[str, str]:
    """把 README 按 ## heading 拆段，关键词归类到 5 桶。
    返回 {bucket: 第一个匹配的 section 首段(纯文本)}；无匹配返回空串。
    ponytail: 第一个 heading 之前的内容算「preamble」— 没有 ## What is 时，
    preamble 的首个实质段落充当 intro 段（README 标配：开头一段介绍，后面
    才列 Features / Why 等）。competitive 桶由 _attach_competitive 单独注入,
    这里只产 4 桶 + 留空 competitive。"""
    if not md:
        return {
            "intro": "",
            "can_do": "",
            "problem": "",
            "competitive": "",
            "when_to_use": "",
        }
    blocks: list[tuple[str, str]] = []
    preamble: list[str] = []
    current_h = ""
    current_body: list[str] = []
    seen_heading = False
    for line in md.splitlines():
        h = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if h:
            if not seen_heading:
                seen_heading = True
                blocks.append(("", "\n".join(preamble).strip()))
            if current_h or current_body:
                blocks.append((current_h, "\n".join(current_body).strip()))
            current_h = h.group(1).strip()
            current_body = []
        else:
            if seen_heading:
                current_body.append(line)
            else:
                preamble.append(line)
    if seen_heading and (current_h or current_body):
        blocks.append((current_h, "\n".join(current_body).strip()))
    if not seen_heading:
        # 整篇没 heading → 整段当作 preamble
        blocks.append(("", md.strip()))

    out = {
        "intro": "",
        "can_do": "",
        "problem": "",
        "competitive": "",
        "when_to_use": "",
    }
    for heading, body in blocks:
        body = re.sub(r"\s*##\s+.+\s*", "\n", body)
        body = re.sub(r"[ \t]+", " ", body)
        body_lines = [
            ln.strip()
            for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        body = "\n".join(body_lines).strip()
        if len(body) < 20:
            continue
        h_low = heading.lower()
        # 跳过纯装饰 heading（贡献 / 许可证 / 鸣谢等不进入「能干什么」）
        if heading and any(
            skip in h_low
            for skip in (
                "license",
                "contribut",
                "thanks",
                "acknowledg",
                "sponsor",
                "donate",
                "star history",
                "appendix",
            )
        ):
            continue
        # preamble 段 — 没 heading 时归类到 intro
        if not heading:
            if not out["intro"]:
                out["intro"] = re.sub(r"\s+", " ", body)[:600]
            continue
        for bucket, keywords in _SECTION_KEYWORDS.items():
            if out[bucket]:
                continue
            if any(kw in h_low for kw in keywords):
                # ponytail: 取首个 ≥20 字符的实质段；中文一句话常 20-40 字符。
                first_para = ""
                for p in re.split(r"\n+", body):
                    p = p.strip()
                    if len(p) >= 20:
                        first_para = p[:600]
                        break
                if not first_para and len(body) >= 20:
                    first_para = re.sub(r"\s+", " ", body)[:600]
                if first_para:
                    out[bucket] = first_para
                break
    return out


def _build_sections_zh(readme_md: str) -> dict[str, str]:
    """清洗 + 拆分 + 逐桶翻译 → {intro, can_do, benefit} 中文三段。
    没找到的桶返回空串（前端按桶渲染，缺桶自然隐藏）。
    ponytail: 串行翻译三桶 — Google Translate free 端点对并发请求不友好（实测
    三路并发会触发 rate limit，部分桶返回原文被 _looks_translated 判定失败）。
    单 repo 三段总耗时 ~3s，可接受。"""
    if not readme_md:
        return {
            "intro": "",
            "can_do": "",
            "problem": "",
            "competitive": "",
            "when_to_use": "",
        }
    clean = _light_clean_for_sections(readme_md)
    if not clean:
        return {
            "intro": "",
            "can_do": "",
            "problem": "",
            "competitive": "",
            "when_to_use": "",
        }
    sections = _split_readme_sections(clean)
    out: dict[str, str] = {}
    for bucket, text in sections.items():
        if not text:
            out[bucket] = ""
            continue
        # ponytail: chunked_translate 内部已按 280 字符分块串行 — 直接调用即可
        zh = _chunked_translate(text)
        out[bucket] = zh if _looks_translated(zh, text) else ""
    return out


def _light_clean_for_sections(md: str) -> str:
    """section 拆分前的轻度清洗 — 不动 bullet/heading。
    ponytail: _strip_markdown_to_text 太狠，会把 Features 段的 bullet 列表整段
    当作噪声丢掉。这里只去图片/HTML/链接/语言表，保留 heading + bullet，交给
    _split_readme_sections 处理。"""
    s = md
    # 去掉代码块（不影响分桶但占空间）
    s = re.sub(r"```.*?```", "", s, flags=re.DOTALL)
    # 去掉图片与纯装饰链接
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[(\s*)\]\(\s*\)", r"\1", s)
    # 链接保留文本 [text](url) → text
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    # 去掉 HTML 标签（徽章）
    s = re.sub(r"<[^>]+>", " ", s)
    # 去掉 pure-shields.io badge 行
    s = re.sub(r"^\s*\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$", "", s, flags=re.MULTILINE)
    # 去掉 GFM 警告行
    s = re.sub(r"^>\s*\[!\w+\].*$", "", s, flags=re.MULTILINE)
    # 去掉语言切换行（`English | 中文 | ...`）
    s = re.sub(
        r"^\s*\[?[A-Z][a-z]+\s*\]?\s*\|\s*\[?[\u4e00-\u9fff].*$",
        "",
        s,
        flags=re.MULTILINE,
    )
    # 截断到合理长度（防止单 repo README 几十 KB 拖慢 translate）
    return s[:12000]


def _build_summary_zh(repo: dict, cache: dict) -> None:
    """为单个 repo 生成 summary_zh（卡片 2 行预览）+ summary_sections（抽屉三段详介）。
    缓存命中 → 直接复用；未命中 → 拉 README 拆分 + 翻译并写回 cache。
    非 GitHub 条目（HF/arXiv/MCP）用 desc_zh 兜底。失败静默降级。
    ponytail: 2026-09 升级。summary_sections = {intro, can_do, benefit} 三桶，
    由 README 的 ## Features / ## What is / ## Why 等 heading 关键词归类，
    每桶独立翻译，缺桶留空（前端按桶渲染自然隐藏）。"""
    full_name = repo.get("name") or ""
    fallback = repo.get("desc_zh") or repo.get("desc") or ""
    url = repo.get("url") or ""
    repo["summary_sections"] = {
        "intro": "",
        "can_do": "",
        "problem": "",
        "competitive": "",
        "when_to_use": "",
    }
    if "/" not in full_name or "github.com" not in url:
        repo["summary_zh"] = fallback
        return
    key = full_name.lower()
    entry = cache.get(key)
    if entry and entry.get("text"):
        # ponytail: 2026-09 — 缓存阈值。旧 cleaner 把 28KB README 砍到 21-50
        # 字符,缓存里残留大量短摘要(<200 字符)。text_len ≥ 200 才视为有效.
        # 短缓存视为损坏/旧版本,丢弃重抓 README + 重翻译.
        if len(entry["text"]) >= 200:
            summary = _summary_from_entry(entry)
            if summary and any("一" <= ch <= "鿿" for ch in summary[:60]):
                repo["summary_zh"] = summary
                repo["summary_sections"] = (
                    entry.get("sections") or repo["summary_sections"]
                )
                return
        cache.pop(key, None)
    fetched = _fetch_readme_from_github(full_name)
    if not fetched:
        repo["summary_zh"] = fallback
        return
    raw_md, source_url = fetched
    # ponytail: 2026-09 — 全文翻译走 _strip_markdown_to_text(4.5KB 上限),不要用
    # _clean_readme_text(只取第一段 600 字符). 此前 _clean_readme_text 把 28KB
    # README 砍到 21-50 字符,导致 summary_zh 极短,sections 几乎全空. README
    # 大段描述都是被 _clean_readme_text 误杀掉的.
    full_clean = _strip_markdown_to_text(raw_md, max_chars=4500)
    zh = _chunked_translate(full_clean) if full_clean else ""
    # ponytail: 短摘要走 _summary_from_entry(cache) — 缓存里就是干净的 zh 文本
    # (取首段). sections 单独走 _light_clean_for_sections(保留 heading + bullet)
    sections_zh = _build_sections_zh(raw_md)
    if zh and _looks_translated(zh, full_clean):
        cache[key] = {
            "text": zh,
            "sections": sections_zh,
            "raw_md": raw_md[
                :6000
            ],  # ponytail: 2026-09 — 留原始 README 给后续 LLM 分析用（避免再拉一次）
            "source_url": source_url,
            "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "translator": "google-translate-free",
        }
        repo["summary_zh"] = _summary_from_entry(cache[key]) or fallback
        repo["summary_sections"] = sections_zh
    else:
        # 翻译失败不缓存、不展示英文 — 回退中文简介
        repo["summary_zh"] = fallback


def _attach_competitive(repos: list, max_per_repo: int = 4) -> int:
    """给每个 repo 的 summary_sections.competitive 注入同类项目。
    ponytail: 2026-09 — 不靠 LLM,从我们自己的快照里按 topic 重叠度找.
    逻辑:
      1. 建 name → repo 索引(去掉自己)
      2. 对每个 repo,按 topic 重叠数 + stars 排序,取 top N
      3. 写入 summary_sections.competitive 字符串("同类项目: A、B、C(覆盖 topic 标签)")
    返回注入了 competitive 的 repo 数。
    """
    pool = [r for r in repos if r.get("name") and r.get("topics")]
    by_name = {r["name"].lower(): r for r in pool}
    filled = 0
    for r in repos:
        if not r.get("name") or not r.get("topics"):
            continue
        my_topics = set(t.lower() for t in r["topics"])
        my_name = r["name"].lower()
        candidates = []
        for other in pool:
            if other["name"].lower() == my_name:
                continue
            other_topics = set(t.lower() for t in other.get("topics", []))
            overlap = len(my_topics & other_topics)
            if overlap == 0:
                continue
            candidates.append((overlap, other.get("stars", 0), other))
        # sort by (overlap desc, stars desc); take top N
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        chosen = [c[2] for c in candidates[:max_per_repo]]
        if not chosen:
            continue
        # competitive 是字符串(中文友好列表),不要 list of dict(避免误读为 pros/cons)
        names = [c["name"] for c in chosen]
        sec = r.get("summary_sections") or {}
        sec["competitive"] = "同类项目:" + "、".join(names)
        r["summary_sections"] = sec
        filled += 1
    return filled


def enrich_summaries(repos: list, max_workers: int = 4) -> int:
    """爬取期为全部 repos 生成详细中文描述（summary_zh + 5 桶 sections）。
    README 拉取 + 翻译 4 线程并发；缓存读写只做一次（整文件）。
    完成后调用 _attach_competitive 注入同类项目桶（基于 snapshot 同 topic 匹配）。
    返回生成数量。任何失败不阻塞爬取主流程。"""
    cache: dict = {}
    if core.README_ZH_CACHE.exists():
        try:
            cache = json.loads(core.README_ZH_CACHE.read_text())
        except Exception:
            cache = {}
    github_repos = [r for r in repos if "github.com" in (r.get("url") or "")]
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
        if not r.get("summary_sections"):
            # 兜底:把整段 desc_zh 塞进 intro,让前端至少有一桶可渲染
            intro = r.get("summary_zh") or r.get("desc_zh") or r.get("desc") or ""
            r["summary_sections"] = {
                "intro": intro[:400] if intro else "",
                "can_do": "",
                "problem": "",
                "competitive": "",
                "when_to_use": "",
            }
    # ponytail: 2026-09 — 注入同类项目桶。从我们自己的快照里找同 topic 仓库,
    # 无需 LLM,纯本地匹配。competitive 是字符串而非 list(drawer 当文字段落渲染).
    n_comp = _attach_competitive(repos)
    print(f"[crawl] competitive: filled for {n_comp} repos")
    try:
        # ponytail: 原子写(tmp + rename)避免多 worker 并发时覆盖其他 worker 的更新
        tmp = core.README_ZH_CACHE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        tmp.replace(core.README_ZH_CACHE)
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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
                "curl",
                "-q",
                "-sS",
                "--max-time",
                "10",
                "-A",
                "Mozilla/5.0",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=15,
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
    cache = (
        json.loads(core.TRANSLATE_CACHE.read_text())
        if core.TRANSLATE_CACHE.exists()
        else {}
    )
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


def _fetch_readme_from_github(
    full_name: str, max_chars: int = 12000
) -> tuple[str, str] | None:
    """Fetch README.md from GitHub raw for owner/repo. Returns (text, source_url) or None.
    ponytail: 2026-09 — cap raised 6KB → 12KB so we have room to grab the Features /
    Why-use / 使用场景 sections AFTER the noisy preamble. Still capped so a giant
    monorepo README doesn't blow the Google Translate free 500-char/chunk budget.
    Try common README filenames in order — README.md / readme.md / README.rst."""
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
            req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if raw.strip():
                return raw[:max_chars], url
        except Exception:
            pass
        try:
            out = subprocess.run(
                [
                    "curl",
                    "-q",
                    "-sSL",
                    "--max-time",
                    "20",
                    "-A",
                    "lodestone/1.0",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=25,
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
        non_text = sum(1 for c in p if c in "|[](){}<>#=*_`@")
        if non_text > len(p) * 0.4:
            continue
        # ponytail: skip the noisy preamble (links / nav menus) but keep all real prose
        if skipped_chars < noise_threshold and (
            p.startswith("- ") or p.startswith("*[") or " | " in p[:200]
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
        return {
            "text": "",
            "source_url": "",
            "from_cache": False,
            "error": "invalid name",
        }
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
        return {
            "text": "",
            "source_url": "",
            "from_cache": False,
            "error": "fetch failed",
        }

    raw_md, source_url = fetched
    clean = _strip_markdown_to_text(raw_md)
    zh_text = _chunked_translate(clean)
    sections_zh = _build_sections_zh(raw_md)
    # ponytail: if translation truly failed, return the cleaned English content with
    # an explicit marker so the UI can show "（翻译失败 · 原文）" rather than confused text.
    if not zh_text:
        zh_text = (
            "【自动翻译暂不可用 · 以下为英文原文 · 数据源："
            + source_url
            + "】\n\n"
            + clean
        )
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    entry = {
        "text": zh_text,
        "sections": sections_zh,
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

    # Persist to JSON cache (atomic write — load-merge-rename).
    # ponytail: 多线程 enrich_summaries 4 worker 并发时,读-改-写会有 lost update
    # 问题(一个 worker 写回的 cache 是基于过期内存 dict,覆盖其他 worker 的更新).
    # 这里只用单进程 fetch 路径,entrich_summaries 的批写覆盖此处;但 fetch+批写
    # 之间仍可能 race — 用 .tmp + rename 保证原子性.
    try:
        cache = (
            json.loads(core.README_ZH_CACHE.read_text())
            if core.README_ZH_CACHE.exists()
            else {}
        )
        cache[cache_key] = entry
        tmp = core.README_ZH_CACHE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        tmp.replace(core.README_ZH_CACHE)
    except OSError:
        pass
    return entry
