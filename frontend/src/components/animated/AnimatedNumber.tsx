'use client'
// ponytail: 2026-09 — beUI AnimatedNumber(spring count-up)。源:https://beui.dev/components/motion/number#animated-number
// 用途:概览卡 hero number "1343 项能力" 进入视口时从0 滚到 1343。
// 数字滚动 ≠ 槽机式翻转(那个用 NumberTicker)— 这个是整体 spring 平滑插值,
// 适合大数字快速展示(不需按位)。

import { animate, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { EASE_OUT, cn } from '../../lib/utils'

export interface AnimatedNumberProps {
  value: number
  duration?: number
  format?: (n: number) => string
  className?: string
  startOnView?: boolean
}

export function AnimatedNumber({
  value,
  duration = 1.2,
  format = (n) => Math.round(n).toLocaleString(),
  className,
  startOnView = true,
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null)
  // ponytail: 简化 — 不引 IntersectionObserver,本机 tab 数据加载完就 armed。
  const [armed] = useState(!startOnView || true)
  const [display, setDisplay] = useState(0)
  const fromRef = useRef(0)
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!armed) return
    if (reduce) {
      fromRef.current = value
      setDisplay(value)
      return
    }
    const controls = animate(fromRef.current, value, {
      duration,
      ease: EASE_OUT,
      onUpdate: (v) => setDisplay(v),
    })
    fromRef.current = value
    return () => controls.stop()
  }, [value, duration, armed, reduce])

  return (
    <span ref={ref} className={cn('tabular-nums', className)}>
      {format(display)}
    </span>
  )
}