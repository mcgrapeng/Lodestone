# -*- coding: utf-8 -*-
"""GitHub GraphQL batch search — N queries per HTTP request via field aliases.

Why: REST search (`gh api search/repositories`) is capped at 30 req/min, and the
crawl needs ~204 queries — 204 × (2s pace + latency) ≈ 12 minutes. GraphQL
rate-limits by POINTS (5000/hour, search ≈ 1-2 points each) and allows aliasing
many `search(...)` fields into ONE request document:

    query {
      q0: search(query: "topic:ai-agent stars:>500", type: REPOSITORY, first: 30) {
        repos: nodes { ... on Repository { nameWithOwner stargazerCount ... } }
      }
      q1: search(query: "...", type: REPOSITORY, first: 30) { ... }
      ...
    }

204 queries → ~14 requests → 搜索阶段 12 分钟 ≈ 1 分钟。

Known trade-off: GraphQL search has NO sort parameter (best-match relevance
only, vs REST's sort=stars). Callers that need star ordering sort locally —
radar.py already sorts category repos by stars after merging. Best-match for
`stars:>N topic:X` queries is strongly star-driven anyway, and the PG pool
accumulates across crawls so a repo missed one day usually lands the next.

Falls soft: any query missing from the returned mapping (request failed /
partial alias errors) is the caller's signal to fall back to REST gh_search
for just that query.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

# ponytail: .env 的 GH_TOKEN/GITHUB_TOKEN 是 gh auth login 之外的非交互认证方式
# （gh CLI 原生读取环境变量）。shell 里已 export 的值优先。
try:
    from env_loader import load_env

    load_env()
except Exception:
    pass

# 每个 search 别名的返回字段 — 与 radar.gh_search 的 REST 字段一一对应
_REPO_FIELDS = """
    nameWithOwner
    description
    url
    stargazerCount
    forkCount
    primaryLanguage { name }
    repositoryTopics(first: 10) { nodes { topic { name } } }
    updatedAt
    pushedAt
