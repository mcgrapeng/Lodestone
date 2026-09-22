import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Header } from './components/Header'
import { HeroStats } from './components/HeroStats'
import { SearchBar } from './components/SearchBar'
import { TrendingRail } from './components/TrendingRail'
import { HotNowSection } from './components/HotNowSection'
import { GainersSection } from './components/GainersSection'
import { CategoryBrowser } from './components/CategoryBrowser'
import { SearchResults } from './components/SearchResults'
import { StatsPanel } from './components/StatsPanel'
import { LocalTab } from './components/LocalTab'
import { UpgradeProgressBanner } from './components/UpgradeProgressBanner'
import { RepoDrawer } from './components/RepoDrawer'
import { SettingsDrawer } from './components/SettingsDrawer'
import { Skeleton } from './components/Skeleton'
import { CrawlProgress } from './components/CrawlProgress'
import { TabNav, type TabId } from './components/TabNav'
import { api } from './lib/api'
import { matchRepo, sourceOf, type RepoFilters, type SortKey, type SourceKind, type SourceCounts } from './lib/filters'
import { useUrlState } from './lib/useUrlState'
import type {
  CrawlProgress as CrawlProgressT,
  InstallStatus,
  LocalData,
  Repo,
  Snapshot,
  Stats,
  Settings,
} from './lib/types'

