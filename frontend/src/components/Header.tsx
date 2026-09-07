import { Github, RefreshCw, Zap, Loader2 } from 'lucide-react'
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
  totalRepos: number
  totalCategories: number
  sourceSummary?: string
}

export function Header({
  fetchedAt,
  refreshing,
  onRefresh,
  totalRepos,
  totalCategories,
  sourceSummary,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border-muted bg-background/85 backdrop-blur-md">
      {/* 品牌色 hairline — 顶栏与内容之间的精致分割 */}
      <div className="h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-primary to-secondary shadow-lg shadow-brand-500/30">
            <Zap className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight">
              <span className="gradient-text">Lodestone</span>
            </div>
            <div className="text-[11px] text-foreground-subtle">
              GitHub 热门 AI · Skills · Plugins
            </div>
          </div>
        </div>

        <div className="ml-auto hidden items-center gap-4 text-xs text-foreground-subtle sm:flex">
          <div className="flex items-center gap-1.5">
            <Github className="h-3.5 w-3.5" />
            <span>{sourceSummary || `${totalRepos.toLocaleString()} 个仓库`}</span>
            <span className="text-foreground-subtle">·</span>
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
    </header>
  )
}
