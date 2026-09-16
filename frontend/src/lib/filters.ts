// ponytail: 统一的仓库筛选/排序/来源识别 — 纯函数，无 React。
// 之前同样的 filter 逻辑在 App / TrendingRail / CategorySection / GainersSection
// 四处各写一份（行为还不一致：Gainers 只过滤当前页）。全部收敛到这里。

import type { Repo } from './types'

export type SourceKind = 'github' | 'huggingface' | 'mcp' | 'arxiv' | 'other'

export type SortKey = 'stars' | 'recent' | 'name'

export interface RepoFilters {
  query: string
  source: SourceKind | 'all'
  sort: SortKey
}

export const DEFAULT_FILTERS: RepoFilters = {
  query: '',
  source: 'all',
  sort: 'stars',
}

/** 从 repo.source / repo.url 推断来源类别（HF/MCP/GitHub/其他）。 */
export function sourceOf(repo: Repo): SourceKind {
  const src = repo.source ?? ''
  if (src.startsWith('huggingface')) return 'huggingface'
  if (src === 'mcp_registry') return 'mcp'
  if (src === 'arxiv') return 'arxiv'
  if (src.startsWith('github') || src === 'github_search_html' || src === 'gh_graphql') {
    return 'github'
  }
  // 旧快照可能缺 source 字段 — 按 URL 兜底
  const url = repo.url ?? ''
  if (url.includes('huggingface.co')) return 'huggingface'
  if (url.includes('arxiv.org')) return 'arxiv'
  if (url.includes('github.com')) return 'github'
  return 'other'
}

export const SOURCE_LABELS: Record<SourceKind | 'all', string> = {
  all: '全部来源',
  github: 'GitHub',
  huggingface: 'HuggingFace',
  mcp: 'MCP',
  arxiv: 'arXiv',
  other: '其他',
}

/** 单个仓库是否匹配搜索词（名称 / 中文描述 / 原描述 / topics）。 */
export function matchRepo(repo: Repo, q: string): boolean {
  if (!q) return true
  const needle = q.toLowerCase()
  return (
    repo.name.toLowerCase().includes(needle) ||
    (repo.desc_zh ?? '').toLowerCase().includes(needle) ||
    (repo.desc ?? '').toLowerCase().includes(needle) ||
    (repo.topics ?? []).some((t) => t.toLowerCase().includes(needle))
  )
}

/** 应用全部筛选（query + source），再按 sort 排序。返回新数组。 */
export function applyFilters(
  repos: Repo[],
  { query, source, sort }: RepoFilters,
): Repo[] {
  const filtered = repos.filter(
    (r) => matchRepo(r, query) && (source === 'all' || sourceOf(r) === source),
  )
  const sorted = [...filtered]
  if (sort === 'stars') {
    sorted.sort((a, b) => (b.stars ?? 0) - (a.stars ?? 0))
  } else if (sort === 'recent') {
    // pushed（最后 push）优先，缺失退回 updated，**都无则排最后**。
    // 旧实现 `key(b).localeCompare(key(a))` 对空字符串排序会把无日期的排最前，
    // 与注释意图相反;用显式 missing-last 比较修正。
    const key = (r: Repo) => r.pushed ?? r.updated ?? ''
    sorted.sort((a, b) => {
      const ka = key(a); const kb = key(b)
      if (!ka && !kb) return 0
      if (!ka) return 1
      if (!kb) return -1
      return kb.localeCompare(ka)
    })
  } else {
    sorted.sort((a, b) => a.name.localeCompare(b.name))
  }
  return sorted
}
