import { useEffect, useMemo, useState } from 'react'
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
import { api } from '../lib/api'

export interface CategoryBrowserProps {
  categories: Category[]
  selected: string | null
  onSelect: (id: string) => void
  filters: RepoFilters
  onFiltersChange: (patch: Partial<RepoFilters>) => void
  onOpen: (repo: Repo) => void
  // ponytail: 2026-09 — 批量装/卸完成后通知父级刷新数据(可空,仅当上层挂了回调才调)。
  onRefresh?: () => void
}

type BatchTarget = 'claude' | 'codex' | 'opencode' | 'easycode'

// ponytail: 2026-09 UI 重构 — 分类导航从横向滚动 chip 条(26 类挤一条,滚动条丑)
// 改为左侧固定侧边栏(≥lg 全分类可见,appica monochrome token)+ 窄屏 Select 折叠。
export function CategoryBrowser({
  categories,
  selected,
  onSelect,
  filters,
  onFiltersChange,
  onOpen,
  onRefresh,
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

  // ponytail: 2026-09 — 批量装/卸工具栏状态。
  // busy 用 `install-${target}` / `uninstall-${target}` 字符串让按钮在 UI 区分当前跑的是哪一类,
  // progress 由轮询 /api/install/status 拿到。brief 原本写 s.computing/s.current_index,
  // 但后端 write_install_status 实际写的是 running/current/total,这里用真实字段。
  const [batchTarget, setBatchTarget] = useState<BatchTarget>('claude')
  const [batchBusy, setBatchBusy] = useState<string | null>(null)
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(null)

  useEffect(() => {
    if (!batchBusy) return
    const interval = setInterval(async () => {
      const s = await api.getInstallStatus()
      if (!s.running) {
        clearInterval(interval)
        setBatchBusy(null)
        setBatchProgress(null)
        onRefresh?.()
      } else {
        setBatchProgress({ current: s.current ?? 0, total: s.total ?? 0 })
      }
    }, 1500)
    return () => clearInterval(interval)
  }, [batchBusy, onRefresh])

  async function batchInstall() {
    if (!cat) return
    setBatchBusy(`install-${batchTarget}`)
    try {
      await api.installCategory(cat.id, batchTarget)
    } finally {
      // ponytail: 保持 busy 直到 polling 捕获 running=false,避免按钮闪回 ready 又被卡死。
    }
  }

  async function batchUninstall() {
    if (!cat) return
    setBatchBusy(`uninstall-${batchTarget}`)
    try {
      await api.uninstallCategory(cat.id, batchTarget)
    } finally {
      // 同上
    }
  }

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

              {/* ponytail: 2026-09 — 一键全装/全卸工具栏。
                  target 选 CLI,busy 时禁用并显示进度 current/total。 */}
              <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border-muted bg-background-muted/40 p-2 text-xs">
                <span className="text-foreground-subtle">批量目标:</span>
                <select
                  value={batchTarget}
                  onChange={(e) => setBatchTarget(e.target.value as BatchTarget)}
                  disabled={!!batchBusy}
                  className="rounded bg-background px-2 py-1 ring-1 ring-border-muted"
                >
                  <option value="claude">Claude Code</option>
                  <option value="codex">Codex</option>
                  <option value="opencode">OpenCode</option>
                  <option value="easycode">EasyCode</option>
                </select>
                <button
                  type="button"
                  onClick={batchInstall}
                  disabled={!!batchBusy}
                  className="rounded bg-primary/20 px-3 py-1 text-primary ring-1 ring-primary/40 hover:bg-primary/30 disabled:opacity-50"
                >
                  {batchBusy?.startsWith('install') && batchProgress
                    ? `装 ${batchProgress.current}/${batchProgress.total}`
                    : '全装到该类'}
                </button>
                <button
                  type="button"
                  onClick={batchUninstall}
                  disabled={!!batchBusy}
                  className="rounded bg-error/15 px-3 py-1 text-error ring-1 ring-error/40 hover:bg-error/25 disabled:opacity-50"
                >
                  {batchBusy?.startsWith('uninstall') ? '卸中…' : '全卸该类'}
                </button>
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
