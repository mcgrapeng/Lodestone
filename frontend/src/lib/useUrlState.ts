// ponytail: URL query 状态（?tab=&q=&cat=&sort=&src=）— 刷新/分享/回车都能还原视图。
// 无 react-router 依赖：读 window.location.search，写 replaceState（不打扰历史），
// popstate（后退/前进）时重新读。

import { useCallback, useEffect, useState } from 'react'

export interface UrlState {
  tab: string          // 'hot' | 'cats' | 'stats' | 'search'
  q: string            // 搜索词
  cat: string | null   // 分类 tab 里选中的分类 id
  sort: string         // 'stars' | 'recent' | 'name'
  src: string          // 'all' | 'github' | 'huggingface' | 'mcp'
}

const DEFAULT_STATE: UrlState = { tab: 'hot', q: '', cat: null, sort: 'stars', src: 'all' }

const VALID_TABS = new Set(['hot', 'trending', 'cats', 'stats', 'search'])
const VALID_SORTS = new Set(['stars', 'recent', 'name'])
const VALID_SRCS = new Set(['all', 'github', 'huggingface', 'mcp', 'arxiv'])

function readUrl(): UrlState {
  try {
    const p = new URLSearchParams(window.location.search)
    const tab = p.get('tab') ?? DEFAULT_STATE.tab
    return {
      tab: VALID_TABS.has(tab) ? tab : DEFAULT_STATE.tab,
      q: p.get('q') ?? '',
      cat: p.get('cat'),
      sort: VALID_SORTS.has(p.get('sort') ?? '') ? p.get('sort')! : 'stars',
      src: VALID_SRCS.has(p.get('src') ?? '') ? p.get('src')! : 'all',
    }
  } catch {
    return { ...DEFAULT_STATE }
  }
}

function writeUrl(s: UrlState) {
  const p = new URLSearchParams()
  if (s.tab !== 'hot') p.set('tab', s.tab)
  if (s.q) p.set('q', s.q)
  if (s.cat) p.set('cat', s.cat)
  if (s.sort !== 'stars') p.set('sort', s.sort)
  if (s.src !== 'all') p.set('src', s.src)
  const qs = p.toString()
  window.history.replaceState(
    null,
    '',
    qs ? `${window.location.pathname}?${qs}` : window.location.pathname,
  )
}

export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const [state, setState] = useState<UrlState>(readUrl)

  // 浏览器后退/前进 → 重读 URL
  useEffect(() => {
    const onPop = () => setState(readUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const update = useCallback((patch: Partial<UrlState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch }
      writeUrl(next)
      return next
    })
  }, [])

  return [state, update]
}
