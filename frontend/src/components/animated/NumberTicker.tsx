'use client'
// ponytail: 2026-09 — beUI NumberTicker(槽机式数字翻转,带 stagger + 入场动画)。
// 源: https://beui.dev/components/motion/number#number-ticker
// 调整:beUI 用 `motion/react` 命名,本项目 framer-motion 通过 `motion` 重新导出;
//  EASE_OUT 改为本地 ./lib/utils 常量,保持项目内单一来源。
// 用途:本机 tab 总数 "1343" → 数字逐位滚入,升级进度 0/5 → 1/5 槽位滑动。

import { animate, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { EASE_OUT, cn } from '../../lib/utils'

const DIGIT_HEIGHT_EM = 1.1
const DIGITS = Array.from({ length: 10 }, (_, n) => n)

export interface NumberTickerProps {
  value: number
  /** Digits to pad to (left). */
  pad?: number
  /** Per-digit roll duration in seconds. */
  duration?: number
  /** Stagger between digits. */
  stagger?: number
  /** Render only after the element enters the viewport. */
  startOnView?: boolean
  prefix?: string
  suffix?: string
  /** Add a small blur during digit rolls. */
  blur?: boolean
  className?: string
  digitClassName?: string
  /** Insert locale group separators (commas). Server-component safe. */
  locale?: boolean
  /** Custom formatter. Client-only. */
  format?: (value: number) => string
}

export function NumberTicker({
  value,
  pad,
  duration = 0.9,
  stagger = 0.04,
  startOnView = true,
  prefix,
  suffix,
  blur = false,
  className,
  digitClassName,
  locale,
  format,
}: NumberTickerProps) {
  const containerRef = useRef<HTMLSpanElement>(null)
  // ponytail: 不引入 framer-motion 的 useInView(IntersectionObserver 需要 ref + 测量),
  // 简化:用 mount-once + startOnView=true 时永远 armed(数字一进入就滚,适合本机 tab 这种
  // 一次加载完就显示的数据)。
  const [armed, setArmed] = useState(!startOnView)
  useEffect(() => {
    if (startOnView) setArmed(true)
  }, [startOnView])

  const text = useMemo(() => {
    const rounded = Math.round(value)
    const formatted = format
      ? format(rounded)
      : locale
        ? rounded.toLocaleString()
        : rounded.toString()
    return pad ? formatted.padStart(pad, '0') : formatted
  }, [value, pad, format, locale])
  const glyphs = useMemo(() => {
    const chars = text.split('')
    // ponytail: 按位值做 key(从右数 position)。增长的数字左侧新增 glyph 不影响
    // 已经在屏幕上的 ones/tens/hundreds,只滚真正变化的那位。
    return chars.map((char, i) => ({ char, id: `g-${chars.length - 1 - i}` }))
  }, [text])
  const readableText = `${prefix ?? ''}${text}${suffix ?? ''}`

  // ponytail: 入场完成前走 stagger 动画,完成后立即跳(0 延迟)— 否则 live update
  // 会有"故意等"的拖尾感。
  const [entered, setEntered] = useState(false)
  useEffect(() => {
    if (!armed || entered) return
    const total = (duration + glyphs.length * stagger) * 1000
    const t = window.setTimeout(() => setEntered(true), total)
    return () => window.clearTimeout(t)
  }, [armed, entered, duration, stagger, glyphs.length])

  return (
    <span
      ref={containerRef}
      className={cn('inline-flex items-center tabular-nums', className)}
    >
      <span className="sr-only">{readableText}</span>
      <span aria-hidden="true" className="inline-flex items-center">
        {prefix ? <span>{prefix}</span> : null}
        {glyphs.map(({ char, id }, i) => {
          const isDigit = /\d/.test(char)
          if (!isDigit) {
            return (
              <span key={id} className="inline-block">
                {char}
              </span>
            )
          }
          const digit = Number(char)
          return (
            <Digit
              key={id}
              digit={armed ? digit : 0}
              delay={entered ? 0 : i * stagger}
              duration={duration}
              blur={blur}
              className={digitClassName}
            />
          )
        })}
        {suffix ? <span>{suffix}</span> : null}
      </span>
    </span>
  )
}

function Digit({
  digit,
  delay,
  duration,
  blur,
  className,
}: {
  digit: number
  delay: number
  duration: number
  blur: boolean
  className?: string
}) {
  const reduce = useReducedMotion()
  const columnRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (reduce || !blur || !columnRef.current || !Number.isFinite(digit)) {
      return
    }
    const node = columnRef.current
    const controls = animate(
      node,
      { filter: ['blur(10px)', 'blur(0px)'] },
      {
        duration: Math.min(duration * 0.75, 0.32),
        delay,
        ease: EASE_OUT,
      },
    )
    return () => {
      controls.stop()
      node.style.filter = 'blur(0px)'
    }
  }, [blur, delay, digit, duration, reduce])

  return (
    <span
      className={cn('relative inline-block overflow-hidden', className)}
      style={{ height: `${DIGIT_HEIGHT_EM}em`, width: '1ch' }}
    >
      <motion.span
        ref={columnRef}
        initial={{ y: 0 }}
        animate={{ y: `-${digit * DIGIT_HEIGHT_EM}em` }}
        transition={
          reduce ? { duration: 0 } : { duration, delay, ease: EASE_OUT }
        }
        className="absolute inset-x-0 top-0 flex flex-col items-center will-change-[transform,filter]"
      >
        {DIGITS.map((n) => (
          <span
            key={n}
            className="flex h-[1.1em] items-center justify-center leading-none"
          >
            {n}
          </span>
        ))}
      </motion.span>
    </span>
  )
}