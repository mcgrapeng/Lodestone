// ponytail: typed thin wrapper over fetch. All endpoints hit radar.py serve (proxied
// by Vite at /api/*). Errors surface as thrown exceptions so callers can `try/catch`.

import type {
  GainPage,
  Snapshot,
  Stats,
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
}
