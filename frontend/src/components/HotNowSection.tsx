import { Zap } from 'lucide-react'
import { motion } from 'motion/react'
import type { Repo } from '../lib/types'
import { RepoCard } from './RepoCard'

export interface HotNowSectionProps {
  repos: Repo[]
  onOpen: (repo: Repo) => void
}

// ponytail: 全网最热网格 — hot_now（按 ⭐ 排序的 Top 池）铺开成网格，
// 与 Trending 专区（今日星增视角）分开：这里看存量热度，那里看今日动量。
export function HotNowSection({ repos, onOpen }: HotNowSectionProps) {
  if (repos.length === 0) return null
  return (
    <section className="px-6 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-secondary/15 ring-1 ring-white/5">
            <Zap className="h-4 w-4 text-secondary" />
          </div>
          <h2 className="text-lg font-semibold tracking-tight text-white">全网最热</h2>
          <span className="chip ml-1">{repos.length}</span>
          <p className="ml-auto text-xs text-foreground-subtle">按 ⭐ 星标排序 · 存量热度榜</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {repos.map((repo, i) => (
            <motion.div
              key={repo.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: Math.min(i * 0.015, 0.4) }}
            >
              <RepoCard repo={repo} onOpen={onOpen} />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