"""


def _escape(q: str) -> str:
    """Escape a query for embedding in a GraphQL string literal."""
    return q.replace("\\", "\\\\").replace('"', '\\"')


def _build_document(
    queries: list[str], per_page: int, cursors: list[str | None] | None = None
) -> str:
    """Build one GraphQL document with N aliased search fields.
    cursors[i] 非空时给 q{i} 加 after: 游标(翻第二页)。"""
    curs: list[str | None] = list(cursors) if cursors is not None else [None] * len(queries)
    parts = []
    for i, q in enumerate(queries):
        cur = curs[i] if i < len(curs) else None
        after = f', after: "{_escape(cur)}"' if cur else ""
        parts.append(
            f'q{i}: search(query: "{_escape(q)}", type: REPOSITORY, first: {per_page}{after}) '
            f"{{ repos: nodes {{ ... on Repository {{ {_REPO_FIELDS} }} }} "
            f"pageInfo {{ endCursor hasNextPage }} }}"
        )
    return "query {\n  " + "\n  ".join(parts) + "\n}"


def _run_gh_graphql(document: str, timeout: int = 90) -> dict:
    """Execute via gh CLI. Returns parsed `data`. Raises on any hard failure.
    GH_TOKEN/GITHUB_TOKEN（.env 或 shell）由 gh CLI 原生识别 — 未认证时
    GraphQL 会立刻被 IP 级限流拒绝。"""
    r = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={document}"],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=dict(os.environ),
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh api graphql exit {r.returncode}: {r.stderr.strip()[:160]}")
    payload = json.loads(r.stdout)
    if payload.get("errors") and not payload.get("data"):
        # 全文档级错误（认证/语法）— 部分别名错误时 data 仍存在，不在这里抛
        raise RuntimeError(f"graphql errors: {str(payload['errors'])[:200]}")
    return payload.get("data") or {}


def _node_to_repo(node: dict) -> dict:
    """GraphQL node → radar 的 repo dict（与 gh_search REST 输出同 shape）。"""
    lang_obj = node.get("primaryLanguage") or {}
    topics = [
        t.get("topic", {}).get("name")
        for t in ((node.get("repositoryTopics") or {}).get("nodes") or [])
    ]
    return {
        "name": node["nameWithOwner"],
        "desc": (node.get("description") or "").strip(),
        "url": node.get("url") or f"https://github.com/{node['nameWithOwner']}",
        "stars": node.get("stargazerCount", 0),
        "forks": node.get("forkCount", 0),
        "lang": (lang_obj.get("name") or "—"),
        "topics": [t for t in topics if t],
        "updated": (node.get("updatedAt") or "")[:10],
        "pushed": (node.get("pushedAt") or "")[:10],
        "score": 0.0,
        "source": "gh_graphql",
    }


def gh_search_batch(
    queries: list[str],
    per_page: int = 30,
    batch_size: int = 6,
    max_workers: int = 3,
    retries: int = 1,
    max_rounds: int = 3,
    pace_s: float = 1.0,
    follow_page2: bool = False,
) -> dict[str, list[dict]]:
    """Run all queries via batched GraphQL. Returns {query_string: [repo dicts]}.

    2026-09 实测约束（GitHub GraphQL）：
      - 单请求节点预算有限：15×first:30 / 4×first:100 都会报
        "Resource limits for this query exceeded"
      - 重文档偶发 HTTP 502/504/EOF（瞬时服务端错误，重试即过）
      安全规格：分类批 6×first:30，5k 池批 8×first:50（都实测通过）

    自适应失败处理（三轮）：
      第 1 轮按 batch_size 分批并行执行；失败批退避重试 retries 次后，
      对半拆分进入下一轮（资源上限错误对半后通常可过）；单 query 的批
      失败即最终失败。最终失败的 query 从结果 mapping 缺失 — 调用方回退 REST。

    follow_page2=True 时对"结果数 == per_page 且 hasNextPage"的 query 用
    after 游标追一页（P1 修复：GraphQL 无 sort=stars，best-match 第 51-100 名
    原本拿不到；单 alias per_page 提到 100 会撞资源上限，游标是唯一扩容手段）。
    """
    unique = list(dict.fromkeys(queries))  # 保序去重
    pending = [unique[i : i + batch_size] for i in range(0, len(unique), batch_size)]

    def _run_batch(batch: list[str], cursors: list[str | None] | None = None):
        last_err = None
        for attempt in range(1 + max(0, retries)):
            if attempt:
                time.sleep(2)  # 502/504 瞬时错误退避
            try:
                data = _run_gh_graphql(_build_document(batch, per_page, cursors))
            except Exception as e:
                last_err = e
                continue
            result: dict[str, list[dict]] = {}
            cursors_out: dict[str, str | None] = {}
            for i, q in enumerate(batch):
                blk = data.get(f"q{i}") or {}
                nodes = blk.get("repos") or []
                if nodes:
                    result[q] = [_node_to_repo(n) for n in nodes if n]
                pi = blk.get("pageInfo") or {}
                cursors_out[q] = pi.get("endCursor") if pi.get("hasNextPage") else None
            return result, cursors_out, None
        return {}, {}, last_err

    from concurrent.futures import ThreadPoolExecutor, as_completed

    out: dict[str, list[dict]] = {}
    cursors_all: dict[str, str | None] = {}  # query → 第二页游标（hasNextPage 时非空）
    rnd = 0
    while pending and rnd < max(1, max_rounds):
        rnd += 1
        next_pending: list[list[str]] = []
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
            fut_to_batch = {
                pool.submit(_run_batch, batch): batch for batch in pending
            }
            if pace_s:
                time.sleep(pace_s)  # 提交后小间隔，避免与上一次调用贴背
            for fut in as_completed(fut_to_batch):
                batch = fut_to_batch[fut]
                result, curs, err = fut.result()
                if err is None:
                    out.update(result)
                    cursors_all.update(curs)
                    n_repos = sum(len(v) for v in result.values())
                    print(
                        f"  · graphql r{rnd} batch: {len(result)}/{len(batch)} "
                        f"aliases, {n_repos} repos",
                        file=sys.stderr,
                    )
                elif len(batch) > 1:
                    # 资源上限/502 → 对半拆分进下一轮（单 query 批没有拆分余地）
                    mid = len(batch) // 2
                    next_pending.append(batch[:mid])
                    next_pending.append(batch[mid:])
                    print(
                        f"  [warn] graphql r{rnd} batch failed ({len(batch)} queries) "
                        f"— splitting: {str(err)[:100]}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"  [warn] graphql query failed after {rnd} rounds: "
                        f"{batch[0][:60]} — {str(err)[:80]}",
                        file=sys.stderr,
                    )
        pending = next_pending

    # 补漏：部分别名返回 null 的 query（批成功但个别别名超时）单独再跑一轮小批。
    # 4 别名轻文档几乎不会失败；仍缺的留给调用方 REST 回退。
    missing = [q for q in unique if q not in out]
    if missing:
        sweep = [missing[i : i + 4] for i in range(0, len(missing), 4)]
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
            fut_to_batch = {pool.submit(_run_batch, b): b for b in sweep}
            for fut in as_completed(fut_to_batch):
                result, curs, err = fut.result()
                if err is None:
                    out.update(result)
                    cursors_all.update(curs)
        print(
            f"  · graphql sweep: {len(missing)} partial/failed queries re-run, "
            f"{len([q for q in unique if q in out])}/{len(unique)} total",
            file=sys.stderr,
        )

    # P1 修复（2026-09）— 游标追第二页：结果满页且 hasNextPage 的 query 用
    # after 游标再取 per_page 个。GraphQL search 无 sort=stars，best-match 第
    # 51-100 名原本拿不到；单 alias per_page=100 撞资源上限，游标是唯一手段。
    # 实测:带 after 的文档比首页更贵,满 batch_size 会撞资源上限 — 起步就
    # 用半批(≤4),失败再对半拆分,两轮后放弃(该 query 只留第一页,无数据损失)。
    if follow_page2:
        full = [
            q
            for q in unique
            if q in out and len(out[q]) >= per_page and cursors_all.get(q)
        ]
        if full:
            n_added = 0
            pending2 = [full[i : i + 4] for i in range(0, len(full), 4)]
            for _round in range(3):
                if not pending2:
                    break
                nxt: list[list[str]] = []
                for chunk in pending2:
                    result, _c2, err = _run_batch(
                        chunk, cursors=[cursors_all[q] for q in chunk]
                    )
                    if err is not None:
                        if len(chunk) > 1:
                            mid = len(chunk) // 2
                            nxt.extend([chunk[:mid], chunk[mid:]])
                        else:
                            print(
                                f"  [warn] graphql page2 query failed: "
                                f"{chunk[0][:50]} — {str(err)[:60]}",
                                file=sys.stderr,
                            )
                        continue
                    for q, repos2 in result.items():
                        seen_names = {r["name"] for r in out[q]}
                        fresh = [r for r in repos2 if r["name"] not in seen_names]
                        out[q] = out[q] + fresh
                        n_added += len(fresh)
                pending2 = nxt
            print(
                f"  · graphql page2: {len(full)} full pages followed, +{n_added} repos",
                file=sys.stderr,
            )
    return out


if __name__ == "__main__":
    # 冒烟：python3 -m sources.github_graphql
    t0 = time.monotonic()
    res = gh_search_batch(
        [
            "topic:ai-agent stars:>500",
            "topic:langgraph stars:>200",
            'stars:>500 "MCP server" in:name,description',
        ],
        per_page=10,
    )
    for q, repos in res.items():
        top = repos[0] if repos else None
        print(f"  {q:<55} → {len(repos)} repos, top: {top['name'] if top else '—'}")
    print(f"  {time.monotonic() - t0:.1f}s")
