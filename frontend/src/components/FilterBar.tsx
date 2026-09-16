import { ArrowUpDown } from 'lucide-react'
import type { RepoFilters, SortKey, SourceKind } from '../lib/filters'
import { SOURCE_LABELS } from '../lib/filters'

export interface FilterBarProps {
  filters: RepoFilters
  onChange: (patch: Partial<RepoFilters>) => void
  /** 数据里实际出现的来源（动态隐藏空来源，如快照里没有 MCP 时） */
  availableSources?: SourceKind[]
}

const SORTS: Array<{ key: SortKey; label: string }> = [
  { key: 'stars', label: '最多 Star' },
  { key: 'recent', label: '最近更新' },
  { key: 'name', label: '名称' },
]

export function FilterBar({ filters, onChange, availableSources }: FilterBarProps) {
  // ponytail: 2026-09 — 包含全部 5 个 SourceKind + all,让 arxiv/other 也能 chip 选中。
  // 旧 fallback 只列 3 个,URL ?src=arxiv 时 FilterBar 不显示对应 chip,用户看不到过滤生效。
  const srcOptions: Array<SourceKind | 'all'> = availableSources?.length
    ? ['all', ...availableSources]
    : ['all', 'github', 'huggingface', 'mcp', 'arxiv', 'other']

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
      <span className="flex items-center gap-1 text-foreground-subtle">
        <ArrowUpDown className="h-3 w-3" /> 排序
      </span>
      {SORTS.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange({ sort: key })}
          className={`chip cursor-pointer transition-colors ${
            filters.sort === key
              ? 'bg-primary/25 font-semibold text-primary ring-1 ring-primary/40'
              : 'hover:bg-background-strong'
          }`}
        >
          {label}
        </button>
      ))}

      <span className="mx-1 h-3 w-px bg-background-strong" />
      <span className="text-foreground-subtle">来源</span>
      {srcOptions.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onChange({ source: s })}
          className={`chip cursor-pointer transition-colors ${
            filters.source === s
              ? 'bg-primary/25 font-semibold text-primary ring-1 ring-primary/40'
              : 'hover:bg-background-strong'
          }`}
        >
          {SOURCE_LABELS[s]}
        </button>
      ))}
    </div>
  )
}
