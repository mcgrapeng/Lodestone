import { Flame, LayoutGrid, BarChart3, Search, TrendingUp, Package } from 'lucide-react'

export type TabId = 'hot' | 'trending' | 'cats' | 'stats' | 'local' | 'search'

export interface TabNavProps {
  active: TabId
  onChange: (tab: TabId) => void
  searchActive: boolean   // q 非空时展示「搜索结果」入口
  searchCount?: number
  /** 本机 tab 上 upgradable 数量(用于角标)。null/0 不显示。 */
  upgradableBadge?: number
}

const TABS: Array<{ id: TabId; label: string; icon: typeof Flame }> = [
  { id: 'hot', label: '热门', icon: Flame },
  { id: 'trending', label: '趋势', icon: TrendingUp },
  { id: 'cats', label: '分类', icon: LayoutGrid },
  { id: 'local', label: '本机', icon: Package },
  { id: 'stats', label: '统计', icon: BarChart3 },
]

// ponytail: 纯 tab 行（无自身定位）— 外层 App 把它和 SearchBar 放进同一个
// sticky 容器。样式复用 app.css 的 nav-tab / nav-tab-active（Appica 设计语言）。
export function TabNav({ active, onChange, searchActive, searchCount, upgradableBadge }: TabNavProps) {
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
            {/* ponytail: 2026-09 — 角标一致性。
                - search tab: 总是显示匹配数(有数字就该显示,即使 0 也不显式 0 徽章)
                - local tab: 升 N 徽章**仅在用户不在本机 tab 时显示**。在 tab 时
                  概览卡已经显示"本机已装 N 项能力",tab 标签再显示一次冗余且
                  占空间。同时 search 角标在 search tab 激活时仍显示,本机 tab
                  激活时不应显示 — 同样的"已激活 tab 不显示次要指标"原则。 */}
            {id === 'local' && !on && upgradableBadge != null && upgradableBadge > 0 && (
              <span className="chip ml-0.5 bg-amber-500/20 text-[10px] text-amber-400">
                ↑{upgradableBadge}
              </span>
            )}
            {id === 'search' && !on && searchCount != null && searchCount > 0 && (
              <span className="chip ml-0.5 text-[10px] text-foreground-subtle">
                {searchCount}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
