import { BarChart3, Tag } from 'lucide-react'
import type { Stats } from '../lib/types'
import { formatStars } from '../lib/format'

export interface StatsPanelProps {
  stats: Stats | null
}

export function StatsPanel({ stats }: StatsPanelProps) {
  if (!stats) {
    return (
      <section className="px-6 py-8">
        <div className="mx-auto max-w-7xl">
          <div className="card-surface p-6 text-sm text-foreground-subtle">加载 /api/stats 中…</div>
        </div>
      </section>
    )
  }

  const langs = Object.entries(stats.by_lang)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 12)
  const topics = Object.entries(stats.by_topic).slice(0, 24)
  const maxLang = Math.max(1, ...langs.map(([, v]) => v.count))

  return (
    <section className="px-6 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-4 flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 ring-1 ring-white/5">
            <BarChart3 className="h-4 w-4 text-primary" />
          </div>
          <h2 className="text-lg font-semibold tracking-tight text-white">生态分布</h2>
          <span className="chip ml-1">{stats.total_repos.toLocaleString()} repos</span>
          {stats.note && <span className="chip ml-1 text-warning/80">{stats.note}</span>}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Language distribution */}
          <div className="card-surface p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">🧪 编程语言</h3>
              <span className="text-[11px] text-foreground-subtle">仓库数</span>
            </div>
            <div className="space-y-2">
              {langs.map(([lang, v]) => (
                <div key={lang} className="flex items-center gap-3">
                  <div className="w-20 shrink-0 truncate text-[12px] text-foreground-muted">
                    {lang}
                  </div>
                  <div className="relative h-5 flex-1 overflow-hidden rounded bg-background-muted">
                    <div
                      className="absolute inset-y-0 left-0 rounded bg-gradient-to-r from-primary to-secondary"
                      style={{ width: `${(v.count / maxLang) * 100}%` }}
                    />
                  </div>
                  <div className="w-12 shrink-0 text-right text-[11px] tabular-nums text-foreground-subtle">
                    {v.count}
                  </div>
                  <div className="hidden w-14 shrink-0 text-right text-[10px] tabular-nums text-foreground-subtle sm:block">
                    ⭐ {formatStars(v.stars)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Topic distribution */}
          <div className="card-surface p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">
                <Tag className="mr-1 inline h-3.5 w-3.5 text-primary" />
                热门主题
              </h3>
              <span className="text-[11px] text-foreground-subtle">出现次数</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {topics.map(([t, c]) => {
                const max = Math.max(...topics.map(([, n]) => n))
                const intensity = c / max
                // 三档强度 — 与 chip-accent 同一色彩语言，避免硬编码 rgba
                const tier =
                  intensity > 0.66
                    ? 'bg-primary/25 text-primary ring-primary/30'
                    : intensity > 0.33
                      ? 'bg-primary/15 text-primary/90 ring-primary/20'
                      : 'bg-background-muted text-foreground-muted ring-white/5'
                return (
                  <span key={t} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${tier}`}>
                    {t} <span className="text-foreground-subtle">· {c}</span>
                  </span>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
