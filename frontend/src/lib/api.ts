// ponytail: typed thin wrapper over fetch. All endpoints hit radar.py serve (proxied
// by Vite at /api/*). Errors surface as thrown exceptions so callers can `try/catch`.

import type {
  CrawlProgress,
  GainPage,
  LlmStatus,
  Snapshot,
  Stats,
  Settings,
  TestLlmResult,
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
  async triggerSummarize(): Promise<{ ok: boolean; error?: string; provider?: string; message?: string }> {
    return post('/api/llm/summarize', {})
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
}