// ponytail: Vite proxy forwards /api/* to radar.py serve on :8765, so same-origin fetch.
const POLL_INTERVAL_MS = 30_000
const CRAWL_PROGRESS_POLL_MS = 2_000
const CRAWL_PROGRESS_IDLE_MS = 30_000

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
  // ponytail: 2026-09 — 本机 tab 数据 + 升级进度。
  // local 与 snapshot 独立(local 不依赖 crawl 数据)。installStatus 给
  // UpgradeProgressBanner 轮询,运行中 2s,idle 30s(同 crawl_progress 节奏)。
  const [local, setLocal] = useState<LocalData | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [installStatus, setInstallStatus] = useState<InstallStatus | null>(null)
  const installPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

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

  // ponytail: 2026-09 — 进度条 banner 数据源。
  // running=true 时 2s 轮询;running=false 时降到 30s 节省请求(空闲 24h = 2880 次 →
  // 2880/15 = 192 次)。切换到 running=true 时立刻 reset 到 2s。
  const crawlPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const crawlPollMsRef = useRef(CRAWL_PROGRESS_POLL_MS)
  const reschedule = (ms: number) => {
    if (ms === crawlPollMsRef.current) return
    crawlPollMsRef.current = ms
    if (crawlPollRef.current) {
      clearInterval(crawlPollRef.current)
      crawlPollRef.current = setInterval(tick, ms)
    }
  }
  const tick = async () => {
    const p = await api.getCrawlProgress()
    setCrawlProgress(p)
    reschedule(p.running ? CRAWL_PROGRESS_POLL_MS : CRAWL_PROGRESS_IDLE_MS)
  }
  useEffect(() => {
    let cancelled = false
    tick()
    crawlPollRef.current = setInterval(tick, crawlPollMsRef.current)
    return () => {
      cancelled = true
      if (crawlPollRef.current) clearInterval(crawlPollRef.current)
    }
    // tick / reschedule 闭包引用稳定,只挂一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ponytail: 2026-09 — install 进度轮询(UpgradeProgressBanner 用)。running=true 时 2s,
  // idle 30s,模式与 crawl_progress 完全相同。
  const rescheduleInstall = (ms: number) => {
    if (ms === installPollMsRef.current) return
    installPollMsRef.current = ms
    if (installPollRef.current) {
      clearInterval(installPollRef.current)
      installPollRef.current = setInterval(tickInstall, ms)
    }
  }
  const installPollMsRef = useRef(CRAWL_PROGRESS_POLL_MS)
  const tickInstall = async () => {
    const s = await api.getInstallStatus()
    setInstallStatus(s)
    rescheduleInstall(s.running ? CRAWL_PROGRESS_POLL_MS : CRAWL_PROGRESS_IDLE_MS)
  }
  useEffect(() => {
    let cancelled = false
    tickInstall()
    installPollRef.current = setInterval(tickInstall, installPollMsRef.current)
    return () => {
      cancelled = true
      if (installPollRef.current) clearInterval(installPollRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    setRefreshToast(null)
    // ponytail: 2026-09 — 清掉上一次 handleRefresh 留下的轮询 interval,避免
    // 用户连点"刷新雷达"叠 N 个 setInterval 同时跑(每次叠 6min 监听)。
    if (refreshPollRef.current) {
      clearInterval(refreshPollRef.current)
      refreshPollRef.current = null
    }
    try {
      const res = await api.triggerCrawl()
      if (!res.ok) {
        setRefreshing(false)
        setRefreshToast(`❌ ${res.error ?? '触发失败'}`)
        return
      }
      setRefreshToast('🚀 已触发后台爬取,完成后自动刷新数据')
      // ponytail: poll /api/data every 5s for up to 6 minutes, stop when fetched_at changes.
      const start = Date.now()
      refreshPollRef.current = setInterval(async () => {
        try {
          const snap = await api.getSnapshot()
          if (snap.fetched_at && snap.fetched_at !== initialFetchedAtRef.current) {
            setSnapshot(snap)
            api.getStats().then(setStats).catch(() => undefined)
            setRefreshToast('✅ 爬取完成,数据已更新')
            if (refreshPollRef.current) {
              clearInterval(refreshPollRef.current)
              refreshPollRef.current = null
            }
            setTimeout(() => setRefreshToast(null), 4000)
          }
        } catch { /* ignore */ }
        if (Date.now() - start > 360_000) {
          if (refreshPollRef.current) {
            clearInterval(refreshPollRef.current)
            refreshPollRef.current = null
          }
          setRefreshToast('⏱ 等待超时,请手动刷新')
        }
      }, 5000)
    } catch (e) {
      setRefreshToast(`❌ ${(e as Error).message}`)
    } finally {
      // ponytail: 2026-09 — 错误路径立即清 refreshing,不再被 1.5s 兜底延迟骗用户。
      setRefreshing(false)
    }
  }
  const refreshPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

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
  // ponytail: FU-2.1 — 拆成 counts + summary 两个 memo,counts 喂 Header marquee,
  // summary 喂右上小标签。一次去重扫描,两处复用。
  const sourceCounts = useMemo<SourceCounts>(() => {
    const zero: SourceCounts = { github: 0, huggingface: 0, mcp: 0, arxiv: 0, awesome_lists: 0, hackernews_ai: 0, other: 0 }
    if (!snapshot) return zero
    const seen = new Set<string>()
    const counts: SourceCounts = { ...zero }
    const tally = (r: Repo) => {
      if (seen.has(r.name)) return
      seen.add(r.name)
      counts[sourceOf(r)] += 1
    }
    snapshot.hot_now.forEach(tally)
    snapshot.categories.forEach((c) => c.repos.forEach(tally))
    return counts
  }, [snapshot])

  const sourceSummary = useMemo(() => {
    const parts: string[] = []
    if (sourceCounts.github) parts.push(`GitHub ${sourceCounts.github}`)
    if (sourceCounts.huggingface) parts.push(`HF ${sourceCounts.huggingface}`)
    if (sourceCounts.mcp) parts.push(`MCP ${sourceCounts.mcp}`)
    if (sourceCounts.arxiv) parts.push(`arXiv ${sourceCounts.arxiv}`)
    return parts.join(' · ')
  }, [sourceCounts])

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

  // ponytail: 2026-09 — URL 里 tab=search 但没有搜索词 → 同步把 URL tab 重置为
  // 'hot',TabNav 才能正确高亮。旧实现只在 activeTab 局部修正,URL 仍记着
  // tab=search,导致 TabNav 不渲染"搜索结果" tab → 4 个 tab 0 个高亮。
  // 用 useEffect 跑副作用,不在 render body 触发 setState 避免死循环。
  useEffect(() => {
    if (url.tab === 'search' && !url.q) {
      setUrl({ tab: 'hot' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url.tab, url.q])
  const activeTab: TabId = url.tab === 'search' && !url.q ? 'hot' : (url.tab as TabId)

  // ponytail: 2026-09 — 本机 tab 主动加载(只在 tab 切到 local 时拉一次)。
  // /api/local 慢(detect_local_skills + compute_upgradable 各 5-10s),
  // 不像 /api/data 那样 30s 轮询。
  const loadLocal = useCallback(async (signal: { v: boolean }) => {
    try {
      const data = await api.getLocal()
      if (!signal.v) {
        setLocal(data)
        setLocalError(null)
      }
    } catch (e) {
      if (!signal.v) setLocalError((e as Error).message)
    }
  }, [])
  // ponytail: 2026-09 P6 — loadLocal 提升成 ref。所有 callback(install status 翻转、
  // RepoDrawer onRepoChanged、30s 轮询)都能调到最新函数,不会因为闭包 stale
  // 导致只调用第一次定义的 loadLocal。
  const loadLocalRef = useRef(loadLocal)
  useEffect(() => {
    loadLocalRef.current = loadLocal
  }, [loadLocal])
  useEffect(() => {
    const signal = { v: false }
    if (activeTab === 'local') {
      loadLocal(signal)
      // ponytail: 2026-09 — 首次进本机 tab 自动触发 cache 刷新(如果 daemon 还没跑)。
      // 之前要等 daemon 5min 周期,首次体验很差(全是"未检查")。现在用户点 tab
      // 立刻看到 banner "正在算",5-30s 后徽章出现。
      api.getLocal().then((data) => {
        if (signal.v) return
        const cs = data.cache_state
        if (!cs?.exists || cs.total === 0) {
          api.triggerRefresh().catch(() => {
            // 静默 — 失败的话 banner 会显示错误 + 重试按钮
          })
        }
      }).catch(() => {
        // loadLocal 本身失败了,不重复触发
      })
    }
    return () => {
      signal.v = true
    }
  }, [activeTab, loadLocal])
  // ponytail: 2026-09 P6 — 本机 tab 时 30s 轮询一次(用户停留 5 min 也不 stale)。
  // 离开 tab 立刻 clearInterval,回来重新挂。
  useEffect(() => {
    if (activeTab !== 'local') return
    const t = setInterval(() => loadLocalRef.current({ v: false }), 30_000)
    return () => clearInterval(t)
  }, [activeTab])
  // ponytail: 2026-09 P6 — install status 翻转触发 loadLocal。升级全部跑完后
  // running true→false 转换,banner 显示完成,local tab 数据应立即更新(否则 30s
  // 才轮询)。prevRunningRef 跨 render 保留上一次的 running 状态。
  const prevRunningRef = useRef(false)
  useEffect(() => {
    const wasRunning = prevRunningRef.current
    const isRunning = installStatus?.running ?? false
    prevRunningRef.current = isRunning
    if (wasRunning && !isRunning) {
      // 跑批刚完成 → 立即刷数据(skill 计数/upgradable map 全部已变化)
      loadLocalRef.current({ v: false })
    }
  }, [installStatus?.running])

  // ponytail: 2026-09 — Trending 列表只来自真实 `snapshot.trending`(github.com/trending
  // 今日上榜)。旧 fallback:trending 为空或 < 8 时回 hot_now 星标榜,标题"今日 Trending"
  // 下显示星标榜骗用户。改成空就空,UI 自然渲染空态卡片。
  const snapshotTrending = useMemo(() => {
    if (!snapshot) return []
    return snapshot.trending ?? []
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
        sourceCounts={sourceCounts}
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
            upgradableBadge={local?.counts?.upgradable ?? 0}
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
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.24, ease: 'easeOut' }}
          >
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

            {activeTab === 'local' && (
              <div className="mx-auto max-w-7xl space-y-4 px-6 pt-4">
                <UpgradeProgressBanner status={installStatus} />
                {local ? (
                  <LocalTab
                    local={local}
                    onRefresh={() => loadLocal({ v: false })}
                    onOpenOrigin={(originUrl: string) => window.open(originUrl, '_blank')}
                  />
                ) : localError ? (
                  <div className="card-surface border-red-500/30 p-4 text-sm text-error">
                    ⚠️ 无法加载 /api/local:{localError}
                  </div>
                ) : (
                  <div className="card-surface p-8 text-center text-sm text-foreground-subtle">
                    加载中...
                  </div>
                )}
              </div>
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
          </motion.div>
        </AnimatePresence>
      )}

      {drawerRepo && (
          <RepoDrawer
            repo={drawerRepo}
            open={drawerOpen}
            onClose={closeDrawer}
            // ponytail: 2026-09 P6 修复 — RepoDrawer 装/卸后既刷 /api/data 也刷 /api/local。
            // 旧实现只刷 /api/data → TabNav ↑N 角标 5 min 内不更新,本机 tab 数据过期。
            // 用 ref 而不是依赖 loadLocal 闭包,避免无限循环(stale closure)。
            onRepoChanged={(r) => {
              setDrawerRepo(r)
              load()
              loadLocalRef.current({ v: false })
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
