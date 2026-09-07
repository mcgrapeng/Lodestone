import { Search, X } from 'lucide-react'

export interface SearchBarProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  totalMatched?: number
}

export function SearchBar({
  value,
  onChange,
  placeholder = '搜索仓库 / 中文描述 / topic …',
  totalMatched,
}: SearchBarProps) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-border-muted bg-background-subtle py-2 pl-9 pr-14 text-sm text-white placeholder-neutral-500 outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
      />
      {/* 快捷键提示 — 聚焦后隐藏 */}
      {!value && (
        <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-white/10 bg-background-muted px-1.5 py-0.5 font-mono text-[10px] text-foreground-subtle">
          /
        </kbd>
      )}
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-foreground-subtle transition hover:bg-background-strong hover:text-white"
          aria-label="清空"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
      {value && totalMatched != null && (
        <span className="absolute -bottom-5 left-1 text-[10px] text-foreground-subtle">
          匹配 {totalMatched} 个仓库
        </span>
      )}
    </div>
  )
}
