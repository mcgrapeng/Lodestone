// ponytail: right-side slide-in drawer for LLM settings.
// Mirrors RepoDrawer's open/close animation pattern. All 3 providers' fields
// stay in state so switching doesn't wipe typed values.

import { useEffect, useState } from 'react'
import { X, Check, AlertCircle, Sparkles, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import type { LlmStatus, Settings, TestLlmResult } from '../lib/types'

interface Props {
  open: boolean
  initial: Settings | null  // null = no saved settings
  onClose: () => void
  onSaved: (s: Settings) => void
}

const DEFAULT_SETTINGS: Settings = {
  provider: 'openai',
  anthropic: { api_key: '', model: 'claude-3-5-haiku-latest' },
  openai: { base_url: 'https://api.openai.com/v1', api_key: '', model: 'gpt-4o-mini' },
  ollama: { host: 'http://127.0.0.1:11434', model: 'llama3.1' },
  min_stars: 50,
}

export function SettingsDrawer({ open, initial, onClose, onSaved }: Props) {
  const [draft, setDraft] = useState<Settings>(initial ?? DEFAULT_SETTINGS)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestLlmResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  // ponytail: 2026-09 P3 — 5 桶生成手动触发相关 state。
  // configured=false 时按钮禁用 + 显示「请先配置 Provider」;
  // running 时轮询 /api/llm/status 看 current/total 进度 + 何时结束。
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [triggerError, setTriggerError] = useState<string | null>(null)

  // Sync draft when initial loads (e.g. async after open)
  useEffect(() => {
    if (initial) setDraft(initial)
  }, [initial])

  // ESC closes
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // ponytail: 2026-09 P3 — drawer 打开时拉一次 LLM status。
  // 用户保存 settings 后也重拉;triggerSummarize 后轮询到 running=false 为止。
  useEffect(() => {
    if (!open) return
    let cancelled = false
    const poll = async () => {
      try {
        const s = await api.getLlmStatus()
        if (!cancelled) setLlmStatus(s)
        return s
      } catch {
        return null
      }
    }
    poll()
    return () => { cancelled = true }
  }, [open, draft.provider])  // re-poll after provider change

  // ponytail: triggerSummarize 后每 2s 轮询直到 running=false,
  // 让用户在 drawer 里看到实时进度(显示「正在跑」spinner → 「完成 N/总数 张」)
  useEffect(() => {
    if (!triggering) return
    const t = setInterval(async () => {
      try {
        const s = await api.getLlmStatus()
        setLlmStatus(s)
        if (!s.running) {
          setTriggering(false)
          setTriggerError(null)
        }
      } catch {
        setTriggering(false)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [triggering])

  if (!open) return null

  const updateProvider = (p: Settings['provider']) => {
    setDraft({ ...draft, provider: p })
    setTestResult(null)
  }

  const updateField = (group: keyof Settings, field: string, value: string | number) => {
    setDraft({ ...draft, [group]: { ...(draft[group] as object), [field]: value } })
    setTestResult(null)
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.testLlm(draft.provider, draft[draft.provider] as unknown as Record<string, unknown>)
      setTestResult(result)
    } catch (e) {
      setTestResult({ ok: false, error: (e as Error).message })
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const res = await api.saveSettings(draft)
      if (!res.ok) {
        setSaveError(res.error ?? '保存失败')
        return
      }
      onSaved(draft)
      onClose()
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  // ponytail: 2026-09 P3 — 手动触发 5 桶生成。
  // 前端先看 llmStatus.configured:未配 → 提示去填字段;已配 → POST 触发 + 进入轮询。
  const triggerSummarize = async () => {
    setTriggerError(null)
    // ponytail: 前端兜底。后端也会返 400,但前端检查能少一次 round-trip + 给出明确文案。
    if (!llmStatus?.configured) {
      setTriggerError('请先配置 Provider 的 API Key / Base URL / Model,然后点「保存」')
      return
    }
    setTriggering(true)
    try {
      const res = await api.triggerSummarize()
      if (!res.ok) {
        setTriggerError(res.error ?? '触发失败')
        setTriggering(false)
      }
      // 成功 → triggering=true,useEffect 开始轮询,直到 running=false
    } catch (e) {
      setTriggerError((e as Error).message)
      setTriggering(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />
      {/* Drawer */}
      <aside className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-border-muted bg-background shadow-2xl transition-transform">
        <header className="flex items-center justify-between border-b border-border-muted px-5 py-3">
          <h2 className="text-lg font-semibold text-foreground">LLM 设置</h2>
          <button
            onClick={onClose}
            aria-label="关闭设置"
            className="rounded p-1 text-foreground-subtle hover:bg-background-muted"
          >
            <X size={18} />
          </button>
        </header>

        <div className="space-y-4 overflow-y-auto p-5" style={{ maxHeight: 'calc(100vh - 130px)' }}>
          <p className="text-xs text-foreground-subtle">
            用于手动触发每张卡的「5 桶介绍」生成（是什么 / 能干什么 / 解决什么问题 / 同类项目 / 何时选它）。
            配置完成后点下面「生成 5 桶分析」按钮 — 后端跑批,不占宿主 LLM 上下文,结果写回数据库。
            设置存于 <code>data/settings.json</code>（不入 git）。
          </p>

          {/* Provider selector */}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-foreground">Provider</span>
            <select
              value={draft.provider}
              onChange={(e) => updateProvider(e.target.value as Settings['provider'])}
              className="w-full rounded border border-border-muted bg-background-muted px-3 py-2 text-sm"
            >
              <option value="anthropic">Anthropic Claude</option>
              <option value="openai">OpenAI 兼容（OpenAI / Groq / Together / Ollama OpenAI 模式）</option>
              <option value="ollama">Ollama 本地</option>
            </select>
          </label>

          {/* Dynamic fields */}
          {draft.provider === 'anthropic' && (
            <div className="space-y-3">
              <FieldRow
                label="API Key"
                type="password"
                value={draft.anthropic.api_key}
                onChange={(v) => updateField('anthropic', 'api_key', v)}
                placeholder="sk-ant-..."
              />
              <FieldRow
                label="Model"
                value={draft.anthropic.model}
                onChange={(v) => updateField('anthropic', 'model', v)}
              />
            </div>
          )}

          {draft.provider === 'openai' && (
            <div className="space-y-3">
              <FieldRow
                label="Base URL"
                value={draft.openai.base_url}
                onChange={(v) => updateField('openai', 'base_url', v)}
                placeholder="https://api.openai.com/v1"
              />
              <FieldRow
                label="API Key"
                type="password"
                value={draft.openai.api_key}
                onChange={(v) => updateField('openai', 'api_key', v)}
                placeholder="sk-..."
              />
              <FieldRow
                label="Model"
                value={draft.openai.model}
                onChange={(v) => updateField('openai', 'model', v)}
              />
            </div>
          )}

          {draft.provider === 'ollama' && (
            <div className="space-y-3">
              <FieldRow
                label="Host"
                value={draft.ollama.host}
                onChange={(v) => updateField('ollama', 'host', v)}
                placeholder="http://127.0.0.1:11434"
              />
              <FieldRow
                label="Model"
                value={draft.ollama.model}
                onChange={(v) => updateField('ollama', 'model', v)}
                placeholder="llama3.1"
              />
            </div>
          )}

          <FieldRow
            label="最小分析星数（stars < 此值跳过 LLM）"
            type="number"
            value={String(draft.min_stars)}
            onChange={(v) => setDraft({ ...draft, min_stars: Number(v) || 0 })}
          />

          {/* Test result inline */}
          {testResult && (
            <div
              className={`flex items-start gap-2 rounded p-2 text-xs ${
                testResult.ok
                  ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                  : 'border border-red-500/30 bg-red-500/10 text-red-400'
              }`}
            >
              {testResult.ok ? <Check size={14} /> : <AlertCircle size={14} />}
              <span>
                {testResult.ok
                  ? `✓ 模型响应正常${testResult.model ? `（${testResult.model}）` : ''}`
                  : `✗ ${testResult.error ?? '未知错误'}`}
              </span>
            </div>
          )}

          {saveError && (
            <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
              ✗ {saveError}
            </div>
          )}

          {/* ponytail: 2026-09 P3 — 5 桶生成触发区。配置好了才能跑,完成后显示上次结果。 */}
          <div className="mt-4 rounded-lg border border-border-muted bg-background-muted/30 p-3">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles size={14} className="text-primary" />
              <span className="text-sm font-medium text-foreground">5 桶介绍生成</span>
              {llmStatus?.running && (
                <Loader2 size={14} className="animate-spin text-primary" />
              )}
            </div>

            {/* ponytail: 2026-09 — 实时进度条。running 时显示 current/total 进度条;done 或未跑时显示上次结果摘要。 */}
            {llmStatus?.running ? (
              <div className="mb-2">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-foreground-subtle">
                    正在分析 {llmStatus.current ?? 0}/{llmStatus.total ?? '?'} 张
                    {llmStatus.analyzed_running != null && (
                      <span className="ml-1 text-primary">· 成功 {llmStatus.analyzed_running}</span>
                    )}
                  </span>
                  <span className="font-mono text-foreground-subtle">
                    {llmStatus.total && llmStatus.current != null
                      ? `${Math.round(100 * llmStatus.current / llmStatus.total)}%`
                      : '启动中…'}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-primary/15">
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                    style={{
                      width: llmStatus.total && llmStatus.current != null
                        ? `${Math.min(100, Math.max(0, 100 * llmStatus.current / llmStatus.total))}%`
                        : '25%',
                    }}
                  />
                </div>
              </div>
            ) : llmStatus?.last_run ? (
              <p className="mb-2 text-xs text-foreground-subtle">
                上次生成: {llmStatus.last_analyzed ?? 0}/{llmStatus.last_total ?? '?'} 张
                {llmStatus.last_duration_s ? ` · ${llmStatus.last_duration_s}s` : ''}
                {llmStatus.last_model ? ` · ${llmStatus.last_model}` : ''}
                {' · '}
                <span className="font-mono">{llmStatus.last_run.slice(0, 19).replace('T', ' ')}</span>
              </p>
            ) : null}

            <button
              onClick={triggerSummarize}
              disabled={triggering || !llmStatus?.configured || llmStatus?.running}
              title={
                !llmStatus?.configured
                  ? '请先填好下方 Provider 字段并点「保存」'
                  : llmStatus?.running
                  ? '正在生成中…完成前不可点击'
                  : '用配置的 LLM 对所有 repos 跑一遍 5 桶分析'
              }
              className="w-full rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {llmStatus?.running
                ? `生成中… ${llmStatus.current ?? 0}/${llmStatus.total ?? '?'}`
                : triggering
                ? '已触发,等待后端启动…'
                : '生成 5 桶分析'}
            </button>

            {!llmStatus?.configured && (
              <p className="mt-1.5 text-xs text-foreground-subtle">
                💡 先填上方 Provider 字段并「保存」,按钮才会亮起
              </p>
            )}

            {triggerError && (
              <div className="mt-2 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
                ✗ {triggerError}
              </div>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <footer className="absolute bottom-0 left-0 right-0 flex gap-2 border-t border-border-muted bg-background px-5 py-3">
          <button
            onClick={testConnection}
            disabled={testing || saving}
            className="flex-1 rounded border border-border-muted bg-background-muted px-3 py-2 text-sm font-medium text-foreground hover:bg-background disabled:opacity-50"
          >
            {testing ? '测试中…' : '测试连通'}
          </button>
          <button
            onClick={save}
            disabled={testing || saving}
            className="flex-1 rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? '保存中…' : '保存'}
          </button>
        </footer>
      </aside>
    </>
  )
}

function FieldRow({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: 'text' | 'password' | 'number'
  placeholder?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-foreground-subtle">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded border border-border-muted bg-background-muted px-3 py-1.5 text-sm text-foreground placeholder:text-foreground-subtle focus:border-primary focus:outline-none"
      />
    </label>
  )
}