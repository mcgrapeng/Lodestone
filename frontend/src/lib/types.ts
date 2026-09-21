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
  // ponytail: 2026-09 P3 — /api/data 后端为每个 repo 算 per-CLI 装态,前端 PlatformDot 4 个 dot 各取一个。
  // 老数据没有这 4 个字段时(全 undefined),前端用 Boolean() 转 false,与之前硬编码 installed={false} 行为一致。
  local_installed_claude?: boolean
  local_installed_codex?: boolean
  local_installed_opencode?: boolean
  local_installed_easycode?: boolean
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

export interface ProviderAnthropic {
  api_key: string
  model: string
}
export interface ProviderOpenAI {
  base_url: string
  api_key: string
  model: string
}
export interface ProviderOllama {
  host: string
  model: string
}
export interface Settings {
  provider: 'anthropic' | 'openai' | 'ollama'
  anthropic: ProviderAnthropic
  openai: ProviderOpenAI
  ollama: ProviderOllama
  min_stars: number
  updated_at?: string
}
export interface TestLlmResult {
  ok: boolean
  model?: string
  error?: string
}

// ponytail: 2026-09 — LLM status 类型与 /api/llm/status 一致;Settings 抽屉进度条轮询用。
export type LlmStatus = {
  configured: boolean
  provider: string | null
  running: boolean
  current: number | null        // 已分析数(跑批中)
  total: number | null          // 总数(跑批中)
  analyzed_running: number | null  // 跑批中成功数
  started_at: string | null
  last_run: string | null
  last_analyzed: number | null
  last_total: number | null
  last_duration_s: number | null
  last_source: 'pg' | 'json' | null
  last_model: string | null
  updated_at: string | null
}

// ponytail: 2026-09 — crawl progress 类型与 /api/crawl/progress 一致;banner 轮询用。
export type CrawlProgress = {
  running: boolean
  phase: string | null
  label: string | null
  current: number | null
  total: number | null
  pct: number | null
  eta: string | null
  pid: number | null
  started_at: number | null
  elapsed_s: number | null
  log_mtime: number | null
  last_lines: string[]
}

// ponytail: 2026-09 — 本机 tab 数据类型,与 /api/local 返回一致。
// skill 项的 source=origin/skillmd/none/cache,upgradable=true 时 UI 高亮。
export type LocalSkill = {
  claude?: boolean
  codex?: boolean
  opencode?: boolean
  easycode?: boolean
  url?: string
  desc_zh?: string
  desc_en?: string
  topics?: string[]
  stars?: number
  source?: string
  origin_full?: string
  pushed_at?: string
  upgradable?: boolean
  upgrade_reason?: string
  local_sha?: string | null
  remote_sha?: string | null
}

export type LocalPlugin = {
  name: string
  marketplace: string
  version: string
  install_path: string
  url?: string
  desc_zh?: string
  desc_en?: string
  enabled: boolean
}

export type LocalData = {
  skills: Record<string, LocalSkill>
  commands: Record<string, { claude?: boolean; path?: string; url?: string; desc_zh?: string; desc_en?: string }>
  agents: Record<string, { claude?: boolean; path?: string; url?: string; desc_zh?: string; desc_en?: string }>
  plugins: LocalPlugin[]
  clis: Record<string, string[] | Record<string, { path: string; version: string }>>
  mcp_servers: string[]
  upgradable?: Record<string, { upgradable: boolean; reason: string; local_sha?: string | null; remote_sha?: string | null; url?: string }>
  // ponytail: 2026-09 — /api/local 新增 cache_state 字段,前端 banner 用
  cache_state?: {
    exists: boolean
    mtime: number | null
    age_s: number | null
    total: number
    computing: boolean
    last_trigger_at: string | null
  }
  counts: {
    skills: number
    commands: number
    agents: number
    plugins: number
    clis: number
    mcp_servers: number
    upgradable?: number
  }
  total: number
}

// ponytail: 2026-09 — /api/local/refresh/status 类型
export type RefreshStatus = {
  computing: boolean
  started_at?: string | null
  updated_at?: string | null
  error?: string | null
  // ponytail: 进度上报(compute_upgradable progress_callback 写入)
  current?: number
  total?: number
  current_name?: string
  cache?: {
    exists: boolean
    mtime: number | null
    age_s: number | null
    total: number
    computing: boolean
    last_trigger_at: string | null
  }
}

// ponytail: 2026-09 — install 进度状态(/api/install/status 轮询用)。
// 镜像 LlmStatus 结构。running=true 时 current/total 持续增长;false 后 6s 内显示结果。
export type InstallStatus = {
  running: boolean
  current: number | null
  total: number | null
  label: string | null
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string | null
}

// ponytail: 2026-09 — 升级单条结果(/api/upgrade 同步返回)。
export type UpgradeResult = {
  ok: boolean
  name: string
  status: string  // upgraded / fetch_failed / no_origin / cache_missing / invalid / locked
  detail?: string
  links?: Record<string, { status: string; detail?: string; link?: string }>
}

// ponytail: 2026-09 — 批量升级结果(/api/upgrade-all 启动后由前端轮询 install_status,
// 终态由 UpgradeProgressBanner 自身根据 status 拼装)。
export type UpgradeAllResult = {
  ok: boolean
  started?: boolean
  skipped?: boolean
  total?: number
  message?: string
  error?: string
}

// ponytail: 兼容旧名
export type crawlProgress = CrawlProgress
