// ponytail: typed thin wrapper over fetch. All endpoints hit radar.py serve (proxied
// by Vite at /api/*). Errors surface as thrown exceptions so callers can `try/catch`.

import type {
  CrawlProgress,
  GainPage,
  InstallStatus,
  LlmStatus,
  LocalData,
  RefreshStatus,
  Settings,
  Snapshot,
  Stats,
  TestLlmResult,
  UpgradeAllResult,
  UpgradeResult,
} from './types'

const BASE = ''  // same-origin via Vite proxy

async function jsonOrThrow<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body?.error) msg = body.error
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return (await r.json()) as T
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return jsonOrThrow<T>(
    await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

// ponytail: /api/data 的 ETag 协商缓存 — 服务端 304 时直接用上次的结果，
// 30s 轮询不再反复传输 ~600KB。Cache-Control: no-store 阻止浏览器自动缓存，
// 所以 If-None-Match 由这里手动携带。
let _dataEtag: string | null = null
let _dataCache: Snapshot | null = null

export const api = {
  async getSnapshot(): Promise<Snapshot> {
    const headers: HeadersInit = _dataEtag ? { 'If-None-Match': _dataEtag } : {}
    const r = await fetch(`${BASE}/api/data`, { headers })
    if (r.status === 304 && _dataCache) return _dataCache
    const snap = await jsonOrThrow<Snapshot>(r)
    const etag = r.headers.get('ETag')
    if (etag) {
      _dataEtag = etag
      _dataCache = snap
    }
    return snap
  },

  async getStats(): Promise<Stats> {
    return jsonOrThrow(await fetch(`${BASE}/api/stats`))
  },

  async getGain(minDelta = 50, page = 1, size = 24): Promise<GainPage> {
    return jsonOrThrow(
      await fetch(
        `${BASE}/api/gain?min_delta=${minDelta}&page=${page}&size=${size}`,
      ),
    )
  },

  // ponytail: skill 安装/更新/卸载闭环 — 2026-09 取代旧的按需 README 翻译。
  // 安装与更新共用 /api/install（update 带 force_update → git fast-forward）。
  async installSkill(
    name: string,
    url: string,
    targets: string[],
  ): Promise<{ ok: boolean; message: string; error?: string }> {
    return post('/api/install', { name, url, targets })
  },

  async updateSkill(
    name: string,
    url: string,
    targets: string[],
  ): Promise<{ ok: boolean; message: string; error?: string }> {
    return post('/api/update', { name, url, targets })
  },

  async uninstallSkill(
    name: string,
  ): Promise<{ ok: boolean; message: string; error?: string }> {
    return post('/api/uninstall', { name })
  },

  // ponytail: 2026-09 P2 — per-platform install/uninstall. Card surfaces
  // 4 dots (Claude/Codex/OpenCode/EasyCode); click hits /api/install_to_target
  // for a single CLI instead of prompting in a drawer.
  async installToTarget(
    name: string,
    url: string,
    target: 'claude' | 'codex' | 'opencode' | 'easycode',
  ): Promise<InstallStatus> {
    return post<InstallStatus>('/api/install_to_target', { name, url, target })
  },

  async uninstallFromTarget(
    name: string,
    target: 'claude' | 'codex' | 'opencode' | 'easycode',
  ): Promise<InstallStatus> {
    return post<InstallStatus>('/api/uninstall_from_target', { name, target })
  },

  async triggerCrawl(): Promise<{ ok: boolean; pid?: number; error?: string }> {
    const r = await fetch(`${BASE}/api/crawl`, { method: 'POST' })
    if (!r.ok) {
      try {
        const body = await r.json()
        return { ok: false, error: body?.error ?? `${r.status}` }
      } catch {
        return { ok: false, error: `${r.status}` }
      }
    }
    return jsonOrThrow(r)
  },

  async getSettings(): Promise<Settings | null> {
    const r = await fetch(`${BASE}/api/settings`)
    if (!r.ok) throw new Error(`getSettings ${r.status}`)
    const body = await r.json()
    return body.settings ?? null
  },

  async saveSettings(s: Settings): Promise<{ ok: boolean; error?: string }> {
    return post('/api/settings', s)
  },

  async testLlm(
    provider: Settings['provider'],
    fields: Record<string, unknown>,
  ): Promise<TestLlmResult> {
    return post('/api/llm/test', { provider, [provider]: fields })
  },

  // ponytail: 2026-09 P3 — 5 桶生成手动触发。前端 Settings 抽屉按钮调此端点,
  // 后端 spawn `radar.py summarize` 后台跑,立即返 200。进度走 /api/llm/status 轮询。
  async triggerSummarize(): Promise<{ ok: boolean; error?: string; provider?: string; message?: string; pid?: number }> {
    return post('/api/llm/summarize', {})
  },

  // ponytail: 2026-09 — 取消正在跑的 5 桶生成。后端 killpg + 等 3s 软退出 +
  // 必要时 SIGKILL,最后写 running=False + error="cancelled by user"。
  async cancelSummarize(): Promise<{ ok: boolean; cancelled?: boolean; error?: string; pid?: number }> {
    return post('/api/llm/cancel', {})
  },

  async getLlmStatus(): Promise<LlmStatus> {
    return jsonOrThrow<LlmStatus>(await fetch(`${BASE}/api/llm/status`))
  },

  // ponytail: 2026-09 — 前端爬取进度条轮询。返回 last_lines + 当前 phase + bar 状态。
  // 失败不抛(进度条非关键 UI),返回兜底。
  async getCrawlProgress(): Promise<CrawlProgress> {
    try {
      return await jsonOrThrow<CrawlProgress>(await fetch(`${BASE}/api/crawl/progress`))
    } catch {
      return { running: false, phase: null, label: null, current: null, total: null, pct: null, eta: null, pid: null, started_at: null, elapsed_s: null, log_mtime: null, last_lines: [] }
    }
  },

  // ponytail: 2026-09 — 本机 tab 核心 API。
  // /api/local: 整库 inventory + 每项 status(up_toable / behind / cache_missing 等)。
  // /api/upgrade?name=X: 同步升级单个 skill(快路径,后端 ls-remote 限流 ~5s)。
  // /api/upgrade-all: 后台 fork 子进程异步跑批量升级,前端转去轮询 install/status。
  async getLocal(): Promise<LocalData> {
    return jsonOrThrow<LocalData>(await fetch(`${BASE}/api/local`))
  },

  async upgradeSkill(name: string): Promise<UpgradeResult> {
    return post(`/api/upgrade?name=${encodeURIComponent(name)}`, {})
  },

  async upgradeAll(): Promise<UpgradeAllResult> {
    return post('/api/upgrade-all', {})
  },

  async getInstallStatus(): Promise<InstallStatus> {
    return jsonOrThrow<InstallStatus>(await fetch(`${BASE}/api/install/status`))
  },

  // ponytail: 2026-09 — 一键全装/全卸分类下所有 skill 到指定 CLI。
  // 后端走 /api/install_category / /api/uninstall_category,异步跑批,前端轮询
  // /api/install/status 看进度(computing=false 即收尾)。
  async installCategory(
    categoryId: string,
    target: 'claude' | 'codex' | 'opencode' | 'easycode',
    except?: string[],
  ): Promise<{ ok: boolean; job_id?: string; error?: string }> {
    return post('/api/install_category', { category_id: categoryId, target, except })
  },

  async uninstallCategory(
    categoryId: string,
    target: 'claude' | 'codex' | 'opencode' | 'easycode',
    except?: string[],
  ): Promise<{ ok: boolean; job_id?: string; error?: string }> {
    return post('/api/uninstall_category', { category_id: categoryId, target, except })
  },

  // ponytail: 2026-09 — 手动触发 upgradable 重算 + 轮询状态。
  // 首次进本机 tab / 看到 0 项可升级时点「立即重算」按钮调。
  async triggerRefresh(): Promise<{ ok: boolean; started?: boolean; already_running?: boolean; error?: string }> {
    return post('/api/local/refresh', {})
  },
  async getRefreshStatus(): Promise<RefreshStatus> {
    return jsonOrThrow<RefreshStatus>(await fetch(`${BASE}/api/local/refresh/status`))
  },
}
