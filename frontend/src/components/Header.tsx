import { useEffect, useState } from 'react'
import { Github, RefreshCw, Loader2, Settings } from 'lucide-react'
import { RadarFilled } from '@appica/icons-react'
import { Button } from '@appica/ui-react'

// 视觉审查修正：精确到秒的时间戳无信息量 — 相对时间，悬停显示精确值
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

export interface HeaderProps {
  fetchedAt: string | null
  refreshing: boolean
  onRefresh: () => void
  onSettings: () => void
  settingsStatus: 'none' | 'untested' | 'configured'
  totalRepos: number
  totalCategories: number
  sourceSummary?: string
  sourceCounts?: Record<string, number>
}

export function Header({
  fetchedAt,
  refreshing,
  onRefresh,
  onSettings,
  settingsStatus,
  totalRepos,
  totalCategories,
  sourceSummary,
  sourceCounts,
}: HeaderProps) {
  // ponytail: 2026-09 — 相对时间 tick。旧实现 fetch-at 时算一次后定格,刷新后
  // "刚刚" / "1 分钟前" 不变。每 30s 触发一次 setState 让组件重渲染,
  //  让"相对时间"保持新鲜直到时变换一次。
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!fetchedAt) return
    const t = setInterval(() => setTick((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [fetchedAt])

  return (
    <header className="sticky top-0 z-40 border-b border-border-muted bg-background/85 backdrop-blur-md">
      {/* 品牌色 hairline — 顶栏与内容之间的精致分割 */}
      <div className="h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2.5">
          {/* 2026-09 UI 回归 — Appica monochrome 徽标:radar 图标 + token 排版,无渐变 */}
          <div className="grid h-9 w-9 place-items-center rounded-xl border border-border-muted bg-background-subtle">
            <RadarFilled className="h-5 w-5 text-primary" />
          </div>
          <div className="leading-tight">
            {/* ponytail: 2026-09 — 升级到 h1。screen reader 用户在 Trending/Cats/
                Search/Stats tab 没顶层标题;HeroStats 里的 h1 移到 Header 让每页都可见。 */}
            <h1 className="text-[15px] font-semibold tracking-tight text-foreground">
              Lodestone
            </h1>
            <div className="text-[11px] text-foreground-subtle">
              GitHub 热门 AI · Skills · Plugins
            </div>
          </div>
        </div>

        <div className="ml-auto hidden items-center gap-4 text-xs text-foreground-subtle sm:flex">
          <div className="flex items-center gap-1.5">
            <Github className="h-3.5 w-3.5" />
            <span>{sourceSummary || `${totalRepos.toLocaleString()} 个仓库`}</span>
            {/* ponytail: 2026-09 — `·` 分隔符条件渲染。旧实现无条件渲染,出现
                「· 0 分类」前导孤立点。同时 sourceSummary 与 totalRepos 互斥:
                有 sourceSummary 时不要再重复仓库总数。 */}
            {(sourceSummary || totalRepos > 0) && <span className="text-foreground-subtle">·</span>}
            <span>{totalCategories} 分类</span>
          </div>
          {fetchedAt && (
            <>
              <div className="h-3 w-px bg-background-strong" />
              <div className="text-foreground-subtle" title={new Date(fetchedAt).toLocaleString('zh-CN', { hour12: false })}>
                {relativeTime(fetchedAt)}更新
              </div>
            </>
          )}
        </div>

        {/* ponytail: 2026-09 — Settings 按钮加 title 提示(mouse 用户可见),状态点
            从 `right-1 top-1` 改 `right-2 top-2`,避开 p-2 的 padding 让点不被裁切。 */}
        <button
          onClick={onSettings}
          aria-label="LLM 设置"
          title="LLM 设置"
          className="relative rounded p-2 text-foreground-subtle hover:bg-background-muted hover:text-foreground"
        >
          <Settings size={16} />
          {settingsStatus === 'configured' && (
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-emerald-500" />
          )}
          {settingsStatus === 'untested' && (
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-amber-500" />
          )}
        </button>

        <Button
          size="sm"
          variant="primary"
          onClick={onRefresh}
          disabled={refreshing}
          className="gap-1.5"
        >
          {refreshing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          <span>{refreshing ? '爬取中…' : '刷新雷达'}</span>
        </Button>
      </div>
      {/* ponytail: FU-2.1 — marquee reads live counts from App's sourceCounts
          (snapshot.hot_now + categories dedup, same tally as sourceSummary).
          Counts refresh on /api/data poll (30s); last crawl piggy-backs on the
          30s relativeTime tick already in this component. */}
      <div className="overflow-hidden border-t border-border-muted bg-background-muted/30">
        <div className="animate-marquee whitespace-nowrap text-[11px] text-accent-cyan/80 py-1.5 px-4">
          → GitHub: {sourceCounts?.github ?? 0} · HF: {sourceCounts?.huggingface ?? 0} · MCP: {sourceCounts?.mcp ?? 0} · arXiv: {sourceCounts?.arxiv ?? 0}{sourceCounts?.awesome_lists ? ` · Awesome: ${sourceCounts.awesome_lists}` : ''}{sourceCounts?.hackernews_ai ? ` · HN: ${sourceCounts.hackernews_ai}` : ''} · last crawl {fetchedAt ? relativeTime(fetchedAt) : '—'} ·
        </div>
      </div>
    </header>
  )
}
