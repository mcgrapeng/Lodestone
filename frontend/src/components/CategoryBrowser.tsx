import { useMemo } from 'react'
import { motion } from 'motion/react'
import type { Category, Repo } from '../lib/types'
import { applyFilters, sourceOf, type RepoFilters, type SourceKind } from '../lib/filters'
import { categoryAccent, stripEmoji } from '../lib/format'
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

// ponytail: 单分类视图 — 替代旧版 19 个 CategorySection 线性铺开（200+ 卡片、
// 数千像素滚动）。chip 导航 + 单分类内容，同屏只渲染 ≤30 张卡。
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
      <div className="mx-auto max-w-7xl">
        {/* 分类 chip 导航 — 视觉审查修正：吸顶（滚动浏览时随时可切分类）+ 双侧渐隐 */}
        <div
          className="-mx-6 sticky top-[158px] z-20 mb-4 overflow-x-auto border-b border-border-muted/60 bg-background/90 px-6 py-2.5 backdrop-blur-md mask-fade-x"
          style={{ scrollbarWidth: 'thin' }}
        >
          <div className="flex gap-1.5">
            {categories.map((c) => {
              const on = c.id === currentId
              const accent = categoryAccent(c.id)
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={`shrink-0 rounded-full px-3 py-1.5 text-xs transition-colors ${
                    on
                      ? 'font-medium text-white ring-1'
                      : 'text-foreground-subtle hover:bg-background-subtle hover:text-white'
                  }`}
                  style={
                    on
                      ? {
                          background: `linear-gradient(90deg, ${accent.from}22, ${accent.to}22)`,
                          // ring 颜色跟随分类 accent
                          ['--tw-ring-color' as string]: `${accent.from}66`,
                        }
                      : undefined
                  }
                >
                  {stripEmoji(c.name)}
                  <span className="ml-1.5 text-[10px] text-foreground-subtle">
                    {c.count}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {cat && (
          <>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                {/* 视觉审查修正：background-clip 渐变文字在部分渲染下不可见（整块空白）—
                    改用 accent 实色 + 底部渐变短横线，保视觉归属且永不丢文字 */}
                <h2
                  className="text-xl font-semibold tracking-tight"
                  style={{ color: categoryAccent(cat.id).from }}
                >
                  {cat.name}
                </h2>
                <div
                  className="mt-1.5 h-0.5 w-16 rounded-full"
                  style={{
                    background: `linear-gradient(90deg, ${categoryAccent(cat.id).from}, ${categoryAccent(cat.id).to})`,
                  }}
                />
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
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
    </section>
  )
}
