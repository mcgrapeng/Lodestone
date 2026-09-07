import { Flame, Sparkles } from 'lucide-react'
import { motion } from 'motion/react'
import type { Repo } from '../lib/types'
import { RepoCard } from './RepoCard'
import { formatStars } from '../lib/format'

export interface TrendingRailProps {
  repos: Repo[]
  onOpen: (repo: Repo) => void
}

// ponytail: 搜索已统一到「搜索结果」tab — 本组件不再自带过滤。
export function TrendingRail({ repos, onOpen }: TrendingRailProps) {
  if (repos.length === 0) return null

  return (
    <section className="px-6 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-warning/15 ring-1 ring-white/5">
            <Flame className="h-4 w-4 text-warning" />
          </div>
          <h2 className="text-lg font-semibold tracking-tight text-white">
            GitHub 今日 Trending
          </h2>
          <span className="chip-accent ml-1">
            <Sparkles className="h-3 w-3" />
            {repos.length}
          </span>
          <p className="ml-auto text-xs text-foreground-subtle">
            来自 GitHub Trending · 24h 星增 {formatStars(
              repos.reduce((s, r) => s + (r.stars_today ?? 0), 0),
            )}
          </p>
        </div>

        {/* 响应式网格铺开（替代横滑单行）— 卡片固定尺寸，所有项目等大 */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {repos.map((repo, i) => (
            <motion.div
              key={repo.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: Math.min(i * 0.03, 0.4) }}
              className="relative"
            >
              {/* 排名徽标 — 前三名品牌色，其余低调灰 */}
              <span
                className={`absolute -left-1.5 -top-1.5 z-10 grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold tabular-nums ring-2 ring-background ${
                  i < 3
                    ? 'bg-gradient-to-br from-primary to-secondary text-white shadow-md shadow-primary/30'
                    : 'bg-background-strong text-foreground-subtle'
                }`}
              >
                {i + 1}
              </span>
              <RepoCard repo={repo} onOpen={onOpen} variant="grid" />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
