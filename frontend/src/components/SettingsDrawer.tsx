// ponytail: right-side slide-in drawer for LLM settings.
// Mirrors RepoDrawer's open/close animation pattern. All 3 providers' fields
// stay in state so switching doesn't wipe typed values.

import { useEffect, useState } from 'react'
import { X, Check, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { Settings, TestLlmResult } from '../lib/types'

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
            用于 crawl 时自动生成每张卡的「5 桶介绍」（是什么 / 能干什么 / 解决什么问题 / 同类项目 / 何时选它）。
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