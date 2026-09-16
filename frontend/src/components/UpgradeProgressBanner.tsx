import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import { Progress } from '@appica/ui-react'
import type { InstallStatus } from '../lib/types'
import { AnimatedNumber } from './animated/AnimatedNumber'

// ponytail: 2026-09 — 升级进度条(本机 tab 用)。
// - Progress (Appica)替代自写 div 进度条
// - AnimatedNumber (beUI 移植)替代静态 "12/47" 文本,数字平滑滚入
// - 三态切换(running/done/failed)+ framer-motion 进出
// - 完成后 6s 显示 ✅,再滑出
// - 1h stale 兜底(subprocess 崩溃前忘了清 status)

const COMPLETE_HOLD_MS = 6_000
const STALE_RUNNING_MS = 60 * 60 * 1000 // 1h

export function UpgradeProgressBanner({ status }: { status: InstallStatus | null }) {
  const running = status?.running ?? false
  const [justFinished, setJustFinished] = useState(false)
  const lastRunning = useRef(running)

  // ponytail: stale-running 兜底(子进程死前忘了清 status)
  const startedAt = status?.started_at ? new Date(status.started_at).getTime() : 0
  const staleRunning =
    running && startedAt > 0 && Date.now() - startedAt > STALE_RUNNING_MS

  useEffect(() => {
    if (running && !staleRunning) {
      setJustFinished(false)
    } else if (lastRunning.current) {
      setJustFinished(true)
    }
    lastRunning.current = running && !staleRunning
  }, [running, staleRunning])

  useEffect(() => {
    if (!justFinished) return
    const t = setTimeout(() => setJustFinished(false), COMPLETE_HOLD_MS)
    return () => clearTimeout(t)
  }, [justFinished])

  if ((!running && !justFinished) || staleRunning) return null

  const hasBar = status?.current != null && status?.total != null && status.total > 0
  const pct = hasBar ? Math.min(100, Math.max(0, (status!.current! / status!.total!) * 100)) : null
  const errorMsg = (status as { error?: string } | null)?.error
  const isError = !running && !!errorMsg

  const done = justFinished && !isError
  const label = status?.label ?? '升级中'
  const headline = isError
    ? `${label} · 失败`
    : running
      ? `${label}`
      : `${label} · 已完成`

  // ponytail: beUI 风格的 border color 切换 — emerald / primary / error,
  // 直接用 Appica 的 token(已经按主题校准过对比度)
  const borderClass = isError
    ? 'border-error/50'
    : running
      ? 'border-primary/40'
      : 'border-emerald-500/40'

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={isError ? 'error' : running ? 'running' : 'done'}
        initial={{ opacity: 0, y: -4, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.98 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className={`relative mb-3 overflow-hidden rounded-lg border bg-background-muted/40 p-3 ${borderClass}`}
      >
        <div className="flex items-center gap-2">
          {isError ? (
            <AlertCircle size={14} className="text-error" />
          ) : done ? (
            <CheckCircle2 size={14} className="text-emerald-500" />
          ) : (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          )}
          <span className="text-xs font-medium text-foreground">{headline}</span>
          {/* ponytail: beUI AnimatedNumber 替代静态 "12/47" — 数字从 0 平滑
              滚到 current(每次 current 变化都从头滚,显得"活"在动) */}
          {running && hasBar && status && (
            <span className="ml-auto flex items-baseline gap-1 font-mono text-xs text-foreground-subtle">
              <AnimatedNumber
                value={status.current ?? 0}
                format={(n) => Math.round(n).toLocaleString()}
                duration={0.5}
              />
              <span>/</span>
              <AnimatedNumber
                value={status.total ?? 0}
                format={(n) => Math.round(n).toLocaleString()}
                duration={0.5}
              />
              <span className="ml-1 text-foreground-subtle">
                · {Math.round(pct!)}%
              </span>
            </span>
          )}
        </div>
        <div className="mt-2">
          <Progress
            variant="bar"
            thickness={6}
            value={running && !hasBar ? null : isError ? 0 : pct ?? 100}
            indicatorColor={
              isError
                ? 'var(--error)'
                : done
                  ? 'var(--success-emphasis, #10b981)'
                  : 'var(--primary)'
            }
          />
        </div>
        {errorMsg && (
          <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-error">
            <XCircle size={11} className="mt-0.5 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
        {status?.started_at && (
          <div className="mt-1.5 text-[11px] text-foreground-subtle">
            <span className="font-mono">开始 {status.started_at.slice(11, 19)}</span>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

// ponytail: 2026-09 — 升级一行 skill 的内联 progress(本机 tab 单项升级时使用)。
// 区别于 UpgradeProgressBanner:这个用于单条 fetch+reset 期间的 spinner 反馈,
// 时间通常 5-30s,所以用 spinner 而不是 progress bar。
export function SingleUpgradeRow({
  status,
  error,
}: {
  status: 'idle' | 'running' | 'ok' | 'fail'
  error?: string
}) {
  if (status === 'idle') return null
  if (status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-foreground-subtle">
        <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        升级中…
      </span>
    )
  }
  if (status === 'ok') {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-500">
        <CheckCircle2 size={11} />
        已升级
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-error">
      <XCircle size={11} />
      {error || '升级失败'}
    </span>
  )
}