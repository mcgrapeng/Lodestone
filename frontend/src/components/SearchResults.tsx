import { useMemo } from 'react'
import { motion } from 'motion/react'
import { Search } from 'lucide-react'
import type { Repo, Snapshot } from '../lib/types'
import { applyFilters, sourceOf, type RepoFilters, type SourceKind } from '../lib/filters'
import { RepoCard } from './RepoCard'
import { FilterBar } from './FilterBar'

export interface SearchResultsProps {
  snapshot: Snapshot
  filters: RepoFilters
  onFiltersChange: (patch: Partial<RepoFilters>) => void
  onOpen: (repo: Repo) => void
}

// ponytail: 全局统一搜索视图 — hot_now + 全部分类去重后一起筛。
// 替代旧版「每个 section 各自过滤」（GainersSection 只过滤当前页的隐性 bug 也一并消灭：
// 搜索语义现在只发生在这里，跨页数据全覆盖）。
export function SearchResults({ snapshot, filters, onFiltersChange, onOpen }: SearchResultsProps) {
  // 全量仓库池（去重）— useMemo，输入不变不重算
  const pool = useMemo(() => {
    const seen = new Set<string>()
    const all: Repo[] = []
    for (const r of snapshot.hot_now) {
      if (!seen.has(r.name)) { seen.add(r.name); all.push(r) }
    }
    for (const c of snapshot.categories) {
      for (const r of c.repos) {
        if (!seen.has(r.name)) { seen.add(r.name); all.push(r) }
      }
    }
    return all
  }, [snapshot])

  const results = useMemo(() => applyFilters(pool, filters), [pool, filters])

  const availableSources = useMemo(() => {
    const seen = new Set<SourceKind>()
    for (const r of pool) seen.add(sourceOf(r))
    return [...seen].sort()
  }, [pool])

  return (
    <section className="px-6 py-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2.5 text-lg font-semibold tracking-tight text-white">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 ring-1 ring-white/5">
                <Search className="h-4 w-4 text-primary" />
              </span>
              「{filters.query}」的搜索结果
            </h2>
            <p className="mt-1 text-sm text-foreground-subtle">
              全库 {pool.length} 个仓库中命中 {results.length} 个 · 名称 / 中文描述 / topic
            </p>
          </div>
          <span className="chip-accent">{results.length}</span>
        </div>

        <FilterBar
          filters={filters}
          onChange={onFiltersChange}
          availableSources={availableSources}
        />

        {results.length === 0 ? (
          <div className="card-surface p-6 text-sm text-foreground-subtle">
            没有匹配「{filters.query}」的仓库 — 换个关键词，或清空来源筛选。
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((repo, i) => (
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
        )}
      </div>
    </section>
  )
}
