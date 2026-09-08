import { useMemo } from 'react'
import { motion } from 'motion/react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@appica/ui-react'
import type { Category, Repo } from '../lib/types'
import { applyFilters, sourceOf, type RepoFilters, type SourceKind } from '../lib/filters'
import { stripEmoji } from '../lib/format'
import { RepoCard } from './RepoCard'
import { FilterBar } from './FilterBar'

export interface CategoryBrowserProps {
  categories: Category[]
  selected: string | null
  onSelect: (id: string) => void
  filters: RepoFilters
  onFiltersChange: (patch: Partial<RepoFilters>) => void
  onOpen: (repo: Repo) => void
}

// ponytail: 2026-09 UI 重构 — 分类导航从横向滚动 chip 条(26 类挤一条,滚动条丑)
// 改为左侧固定侧边栏(≥lg 全分类可见,appica monochrome token)+ 窄屏 Select 折叠。
export function CategoryBrowser({
  categories,
  selected,
  onSelect,
  filters,
  onFiltersChange,
  onOpen,
}: CategoryBrowserProps) {
  const currentId =
    selected && categories.some((c) => c.id === selected) ? selected : categories[0]?.id ?? null
  const cat = categories.find((c) => c.id === currentId) ?? null

  const repos = useMemo(
    () => (cat ? applyFilters(cat.repos, filters) : []),
    [cat, filters],
  )

  // 该分类数据里实际出现的来源 — 空来源不展示按钮
  const availableSources = useMemo(() => {
    if (!cat) return []
    const seen = new Set<SourceKind>()
    for (const r of cat.repos) seen.add(sourceOf(r))
    return [...seen].sort()
  }, [cat])

  if (!categories.length) return null

  return (
    <section className="px-6 py-6">
      <div className="mx-auto flex max-w-7xl gap-6">
        {/* ≥lg:左侧分类栏 — 全部分类可见,无横向滚动 */}
        <aside className="hidden w-56 shrink-0 lg:block">
          <nav
            className="sticky top-[140px] flex max-h-[calc(100vh-160px)] flex-col gap-0.5 overflow-y-auto pr-1"
            aria-label="分类导航"
          >
            {categories.map((c) => {
              const on = c.id === currentId
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => onSelect(c.id)}
                  aria-current={on ? 'true' : undefined}
                  className={[
                    'flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-[13px] transition-colors',
                    on
                      ? 'bg-primary/15 font-medium text-foreground ring-1 ring-primary/40'
                      : 'text-foreground-subtle hover:bg-background-subtle hover:text-foreground',
                  ].join(' ')}
                >
                  <span className="truncate">{stripEmoji(c.name)}</span>
                  <span
                    className={
                      on
                        ? 'shrink-0 text-[11px] font-medium text-primary'
                        : 'shrink-0 text-[11px] text-foreground-subtle'
                    }
                  >
                    {c.count}
                  </span>
                </button>
              )
            })}
          </nav>
        </aside>

        {/* 内容区 */}
        <div className="min-w-0 flex-1">
          {/* <lg:侧栏折叠为 Select 下拉(替代横向滚动 chip 条) */}
          <div className="mb-4 lg:hidden">
            <Select value={currentId ?? ''} onValueChange={(v) => v && onSelect(String(v))}>
              <SelectTrigger className="w-full" aria-label="选择分类">
                <SelectValue placeholder="选择分类" />
              </SelectTrigger>
              <SelectContent>
                {categories.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {stripEmoji(c.name)} · {c.count}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {cat && (
            <>
              <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                <div>
                  {/* 2026-09 UI 回归 — 分类标题从彩色 accent 改 token 主色 */}
                  <h2 className="text-xl font-semibold tracking-tight text-foreground">
                    {cat.name}
                  </h2>
                  <div className="mt-1.5 h-0.5 w-16 rounded-full bg-primary" />
                  {cat.desc && (
                    <p className="mt-1 text-sm text-foreground-subtle">{cat.desc}</p>
                  )}
                </div>
                <span className="chip">
                  {repos.length} / {cat.repos.length} repos
                </span>
              </div>

              <FilterBar
                filters={filters}
                onChange={onFiltersChange}
                availableSources={availableSources}
              />

              {repos.length === 0 ? (
                <div className="card-surface p-6 text-sm text-foreground-subtle">
                  当前筛选下没有仓库 — 试试切换来源或清空筛选。
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {repos.map((repo, i) => (
                    <motion.div
                      key={repo.name}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: Math.min(i * 0.02, 0.3) }}
                    >
                      <RepoCard repo={repo} onOpen={onOpen} />
                    </motion.div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  )
}
