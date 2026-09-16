import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2, AlertCircle, RefreshCw, Sparkles } from 'lucide-react'
import { Button, Progress } from '@appica/ui-react'
import { api } from '../lib/api'

// ponytail: 2026-09 — 取代 292 个"未检查"徽章。
// - cache 算完且有 upgradable → 不显示(状态徽章已准确,再显示冗余)
// - cache 不存在 / total=0 / 过期 → 显示"立即重算" CTA
// - 用户主动重算中 → 显示"重算中"进度
// - 失败 → 显示错误 + 重试
// 优先级 1 的核心:把"全是未检查"的视觉噪声 → 1 个有信息的 banner。

interface Props {
  local: { total: number; cache_state?: {
    exists: boolean
    age_s: number | null
    total: number
    computing: boolean
    last_trigger_at: string | null
  } } | null
  onAfterRefresh?: () => void
}

export function CacheStatusBanner({ local, onAfterRefresh }: Props) {
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshInfo, setRefreshInfo] = useState<{
    computing: boolean
    started_at: string | null
    current: number
    total: number
    current_name: string
  } | null>(null)
  const [tick, setTick] = useState(0)
  // ponytail: 2026-09 — 客户端进度模拟。后端 total=0 时 real work 瞬间完成,前端
  // 看不到任何"在跑"的感觉 — 用户只看到静态 100% bar。解决:用户点 trigger 后,
  // 客户端动画从 0 → 100% 跑 1.5s,与后端 polling 重叠。后端报 real current/total
  // 优先覆盖。这样 idle 状态下也是"在跑",不是"啥都没发生"。
  const [simulatedAt, setSimulatedAt] = useState<number | null>(null)
  // ponytail: 动画刻度。ref 存每次 trigger 开始的 timestamp,requestAnimationFrame
  // 驱动 0 → 100 平滑过渡。trigger 完即停。
  const simStartRef = useRef<number | null>(null)
  const simTickRef = useRef<number | null>(null)

  // ponytail: 2s 轮询 /api/local/refresh/status 看 computing 翻转 + 进度
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await api.getRefreshStatus()
        const wasComputing = refreshInfo?.computing
        setRefreshInfo({
          computing: !!r.computing,
          started_at: r.started_at ?? null,
          current: typeof r.current === 'number' ? r.current : 0,
          total: typeof r.total === 'number' ? r.total : 0,
          current_name: r.current_name ?? '',
        })
        // computing 翻 false 时(用户主动重算完成)— 通知父组件 loadLocal 立刻刷
        if (wasComputing && !r.computing) {
          onAfterRefresh?.()
        }
      } catch {
        // 静默
      }
      setTick((n) => n + 1) // trigger re-render
    }, 2_000)
    return () => clearInterval(id)
  }, [onAfterRefresh, refreshInfo?.computing])

  // ponytail: 组件卸载时清掉 raf(避免 setState on unmounted 警告)
  useEffect(() => () => {
    if (simTickRef.current != null) {
      cancelAnimationFrame(simTickRef.current)
      simTickRef.current = null
    }
    simStartRef.current = null
  }, [])

  async function handleTrigger() {
    setError(null)
    setTriggering(true)
    try {
      const r = await api.triggerRefresh()
      if (!r.ok) {
        setError(r.error ?? '触发失败')
      } else {
        setRefreshInfo({
          computing: true, started_at: new Date().toISOString(),
          current: 0, total: 0, current_name: '',
        })
        // ponytail: 2026-09 — 客户端动画模拟开始。1.5s 内 0→100% 平滑填充,
        // 与后端 2s polling 重叠。trigger 完 1.5s 后 raf 自动停(避免永久渲染)。
        simStartRef.current = performance.now()
        const tick = () => {
          if (!simStartRef.current) return
          const elapsed = (performance.now() - simStartRef.current) / 1000
          if (elapsed > 1.5) {
            simStartRef.current = null
            simTickRef.current = null
            setTick((n) => n + 1)
            return
          }
          // ease-out cubic: 1 - (1-t)^3
          const t = elapsed / 1.5
          setSimulatedAt(t * t * (3 - 2 * t))
          setTick((n) => n + 1)
          simTickRef.current = requestAnimationFrame(tick)
        }
        simTickRef.current = requestAnimationFrame(tick)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setTriggering(false)
    }
  }

  // ponytail: 优先级 — banner 只在"cache 没数据"时显示。cache 有数据 + total>0
  // 表示 daemon 算完且有真结果,行内徽章已准确,不再 banner 重复告知。
  void tick // 触发重渲染(refreshInfo 更新)
  const cs = local?.cache_state

  if (error) {
    return (
      <WrapBanner tone="error">
        <AlertCircle size={14} className="shrink-0 text-error" />
        <div className="flex-1 text-sm text-error">重算失败:{error}</div>
        <Button size="sm" variant="outline" onClick={() => { setError(null); handleTrigger() }} disabled={triggering} className="h-8 px-3 text-xs">
          重试
        </Button>
      </WrapBanner>
    )
  }

  if (refreshInfo?.computing || cs?.computing) {
    const cur = refreshInfo?.current ?? 0
    const tot = refreshInfo?.total ?? 0
    const pct = tot > 0 ? Math.min(100, Math.round(100 * cur / tot)) : 0
    const curName = refreshInfo?.current_name || ''
    // ponytail: 2026-09 — 进度条始终显示(之前 tot=0 时隐藏)。
    // - tot > 0: 标准模式(current/total/%)
    // - tot = 0 + cur = 0: indeterminate 动画(stripes 自动循环,无目标值)
    // - tot = 0 + cur > 0: 100%(刚跑完,bar 满 + 文字 "已检查 0 项可升级")
    return (
      <WrapBanner tone="primary">
        <Loader2 size={14} className="animate-spin text-primary" />
        <div className="flex-1">
          <div className="text-sm font-medium text-foreground">
            正在重算 upgradable 状态{tot > 0 ? ` · ${cur}/${tot} (${pct}%)` : ''}
          </div>
          <div className="mt-0.5 text-[11px] text-foreground-subtle">
            {curName
              ? `正在检查 ${curName}`
              : (local && local.total > 0
                ? `扫描 ${local.total} 个 skill 的 latest SHA · 通常 5–30 秒`
                : '扫描中…')}
          </div>
        </div>
        <div className="hidden h-1.5 w-32 shrink-0 overflow-hidden rounded-full bg-primary/15 sm:block">
          <Progress
            variant="bar"
            thickness={6}
            // ponytail: value=null → indeterminate 动画(stripes 循环),tot=0 时
            // 用这个给视觉反馈。cur > 0 → 已跑完虽然 tot=0 → 100% 满条。
            value={tot > 0 ? Math.min(100, (cur / tot) * 100) : (cur > 0 ? 100 : null)}
            indicatorColor="var(--primary)"
          />
        </div>
      </WrapBanner>
    )
  }

  // cache 完全不存在(serve 刚启动,daemon 还没跑)
  if (!cs?.exists) {
    return (
      <WrapBanner>
        <Sparkles size={14} className="shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-foreground">
            本机 upgradable 状态还没算
          </div>
          <div className="mt-0.5 text-[11px] text-foreground-subtle">
            扫描 {local?.total ?? '?'} 个 skill 的 latest SHA 通常 5–30 秒(受 GitHub 限流)。
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleTrigger}
          disabled={triggering}
          className="h-8 px-3 text-xs"
        >
          {triggering ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />}
          立即重算
        </Button>
      </WrapBanner>
    )
  }

  // cache 存在但 total=0 — 跑完了,确实没可升级的
  const ageS = cs?.age_s ?? 0
  if ((cs?.total ?? 0) === 0) {
    const isJustFilled = ageS < 30
    return (
      <WrapBanner>
        <Sparkles size={14} className="shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-foreground">
            {isJustFilled ? '已检查 0 个可升级的 skill' : `缓存 ${Math.round(ageS / 60)} 分钟前算过,0 项可升级`}
          </div>
          <div className="mt-0.5 text-[11px] text-foreground-subtle">
            已装 skill 多来自其他来源(非 GitHub /api/install 装的),没 origin 记录,无法判断是否有新版。
          </div>
          {/* ponytail: 2026-09 — total=0 也要给视觉进度反馈。
              1. trigger 后 1.5s 内客户端模拟 0→100% 平滑填充(eased)
              2. 完成后停在 100% emerald 条
              3. 之前的 5min+ 缓存:0% 条+ 文案"已 N 分钟前算过"
              没有进度感 → 用户以为啥都没发生。*/}
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-emerald-500/15">
            <div
              className={
                'h-full rounded-full ' +
                (isJustFilled
                  ? simulatedAt != null
                    ? 'bg-emerald-500'
                    : 'bg-emerald-500/60'
                  : 'bg-foreground-muted/30')
              }
              style={{
                width: isJustFilled
                  ? `${(simulatedAt ?? 1) * 100}%`
                  : '0%',
                transition: isJustFilled && simulatedAt != null
                  ? 'none'
                  : 'width 300ms ease-out',
              }}
            />
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleTrigger}
          disabled={triggering}
          className="h-8 px-3 text-xs"
        >
          {triggering ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />}
          重新计算
        </Button>
      </WrapBanner>
    )
  }

  // cache 存在 + 有数据 + age > 5min → 提示已过期(daemon 5min 自动跑,或手动刷)
  if (ageS > 300) {
    return (
      <WrapBanner>
        <RefreshCw size={14} className="shrink-0 text-foreground-subtle" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-foreground">
            缓存已 {Math.round(ageS / 60)} 分钟前算过
          </div>
          <div className="mt-0.5 text-[11px] text-foreground-subtle">
            daemon 每 5 分钟自动跑一次,你也可以手动立即重算。
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleTrigger}
          disabled={triggering}
          className="h-8 px-3 text-xs"
        >
          {triggering ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />}
          立即重算
        </Button>
      </WrapBanner>
    )
  }

  // cache fresh + 有数据 → 不显示 banner(状态徽章已准确,避免冗余)
  return null
}

function WrapBanner({
  children,
  tone = 'default',
}: {
  children: React.ReactNode
  tone?: 'default' | 'primary' | 'error'
}) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        className={
          tone === 'error'
            ? 'mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-error/50 bg-error/10 p-3'
            : tone === 'primary'
              ? 'mb-3 flex items-center gap-3 rounded-lg border border-primary/40 bg-primary/10 p-3'
              : 'mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-foreground-muted/30 bg-background-muted/30 p-3'
        }
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}