import { Flame, LayoutGrid, BarChart3, Search, TrendingUp } from 'lucide-react'

export type TabId = 'hot' | 'trending' | 'cats' | 'stats' | 'search'

export interface TabNavProps {
  active: TabId
  onChange: (tab: TabId) => void
  searchActive: boolean   // q 非空时展示「搜索结果」入口
  searchCount?: number
}

const TABS: Array<{ id: TabId; label: string; icon: typeof Flame }> = [
  { id: 'hot', label: '热门', icon: Flame },
  { id: 'trending', label: '趋势', icon: TrendingUp },
  { id: 'cats', label: '分类', icon: LayoutGrid },
  { id: 'stats', label: '统计', icon: BarChart3 },
]

// ponytail: 纯 tab 行（无自身定位）— 外层 App 把它和 SearchBar 放进同一个
// sticky 容器。样式复用 app.css 的 nav-tab / nav-tab-active（Appica 设计语言）。
export function TabNav({ active, onChange, searchActive, searchCount }: TabNavProps) {
  const items = searchActive
    ? [...TABS, { id: 'search' as TabId, label: '搜索结果', icon: Search }]
    : TABS

  return (
    <div role="tablist" aria-label="视图切换" className="flex items-center gap-1.5 overflow-x-auto">
      {items.map(({ id, label, icon: Icon }) => {
        const on = active === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(id)}
            className={`nav-tab ${on ? 'nav-tab-active' : ''}`}
          >
            <Icon className={`h-3.5 w-3.5 ${on ? 'text-primary' : ''}`} />
            {label}
            {id === 'search' && searchCount != null && (
              <span className={`chip ml-0.5 text-[10px] ${on ? 'bg-primary/20 text-primary' : ''}`}>
                {searchCount}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
