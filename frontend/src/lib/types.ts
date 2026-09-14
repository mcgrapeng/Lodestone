// ponytail: shape mirrors radar.py `_json` payloads + db queries. Kept narrow
// — extra fields on the server are ignored.

export interface Repo {
  name: string                  // "owner/repo"
  url: string                   // "https://github.com/owner/repo"
  desc?: string
  desc_zh?: string
  summary_zh?: string
  stars?: number
  forks?: number
  lang?: string
  topics?: string[]
  updated?: string
  pushed?: string
  stars_today?: number | null
  score?: number
  source?: string               // "github_trending" | "github_search" | "hf_spaces" | ...
  is_ai_relevant?: boolean
  best_category?: string | null
  local_installed?: boolean
  trending?: boolean
  is_fresh?: boolean
  facts?: string
  is_skill?: boolean                  // 2026-09 — 仓库根是否有 SKILL.md / skill.md / SKILL.yaml
  summary_sections?: {                // 2026-09 — README 拆分 / 同 topic 匹配 / 翻译的中文 5 桶详介
    intro?: string                    //   【是什么】一句话定位(从 README ## What is 段)
    can_do?: string                   //   【能干什么】3-5 个具体能力(从 ## Features 段)
    problem?: string                  //   【解决什么问题】用户痛点(从 ## Why / Motivation 段)
    competitive?: string             //   【同类竞品】3-4 个同 topic 仓库名(逗号分隔)
    when_to_use?: string              //   【何时选它】决策建议(从 README ## When to use 段)
  }
  analysis_5d?: {                     // 2026-09 — LLM 5 桶决策分析（无 key 时为 null）
    what?: string                     //   【是什么】一句话定位
    can_do?: string                   //   【能干什么】3-5 个具体能力
    problem?: string                  //   【解决什么】用户痛点
    alternatives?: Array<{            //   【同类竞品】每个含名字 + 优点 + 缺点
      name: string
      pros: string
      cons: string
    }>
    when_to_use?: string              //   【何时选它】决策建议
  }
}

export interface Category {
  id: string
  name: string                  // "🤖 AI Agent & Skills"
  desc?: string
  count: number
  repos: Repo[]
}

export interface Snapshot {
  hot_now: Repo[]
  categories: Category[]
  fetched_at: string | null
  stars_today?: Record<string, number | null>   // JSON 模式：trending 仓库的 24h 星增
  trending?: Repo[]                             // 今日上榜完整列表（按 stars_today 排序）
}

export interface Stats {
  by_lang: Record<string, { count: number; stars: number }>
  by_topic: Record<string, number>
  total_repos: number
  total_stars: number
  note?: string
}

export interface GainPage {
  gainers: Repo[]
  page: number
  size: number
  pages: number
  total: number
  range?: string         // "24h" | "7d"
  note?: string | null
}

export interface ReadmeZh {
  ok: boolean
  repo: string
  text?: string
  source_url?: string
  fetched_at?: string
  translator?: string
  from_cache?: boolean
  fallback?: string
  error?: string
}
