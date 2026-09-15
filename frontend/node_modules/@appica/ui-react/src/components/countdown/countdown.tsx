'use client'

import * as React from 'react'
import { LazyMotion, domAnimation, m } from 'motion/react'
import { useReducedMotion } from '../../hooks/use-reduced-motion'
import { cn } from '../../internal/utils'

interface CountdownParts {
  days: number
  hours: number
  minutes: number
  seconds: number
  total: number
  isComplete: boolean
}

const CountdownContext = React.createContext<CountdownParts | null>(null)

const MS = { day: 86_400_000, hour: 3_600_000, minute: 60_000, second: 1_000 } as const

function toTimestamp(value: Date | number | string): number {
  if (value instanceof Date) return value.getTime()
  if (typeof value === 'number') return value
  return new Date(value).getTime()
}

function getParts(total: number): CountdownParts {
  const remaining = Math.max(0, total)
  return {
    days: Math.floor(remaining / MS.day),
    hours: Math.floor(remaining / MS.hour) % 24,
    minutes: Math.floor(remaining / MS.minute) % 60,
    seconds: Math.floor(remaining / MS.second) % 60,
    total: remaining,
    isComplete: remaining <= 0,
  }
}

interface CountdownProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  /** Absolute instant to count down to (a `Date`, epoch-ms, or date string). */
  targetDate?: Date | number | string
  /** Relative length in **seconds** from mount. Ignored when `targetDate` is set. */
  duration?: number
  /**
   * Tick interval in milliseconds.
   * @default 1000
   */
  interval?: number
  /** Fired once when the countdown reaches zero. */
  onComplete?: () => void
  /** Segments and labels, or a render-prop receiving `{ days, hours, minutes, seconds, total, isComplete }`. */
  children?: React.ReactNode | ((parts: CountdownParts) => React.ReactNode)
}

function Countdown({
  targetDate,
  duration,
  interval = 1000,
  onComplete,
  className,
  children,
  ...props
}: CountdownProps) {
  const mountRef = React.useRef<number>(Date.now())

  const target = React.useMemo(() => {
    if (targetDate != null) {
      const ts = toTimestamp(targetDate)
      return Number.isNaN(ts) ? mountRef.current : ts
    }
    if (duration != null) return mountRef.current + duration * 1000
    return mountRef.current
  }, [targetDate, duration])

  const [now, setNow] = React.useState(() => Date.now())

  React.useEffect(() => {
    if (Date.now() >= target) {
      setNow(Date.now())
      return
    }
    let id: ReturnType<typeof setTimeout> | undefined
    const schedule = () => {
      const current = Date.now()
      const delay = interval - (current % interval)
      id = setTimeout(() => {
        const t = Date.now()
        setNow(t)
        if (t < target) schedule()
      }, delay)
    }
    schedule()
    return () => {
      if (id !== undefined) clearTimeout(id)
    }
  }, [target, interval])

  const parts = React.useMemo(() => getParts(target - now), [target, now])

  const completedRef = React.useRef(false)
  React.useEffect(() => {
    if (parts.isComplete && !completedRef.current) {
      completedRef.current = true
      onComplete?.()
    } else if (!parts.isComplete) {
      completedRef.current = false
    }
  }, [parts.isComplete, onComplete])

  return (
    <CountdownContext value={parts}>
      <div data-slot="countdown" role="timer" className={cn('inline-flex items-center', className)} {...props}>
        {typeof children === 'function' ? children(parts) : children}
      </div>
    </CountdownContext>
  )
}

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] as const

const ROLL_TRANSITION = {
  type: 'tween',
  duration: 0.5,
  ease: [0.65, 0, 0.35, 1] satisfies [number, number, number, number],
} as const

function DigitRoller({ digit, reduced }: { digit: number; reduced: boolean }) {
  return (
    <span className="relative inline-block overflow-hidden leading-none">
      <span className="invisible">0</span>
      <m.span
        className="absolute inset-x-0 top-0 flex flex-col items-center"
        initial={false}
        animate={{ y: `${-digit * 10}%` }}
        transition={reduced ? { duration: 0 } : ROLL_TRANSITION}
        suppressHydrationWarning
      >
        {DIGITS.map((d) => (
          <span key={d} className="flex h-[1em] items-center justify-center leading-none">
            {d}
          </span>
        ))}
      </m.span>
    </span>
  )
}

interface CountdownSegmentProps extends Omit<React.ComponentProps<'span'>, 'children'> {
  /** Which unit to read from the parent `Countdown`. */
  unit?: 'days' | 'hours' | 'minutes' | 'seconds'
  /** Render this number directly instead of reading context (standalone display). */
  value?: number
  /**
   * Minimum digit count; the value is zero-padded to this width.
   * @default 2
   */
  minDigits?: number
}

function CountdownSegment({ unit, value, minDigits = 2, className, ...props }: CountdownSegmentProps) {
  const parts = React.useContext(CountdownContext)
  const reduced = useReducedMotion()

  const resolved = value ?? (unit && parts ? parts[unit] : 0)
  const text = String(Math.max(0, Math.trunc(resolved))).padStart(minDigits, '0')

  return (
    <LazyMotion features={domAnimation} strict>
      <span data-slot="countdown-segment" className={cn('inline-flex', className)} {...props}>
        <span className="sr-only" suppressHydrationWarning>
          {text}
        </span>
        <span aria-hidden="true" dir="ltr" className="inline-flex">
          {text.split('').map((char, i) => (
            <DigitRoller key={i} digit={Number(char)} reduced={reduced} />
          ))}
        </span>
      </span>
    </LazyMotion>
  )
}

export { Countdown, CountdownSegment }
export type { CountdownProps, CountdownSegmentProps, CountdownParts }
