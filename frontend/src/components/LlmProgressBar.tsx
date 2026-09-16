import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Progress, BorderBeam, Button } from '@appica/ui-react'
import { CheckCircle2, Sparkles, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { LlmStatus } from '../lib/types'

// ponytail: 2026-09 — 5 桶分析进度条。
// 设计目标:
//   1. running 时实时进度(current/total/%/成功数)
//   2. 完成时 6s 显示 ✅「X 张 · 耗时 Ns · model」summary,然后滑出
//   3. 失败时显示 ✗ 与后端 error
//   4. 用 Appica UI 的 <Progress> + <BorderBeam> 组合出「炫酷」效果(已有依赖,
//      不造轮子);用 framer-motion 做 enter/exit 动画,跟 CrawlProgress 同套。

const COMPLETE_HOLD_MS = 6_000

function fmtDuration(s: number | null): string {
  if (s == null || s <= 0) return ''
  if (s < 60) return `${s.toFixed(0)}s`
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m${sec.toString().padStart(2, '0')}s`
}

export function LlmProgressBar({ status }: { status: LlmStatus | null }) {
  const running = status?.running ?? false
  const lastRun = status?.last_run ?? null
  const error = (status as { error?: string } | null)?.error
  // ponytail: 2026-09 — /api/llm/cancel 写 error="cancelled by user"。区分:
  // 正常完成 / 真实错误 / 用户取消 — 前端用不同文案 + 图标。
  const cancelled = error === 'cancelled by user'

  // 内部状态:刚完成 / 刚失败。running→false 切换时锁定 6s 显示结果。
  const [justFinished, setJustFinished] = useState(false)
  const [justFailed, setJustFailed] = useState<string | null>(null)
  const lastRunning = useRef(running)

  useEffect(() => {
    if (running) {
      setJustFinished(false)
      setJustFailed(null)
    } else if (lastRunning.current) {
      // 跑完状态由 lastRun + error 判定:取消 → 失败态,真错误 → 失败态,正常 → 完成态
      if (cancelled) {
        setJustFailed('已取消(用户主动停止)')
      } else if (error) {
        setJustFailed(error)
      } else if (lastRun) {
        setJustFinished(true)
      } else {
        setJustFailed('生成被中断或失败,请重试')
      }
    }
    lastRunning.current = running
  }, [running, lastRun, error, cancelled])

  // 完成后 6s 自动滑出
  useEffect(() => {
    if (!justFinished && !justFailed) return
    const t = setTimeout(() => {
      setJustFinished(false)
      setJustFailed(null)
    }, COMPLETE_HOLD_MS)
    return () => clearTimeout(t)
  }, [justFinished, justFailed])

  // 完全没在跑也没刚跑完 → 不渲染。避免空 card 占位。
  if (!running && !justFinished && !justFailed) return null

  // 计算百分比。running 但没收到 first 写盘 current/total 都 null → indeterminate。
  const hasBar = status?.current != null && status?.total != null && status.total > 0
  const pct = hasBar
    ? Math.min(100, Math.max(0, (status!.current! / status!.total!) * 100))
    : null
  const indeterminate = running && !hasBar

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={
          running
            ? 'running'
            : justFailed
              ? 'failed'
              : 'done'
        }
        initial={{ opacity: 0, y: -4, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.98 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className={`relative mb-3 overflow-hidden rounded-lg border bg-background-muted/40 p-3 ${
          running
            ? 'border-primary/40'
            : justFailed
              ? 'border-error/40'
              : 'border-emerald-500/40'
        }`}
      >
        {/* ponytail: 2026-09 — BorderBeam 仅在 running 时渲染,流动光带绕 border 转。
            Appica UI 的 speed prop(默认 5s/lap)替代先前误用的 duration prop。 */}
        {running && (
          <BorderBeam
            color="var(--primary)"
            length={30}
            thickness={1.5}
            speed={6}
            className="pointer-events-none"
          />
        )}

        <div className="flex items-center gap-2">
          {running ? (
            <Sparkles size={14} className="animate-pulse text-primary" />
          ) : justFailed ? (
            <XCircle size={14} className="text-error" />
          ) : (
            <CheckCircle2 size={14} className="text-emerald-500" />
          )}
          <span className="text-xs font-medium text-foreground">
            {running
              ? '正在生成 5 桶介绍'
              : justFailed
                ? cancelled ? '已取消' : '生成失败'
                : '5 桶分析已完成'}
          </span>
          {running && hasBar && (
            <span className="ml-auto font-mono text-xs text-foreground-subtle">
              {status!.current}/{status!.total}
              {' · '}
              {Math.round(pct!)}%
            </span>
          )}
          {running && !hasBar && (
            <span className="ml-auto font-mono text-xs text-foreground-subtle">启动中…</span>
          )}
          {!running && justFinished && status?.last_duration_s != null && (
            <span className="ml-auto font-mono text-xs text-emerald-500">
              耗时 {fmtDuration(status.last_duration_s)}
            </span>
          )}
          {/* ponytail: 2026-09 — running 时显示取消按钮,跟进度数字同一行 ml-auto 之前。 */}
          {running && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => api.cancelSummarize()}
              className="ml-2 h-7 px-2 text-xs text-foreground-subtle hover:text-error"
            >
              <XCircle size={12} className="mr-1" />
              取消
            </Button>
          )}
        </div>

        <div className="mt-2">
          {/* ponytail: Appica UI 的 <Progress variant="bar"> 自带宽度过渡动画,
              indeterminate 状态传 value=null 自动进入循环动画态。 */}
          <Progress
            variant="bar"
            thickness={6}
            value={indeterminate ? null : (pct ?? 100)}
            indicatorColor={
              running
                ? 'var(--primary)'
                : justFailed
                  ? 'var(--error)'
                  : 'var(--success-emphasis, #10b981)'
            }
          />
        </div>

        <div className="mt-1.5 flex items-center justify-between text-[11px] text-foreground-subtle">
          <span>
            {running && hasBar && (
              <>
                已分析 <span className="font-mono text-foreground">{status!.current}</span> /{' '}
                <span className="font-mono">{status!.total}</span>
                {' · '}
                成功{' '}
                <span className="font-mono text-primary">
                  {status!.analyzed_running ?? status!.current ?? 0}
                </span>
              </>
            )}
            {running && !hasBar && '后端正在准备第一批…'}
            {!running && justFinished && status && (
              <>
                生成{' '}
                <span className="font-mono text-foreground">
                  {status.last_analyzed ?? 0}
                </span>
                {' / '}
                <span className="font-mono">{status.last_total ?? '?'}</span> 张
                {status.last_model && (
                  <>
                    {' · '}
                    <span className="font-mono text-primary">{status.last_model}</span>
                  </>
                )}
                {status.last_run && (
                  <>
                    {' · '}
                    <span className="font-mono">
                      {status.last_run.slice(0, 19).replace('T', ' ')}
                    </span>
                  </>
                )}
              </>
            )}
            {!running && justFailed && justFailed}
          </span>
          {running && hasBar && status!.analyzed_running != null && (
            <span className="font-mono text-primary">
              {Math.round((status!.analyzed_running / status!.total!) * 100)}% 命中
            </span>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}