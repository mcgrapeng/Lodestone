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
}: HeaderProps) {
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
            <div className="text-[15px] font-semibold tracking-tight text-foreground">
              Lodestone
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

        <button
          onClick={onSettings}
          aria-label="LLM 设置"
          className="relative rounded p-2 text-foreground-subtle hover:bg-background-muted hover:text-foreground"
        >
          <Settings size={16} />
          {settingsStatus === 'configured' && (
            <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-emerald-500" />
          )}
          {settingsStatus === 'untested' && (
            <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-500" />
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
    </header>
  )
}
