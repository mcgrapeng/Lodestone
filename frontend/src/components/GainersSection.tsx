import { useEffect, useState } from 'react'
import { Rocket, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import type { GainPage, Repo } from '../lib/types'
import { RepoCard } from './RepoCard'
import { Skeleton } from './Skeleton'

export interface GainersSectionProps {
  onOpen: (repo: Repo) => void
}

// ponytail: 搜索已统一到「搜索结果」tab — 本组件不再只对当前页做局部过滤
// （旧版 query 只过滤当前 50 条分页，跨页结果会被漏掉的隐性 bug 随之消灭）。
export function GainersSection({ onOpen }: GainersSectionProps) {
  const [data, setData] = useState<GainPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  async function load(p: number) {
    setLoading(true)
    setError(null)
    try {
      const res = await api.getGain(50, p, 12)
      setData(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  const gainers = data?.gainers ?? []

  if (loading && !data) {
    return (
      <section className="px-6 py-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-4 flex items-center gap-2.5">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-success/15 ring-1 ring-white/5">
              <Rocket className="h-4 w-4 text-success" />
            </div>
            <h2 className="text-lg font-semibold tracking-tight text-white">24h 星增 Top</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="card-surface p-4">
                <Skeleton className="mb-2 h-4 w-2/3" />
                <Skeleton className="mb-1 h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            ))}
          </div>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="px-6 py-8">
        <div className="mx-auto max-w-7xl">
          <div className="card-surface p-6 text-sm text-error">
            加载 /api/gain 失败:{error}
          </div>
        </div>
      </section>
    )
  }

  if (!data || data.gainers.length === 0) {
    return (
      <section className="px-6 py-8">
        <div className="mx-auto max-w-7xl">
          <div className="card-surface flex items-center gap-3 p-6 text-sm text-foreground-subtle">
            <Rocket className="h-4 w-4 text-foreground-subtle" />
            还没有 24h 星增数据。多日连续 crawl 后会累积 — 首次启动请先跑一次{' '}
            <code className="rounded bg-background-muted px-1.5 py-0.5 text-[12px] text-primary">
              radar.py crawl
            </code>
            。
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="px-6 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-4 flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-success/15 ring-1 ring-white/5">
            <Rocket className="h-4 w-4 text-success" />
          </div>
          <h2 className="text-lg font-semibold tracking-tight text-white">
            24h 星增 Top {page}/{data.pages}
          </h2>
          <span className="chip ml-1">{data.total}</span>
          <button
            type="button"
            onClick={() => load(page)}
            className="ml-auto chip cursor-pointer transition-colors hover:bg-background-strong"
            disabled={loading}
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        {gainers.length === 0 ? (
          <div className="card-surface p-6 text-sm text-foreground-subtle">
            本页没有数据。
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {gainers.map((repo) => (
              <RepoCard key={repo.name} repo={repo} onOpen={onOpen} variant="grid" />
            ))}
          </div>
        )}

        {data.pages > 1 && (
          <div className="mt-5 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="chip cursor-pointer transition-colors hover:bg-background-strong disabled:opacity-30"
            >
              <ChevronLeft className="h-3 w-3" /> 上一页
            </button>
            <span className="text-xs text-foreground-subtle">
              {page} / {data.pages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="chip cursor-pointer transition-colors hover:bg-background-strong disabled:opacity-30"
            >
              下一页 <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
