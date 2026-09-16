import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Header } from './components/Header'
import { HeroStats } from './components/HeroStats'
import { SearchBar } from './components/SearchBar'
import { TrendingRail } from './components/TrendingRail'
import { HotNowSection } from './components/HotNowSection'
import { GainersSection } from './components/GainersSection'
import { CategoryBrowser } from './components/CategoryBrowser'
import { SearchResults } from './components/SearchResults'
import { StatsPanel } from './components/StatsPanel'
import { RepoDrawer } from './components/RepoDrawer'
import { SettingsDrawer } from './components/SettingsDrawer'
import { Skeleton } from './components/Skeleton'
import { CrawlProgress } from './components/CrawlProgress'
import { TabNav, type TabId } from './components/TabNav'
import { api } from './lib/api'
import { matchRepo, sourceOf, type RepoFilters, type SortKey, type SourceKind } from './lib/filters'
import { useUrlState } from './lib/useUrlState'
import type { CrawlProgress as CrawlProgressT, Repo, Snapshot, Stats, Settings } from './lib/types'

// ponytail: Vite proxy forwards /api/* to radar.py serve on :8765, so same-origin fetch.
const POLL_INTERVAL_MS = 30_000
const CRAWL_PROGRESS_POLL_MS = 2_000

export function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [drawerRepo, setDrawerRepo] = useState<Repo | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [refreshToast, setRefreshToast] = useState<string | null>(null)
  const [crawlProgress, setCrawlProgress] = useState<CrawlProgressT | null>(null)
  const initialFetchedAtRef = useRef<string | null>(null)

  // URL 即状态（?tab=&q=&cat=&sort=&src=）— 刷新 / 分享 / 收藏都能还原视图
  const [url, setUrl] = useUrlState()
  const lastTabRef = useRef<TabId>('hot')

  const filters: RepoFilters = useMemo(
    () => ({ query: url.q, source: url.src as SourceKind | 'all', sort: url.sort as SortKey }),
    [url.q, url.src, url.sort],
  )
  const patchFilters = useCallback(
    (patch: Partial<RepoFilters>) => {
      setUrl({
        ...(patch.sort && { sort: patch.sort }),
        ...(patch.source && { src: patch.source }),
      })
    },
    [setUrl],
  )

  // 搜索联动：输入即切「搜索结果」tab；清空回到之前的 tab（不靠 effect，避免循环）
  const handleQueryChange = useCallback(
    (q: string) => {
      if (q) {
        if (url.tab !== 'search') lastTabRef.current = url.tab as TabId
        setUrl({ q, tab: 'search' })
      } else {
        setUrl({ q, tab: lastTabRef.current === 'search' ? 'hot' : lastTabRef.current })
      }
    },
    [url.tab, setUrl],
  )

  const switchTab = useCallback(
    (tab: TabId) => {
      if (tab !== 'search') lastTabRef.current = tab
      setUrl({ tab })
      window.scrollTo({ top: 0 })
    },
    [setUrl],
  )

  // ponytail: load /api/data + /api/stats on mount, then poll both every 30s for
  // fresh snapshots without hammering the backend.
  // ponytail: 2026-09 — 之前 `if (!stats)` 只拉一次,导致第一次 crawl 跑完前
  // stats 是空 {} 锁住,UI 永远显示「0 repos」。每次 load 都重拉,小 endpoint,
  // 不值得缓存判断。
  const load = useCallback(async () => {
    try {
      const snap = await api.getSnapshot()
      setSnapshot(snap)
      setError(null)
      // ponytail: settings 加载与 snapshot 解耦 — 一次失败不影响另一次
      api.getSettings().then(setSettings).catch(() => setSettings(null))
      api.getStats().then(setStats).catch(() => undefined)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_INTERVAL_MS)
    return () => clearInterval(t)
  }, [load])

  // ponytail: 2026-09 — 进度条 banner 数据源。2s 轮询 /api/crawl/progress,crawl 不
  // 在时也轮询(开销 ~50B JSON)以检测外部触发的爬取。running=false 时不显示 banner,
  // 但保留 polling 方便下次 handleRefresh 立即接上。
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      const p = await api.getCrawlProgress()
      if (!cancelled) setCrawlProgress(p)
    }
    tick()
    const t = setInterval(tick, CRAWL_PROGRESS_POLL_MS)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    setRefreshToast(null)
    try {
      const res = await api.triggerCrawl()
      if (!res.ok) {
        setRefreshToast(`❌ ${res.error ?? '触发失败'}`)
        return
      }
      setRefreshToast('🚀 已触发后台爬取,完成后自动刷新数据')
      // ponytail: poll /api/data every 5s for up to 6 minutes, stop when fetched_at changes.
      const start = Date.now()
      const stop = setInterval(async () => {
        try {
          const snap = await api.getSnapshot()
          if (snap.fetched_at && snap.fetched_at !== initialFetchedAtRef.current) {
            setSnapshot(snap)
            api.getStats().then(setStats).catch(() => undefined)
            setRefreshToast('✅ 爬取完成,数据已更新')
            clearInterval(stop)
            setTimeout(() => setRefreshToast(null), 4000)
          }
        } catch { /* ignore */ }
        if (Date.now() - start > 360_000) {
          clearInterval(stop)
          setRefreshToast('⏱ 等待超时,请手动刷新')
        }
      }, 5000)
    } catch (e) {
      setRefreshToast(`❌ ${(e as Error).message}`)
    } finally {
      setTimeout(() => setRefreshing(false), 1500)
    }
  }

  // ponytail: capture initial fetched_at so the polling loop can detect a fresh crawl.
  useEffect(() => {
    if (snapshot?.fetched_at && !initialFetchedAtRef.current) {
      initialFetchedAtRef.current = snapshot.fetched_at
    }
  }, [snapshot?.fetched_at])

  const totalRepos = useMemo(() => {
    // 视觉审查修正：顶栏与统计卡同一口径（去重），消除 794 vs 751 的矛盾
    if (!snapshot) return 0
    if (stats?.total_repos) return stats.total_repos
    const seen = new Set<string>()
    let n = 0
    for (const r of snapshot.hot_now) { if (!seen.has(r.name)) { seen.add(r.name); n++ } }
    for (const c of snapshot.categories) {
      for (const r of c.repos) { if (!seen.has(r.name)) { seen.add(r.name); n++ } }
    }
    return n
  }, [snapshot, stats])

  // 视觉审查修正：顶栏数字换成指标卡没有的分源计数（消除与指标卡的重复）
  const sourceSummary = useMemo(() => {
    if (!snapshot) return ''
    const seen = new Set<string>()
    const counts: Record<string, number> = {}
    const tally = (r: Repo) => {
      if (seen.has(r.name)) return
      seen.add(r.name)
      const s = sourceOf(r)
      counts[s] = (counts[s] ?? 0) + 1
    }
    snapshot.hot_now.forEach(tally)
    snapshot.categories.forEach((c) => c.repos.forEach(tally))
    const parts: string[] = []
    if (counts.github) parts.push(`GitHub ${counts.github}`)
    if (counts.huggingface) parts.push(`HF ${counts.huggingface}`)
    if (counts.mcp) parts.push(`MCP ${counts.mcp}`)
    if (counts.arxiv) parts.push(`arXiv ${counts.arxiv}`)
    return parts.join(' · ')
  }, [snapshot])

  // 搜索 tab 徽标计数 — 与 SearchResults 的池子同口径（hot_now + 分类去重）
  const searchCount = useMemo(() => {
    if (!snapshot || !url.q) return 0
    const q = url.q
    const seen = new Set<string>()
    let n = 0
    for (const r of snapshot.hot_now) {
      if (!seen.has(r.name)) { seen.add(r.name); if (matchRepo(r, q)) n++ }
    }
    for (const c of snapshot.categories) {
      for (const r of c.repos) {
        if (!seen.has(r.name)) { seen.add(r.name); if (matchRepo(r, q)) n++ }
      }
    }
    return n
  }, [snapshot, url.q])

  function openRepo(repo: Repo) {
    setDrawerRepo(repo)
    setDrawerOpen(true)
  }

  function closeDrawer() {
    setDrawerOpen(false)
    setTimeout(() => setDrawerRepo(null), 200)
  }

  // URL 里 tab=search 但没有搜索词（手动改地址栏等）→ 回落热门
  const activeTab: TabId = url.tab === 'search' && !url.q ? 'hot' : (url.tab as TabId)

  // Trending 专区数据 — 2026-09 修复：直接消费快照的 trending 列表（真实的
  // github.com/trending 今日上榜），旧逻辑用 hot_now 兜底导致显示的是星标榜
  const snapshotTrending = useMemo(() => {
    if (!snapshot) return []
    if (snapshot.trending?.length) return snapshot.trending
    const marked = snapshot.hot_now.filter((r) => r.trending)
    return marked.length >= 8 ? marked : snapshot.hot_now.slice(0, 16)
  }, [snapshot])

  // ponytail: "/" 全局快捷键聚焦搜索框（输入框内按 Esc 清空失焦）。
  // 输入状态下不抢按键 — 只在非编辑焦点时响应。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      const typing =
        el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
      if (e.key === '/' && !typing) {
        e.preventDefault()
        document.querySelector<HTMLInputElement>('input[type="search"]')?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="min-h-screen pb-24">
      <Header
        fetchedAt={snapshot?.fetched_at ?? null}
        refreshing={refreshing}
        onRefresh={handleRefresh}
        onSettings={() => setSettingsOpen(true)}
        settingsStatus={settings?.updated_at ? 'configured' : 'none'}
        totalRepos={totalRepos}
        totalCategories={snapshot?.categories.length ?? 0}
        sourceSummary={sourceSummary}
      />

      {/* sticky 搜索 + tab（同一容器，一层 sticky 偏移） */}
      <div className="sticky top-[57px] z-30 border-b border-border-muted bg-background/85 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-6 pt-3">
          <SearchBar value={url.q} onChange={handleQueryChange} />
        </div>
        <div className="mx-auto max-w-7xl px-6 pb-2 pt-2.5">
          <TabNav
            active={activeTab}
            onChange={switchTab}
            searchActive={!!url.q}
            searchCount={searchCount}
          />
        </div>
      </div>

      {crawlProgress && <CrawlProgress progress={crawlProgress} />}

      {refreshToast && (
        <div className="fixed left-1/2 top-20 z-50 -translate-x-1/2 rounded-full border border-primary/30 bg-background-muted/95 px-4 py-2 text-sm text-primary shadow-lg shadow-primary/20 backdrop-blur">
          {refreshToast}
        </div>
      )}

      {error && (
        <div className="mx-auto mt-6 max-w-3xl px-6">
          <div className="card-surface border-red-500/30 p-4 text-sm text-error">
            ⚠️ 无法加载 /api/data:{error}
            <div className="mt-1 text-xs text-foreground-subtle">
              请确认 <code className="text-primary">radar.py serve</code> 正在 :8765 运行,
              然后 <code className="text-primary">radar.py crawl</code> 一次。
            </div>
          </div>
        </div>
      )}

      {!snapshot ? (
        <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
          <Skeleton className="h-12 w-2/3" />
          <Skeleton className="h-6 w-1/2" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="card-surface p-4">
                <Skeleton className="mb-2 h-4 w-1/3" />
                <Skeleton className="h-8 w-2/3" />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          {activeTab === 'hot' && (
            <>
              <HeroStats snapshot={snapshot} stats={stats} />
              <HotNowSection repos={snapshot.hot_now} onOpen={openRepo} />
            </>
          )}

          {activeTab === 'trending' && (
            <>
              <TrendingRail repos={snapshotTrending} onOpen={openRepo} />
              <GainersSection onOpen={openRepo} />
            </>
          )}

          {activeTab === 'cats' && (
            <CategoryBrowser
              categories={snapshot.categories}
              selected={url.cat}
              onSelect={(id) => setUrl({ cat: id })}
              filters={filters}
              onFiltersChange={patchFilters}
              onOpen={openRepo}
            />
          )}

          {activeTab === 'search' && url.q && (
            <SearchResults
              snapshot={snapshot}
              filters={filters}
              onFiltersChange={patchFilters}
              onOpen={openRepo}
            />
          )}

          {activeTab === 'stats' && <StatsPanel stats={stats} />}
        </>
      )}

      {drawerRepo && (
          <RepoDrawer
            repo={drawerRepo}
            open={drawerOpen}
            onClose={closeDrawer}
            // 安装/卸载/更新成功 → 更新抽屉内状态 + 重拉快照，全站「已装」徽标实时刷新
            onRepoChanged={(r) => {
              setDrawerRepo(r)
              load()
            }}
          />
        )}

      <SettingsDrawer
        open={settingsOpen}
        initial={settings}
        onClose={() => setSettingsOpen(false)}
        onSaved={(s) => {
          setSettings(s)
          setRefreshToast('✓ 设置已保存。下次 crawl 自动用新 provider。')
          setTimeout(() => setRefreshToast(null), 4000)
        }}
      />

      <footer className="mt-16 border-t border-border-muted py-6 text-center text-[11px] text-foreground-subtle">
        Lodestone · React 19 + Appica UI · 数据源自 GitHub / HuggingFace / MCP Registry ·
        爬虫见 <code className="text-foreground-subtle">scrapers/</code>
      </footer>
    </div>
  )
}
