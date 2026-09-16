import { useState } from 'react'
import type { CrawlProgress } from '../lib/types'

// ponytail: 2026-09 — 后台爬取进度 banner。固定在搜索栏下,crawl 跑时实时更新。
// 设计:bar + 当前阶段 + ETA + (展开) 最后几行日志 — 不用动画/没用颜色转移,3 个进度数字说清楚。
// 完成后保留 4s 然后滑出,不抢 toast。

function formatElapsed(s: number | null): string {
  if (s == null) return ''
  if (s < 60) return `${s.toFixed(0)}s`
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m${sec.toString().padStart(2, '0')}s`
}

export function CrawlProgress({ progress }: { progress: CrawlProgress }) {
  const [expanded, setExpanded] = useState(true) // ponytail: 默认展开,让用户立即看到日志
  if (!progress.running) return null

  // ponytail: 当前阶段可能有 bar (X/Y) 也可能没有 (README 抓取,没发 per-repo 进度)。
  // 没 bar 时显示 "进行中 · ~Ns" — 别用 0% bar 误导用户以为没动。
  const hasBar = progress.current != null && progress.total != null
  const widthPct = hasBar ? Math.min(100, Math.max(0, progress.pct ?? 0)) : null

  const stepLabel = progress.label ?? '进行中'
  const phaseLabel = progress.phase ?? 'Crawl'

  return (
    <div className="border-b border-primary/40 bg-primary/10 backdrop-blur">
      <div className="mx-auto max-w-7xl px-6 py-2.5">
        <div className="flex items-center gap-3 text-sm">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" />
          <span className="font-medium text-foreground">{phaseLabel}</span>
          <span className="font-mono text-primary">{stepLabel}</span>
          {hasBar ? (
            <span className="font-mono text-xs text-foreground-subtle">
              {progress.current}/{progress.total}
            </span>
          ) : (
            <span className="font-mono text-xs text-primary">· · ·</span>
          )}
          <span className="ml-auto font-mono text-xs text-foreground-subtle">
            {hasBar ? `${widthPct!.toFixed(0)}%` : '—'}
            {progress.eta && <> · {progress.eta.replace(/[()]/g, '')}</>}
            {progress.elapsed_s != null && <> · {formatElapsed(progress.elapsed_s)}</>}
          </span>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="rounded border border-primary/40 bg-background-muted px-2.5 py-0.5 text-xs text-foreground hover:bg-primary/20"
            title={expanded ? '收起日志' : '展开日志'}
          >
            {expanded ? '收起' : '日志'}
          </button>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-primary/15">
          {hasBar ? (
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
              style={{ width: `${widthPct}%` }}
            />
          ) : (
            // ponytail: 无 bar 时显示静态条 + 脉冲,告诉用户「在跑但未到下一个里程碑」。
            // 不用自定义 keyframe(避免 tailwind 配置),只复用 animate-pulse。
            <div className="h-full w-1/4 animate-pulse rounded-full bg-primary/60" />
          )}
        </div>
        {expanded && progress.last_lines.length > 0 && (
          <pre className="mt-2 max-h-48 overflow-auto rounded border border-primary/20 bg-background p-2.5 font-mono text-[11px] leading-snug text-foreground-muted">
            {progress.last_lines.join('\n')}
          </pre>
        )}
      </div>
    </div>
  )
}
