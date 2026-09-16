import { useMemo } from 'react'
import { TrendingUp, Sparkles, Globe2, Cpu } from 'lucide-react'
import type { Snapshot, Stats } from '../lib/types'
import { formatStars } from '../lib/format'

export interface HeroStatsProps {
  snapshot: Snapshot
  stats: Stats | null
}

export function HeroStats({ snapshot, stats }: HeroStatsProps) {
  // 视觉审查修正：顶栏与统计卡数字统一口径（hot_now + 分类去重），
  // 「今日上榜」从 stars_today 取（JSON 模式下 hot_now 不带 trending flag）
  const dedupRepos = useMemo(() => {
    const seen = new Set<string>()
    let n = 0
    for (const r of snapshot.hot_now) { if (!seen.has(r.name)) { seen.add(r.name); n++ } }
    for (const c of snapshot.categories) {
      for (const r of c.repos) { if (!seen.has(r.name)) { seen.add(r.name); n++ } }
    }
    return n
  }, [snapshot])
  const totalRepos = stats?.total_repos ?? dedupRepos
  const totalStars = stats?.total_stars
    ?? snapshot.hot_now.reduce((s, r) => s + (r.stars ?? 0), 0)
  const trendingCount = Object.keys(snapshot.stars_today ?? {}).length
    || snapshot.hot_now.filter((r) => r.trending).length
  const skillsCount = snapshot.categories
    .filter((c) => /Skills|Plugins|MCP|Servers/i.test(c.name))
    .reduce((s, c) => s + c.repos.length, 0)
  const languagesCount = stats ? Object.keys(stats.by_lang).length : 0
  const topicsCount = stats ? Object.keys(stats.by_topic).length : 0

  const tiles = [
    { icon: Sparkles, label: '收录仓库', value: totalRepos.toLocaleString(), sub: `累计 Star ${formatStars(totalStars)}` },
    { icon: TrendingUp, label: '今日上榜', value: trendingCount.toString(), sub: trendingCount ? '24h 星增动量' : '暂无新上榜' },
    { icon: Cpu, label: 'Skills · Plugins', value: skillsCount.toLocaleString(), sub: '可一键安装' },
    { icon: Globe2, label: '语言 · 主题', value: languagesCount.toLocaleString(), sub: `主题 ${topicsCount || '—'} 个` },
  ]

  return (
    <section aria-label="仪表盘概览" className="px-6 pt-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5">
          {/* ponytail: 2026-09 — 顶层 H1 移到 Header(每页都有),这里改 h2 + 描述。 */}
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            仪表盘
            <span className="ml-3 align-middle text-sm font-normal text-foreground-subtle">
              主流 AI 开源项目 · Skills · Plugins · 论文，{snapshot.categories.length} 个分类
            </span>
          </h2>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map(({ icon: Icon, label, value, sub }) => (
            <div
              key={label}
              className="card-surface group relative overflow-hidden p-4 transition-colors hover:border-primary/25"
            >
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/40 to-transparent" />
              {/* 角落柔光 — hover 时亮起 */}
              <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/10 blur-2xl transition-opacity duration-300 group-hover:bg-primary/20" />
              <div className="relative">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-primary/25 to-secondary/15 ring-1 ring-white/5">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-3 text-[11px] tracking-wider text-foreground-subtle">
                  {label}
                </div>
                <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-white">
                  {value}
                </div>
                <div className="mt-0.5 text-[11px] text-foreground-subtle">{sub}</div>
              </div>
            </div>
          ))}
        </div>
        {/* 视觉审查修正：删除徽章行（与统计卡三层重复）— 总星标并入首卡 sub */}
      </div>
    </section>
  )
}
