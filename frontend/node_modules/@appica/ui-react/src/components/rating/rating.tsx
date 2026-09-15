'use client'

import * as React from 'react'
import { LazyMotion, animate, domAnimation, m, useMotionValue, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'
import { cn } from '../../internal/utils'
import { useDirection } from '../../hooks/use-direction'
import { useReducedMotion } from '../../hooks/use-reduced-motion'

type RatingVariant = 'filled' | 'outline'
type RatingOrientation = 'horizontal' | 'vertical'

interface RatingIconPair {
  /** Drawn under the fill when `variant="outline"`. */
  empty: React.ReactNode
  /** Drawn as the fill, and as the muted base when `variant="filled"`. */
  filled: React.ReactNode
}

const STAR: RatingIconPair = {
  empty: (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12.007 17.754 5.827 21l1.18-6.876L2 9.256l6.91-1L12 2l3.09 6.255 6.91 1-5.007 4.87L18.173 21z" />
    </svg>
  ),
  filled: (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="m8.33 7.439-6.242.903-.11.023a.98.98 0 0 0-.692 1.206 1 1 0 0 0 .26.438l4.524 4.393-1.067 6.206-.013.107a.975.975 0 0 0 .934 1.034 1 1 0 0 0 .499-.112l5.583-2.93 5.57 2.93.099.045a.98.98 0 0 0 1.275-.566 1 1 0 0 0 .048-.508l-1.068-6.206 4.525-4.394.076-.083a.975.975 0 0 0-.62-1.582L15.67 7.44l-2.79-5.644a.978.978 0 0 0-1.756 0z" />
    </svg>
  ),
}

const ZERO_TRANSITION = { duration: 0 } as const
const SETTLE_TRANSITION = { type: 'spring', stiffness: 380, damping: 34, mass: 0.5 } as const
const SCALE_TRANSITION = { type: 'spring', stiffness: 420, damping: 24, mass: 0.6 } as const
// Overdamped going down so the press reads as instant, underdamped coming back
// up so releasing overshoots slightly before settling.
const PRESS_TRANSITION = { type: 'spring', stiffness: 800, damping: 45, mass: 0.5 } as const
const RELEASE_TRANSITION = { type: 'spring', stiffness: 500, damping: 15, mass: 0.7 } as const

const PRESSED_SCALE = 0.9
const LIFTED_SCALE = 1.14

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const round = (value: number) => Math.round(value * 1e4) / 1e4

function quantize(raw: number, step: number, count: number) {
  return clamp(round(Math.ceil(round(raw / step)) * step), step, count)
}

function clipFor(fill: number, rtl: boolean, vertical: boolean) {
  const inset = `${round((1 - fill) * 100)}%`
  if (vertical) return `inset(0 0 ${inset} 0)`
  return rtl ? `inset(0 0 0 ${inset})` : `inset(0 ${inset} 0 0)`
}

const iconLayerClasses = 'block size-(--rating-size) *:size-full'

// stroke-dasharray inherits into the SVG, where it resolves against the 24-unit
// viewBox - so the dash scales with --rating-size instead of staying fixed.
const DASHED = '[stroke-dasharray:2.5_2]'

interface RatingItemVisualProps {
  index: number
  progress: MotionValue<number>
  icons: RatingIconPair
  variant: RatingVariant
  rtl: boolean
  vertical: boolean
  reduced: boolean
  disabled: boolean
  lifted: boolean
  pressed: boolean
}

function RatingItemVisual({
  index,
  progress,
  icons,
  variant,
  rtl,
  vertical,
  reduced,
  disabled,
  lifted,
  pressed,
}: RatingItemVisualProps) {
  const clipPath = useTransform(progress, (value) => clipFor(clamp(value - index, 0, 1), rtl, vertical))

  // Reading the ref during render is what distinguishes a release (bounce back)
  // from an ordinary hover change (no bounce); the effect commits it afterwards.
  const wasPressed = React.useRef(false)
  React.useEffect(() => {
    wasPressed.current = pressed
  }, [pressed])

  return (
    <m.span
      className="relative block"
      initial={false}
      animate={{ scale: reduced ? 1 : pressed ? PRESSED_SCALE : lifted ? LIFTED_SCALE : 1 }}
      transition={
        reduced
          ? ZERO_TRANSITION
          : pressed
            ? PRESS_TRANSITION
            : wasPressed.current
              ? RELEASE_TRANSITION
              : SCALE_TRANSITION
      }
    >
      <span className="relative block">
        <span
          data-slot="rating-item-base"
          className={cn(
            iconLayerClasses,
            'relative',
            variant === 'filled' && (disabled ? 'text-background-muted' : 'text-border-strong'),
            variant === 'outline' && disabled && DASHED,
          )}
        >
          {variant === 'filled' ? icons.filled : icons.empty}
        </span>
        {variant === 'filled' && disabled ? (
          <span aria-hidden="true" className={cn(iconLayerClasses, 'text-border-strong absolute inset-0', DASHED)}>
            {icons.empty}
          </span>
        ) : null}
        <m.span
          data-slot="rating-item-fill"
          aria-hidden="true"
          className={cn(iconLayerClasses, 'absolute inset-0')}
          style={{ clipPath }}
        >
          {icons.filled}
        </m.span>
      </span>
    </m.span>
  )
}

// The button padding is a sixth of the icon size (4px at the 24px default), so
// the hit area and the gap it creates both scale with `size`.
const ITEM_PADDING = 'p-[calc(var(--rating-size)/6)]'

const rootClasses = cn(
  'text-primary relative inline-flex w-fit items-center data-disabled:cursor-not-allowed data-disabled:opacity-disabled',
  'data-[orientation=vertical]:flex-col',
  'data-[orientation=horizontal]:mx-[calc(var(--rating-size)/-6)]',
  'data-[orientation=vertical]:my-[calc(var(--rating-size)/-6)]',
)

const itemClasses = cn(
  'outline-ring rounded-sm relative inline-flex cursor-pointer items-center justify-center disabled:pointer-events-none',
  ITEM_PADDING,
)

const defaultItemAriaLabel = (value: number, count: number) => `${value} of ${count}`

interface RatingProps extends Omit<
  React.ComponentProps<'div'>,
  'children' | 'defaultValue' | 'onChange' | 'role' | 'aria-readonly'
> {
  /** Controlled rating. Pair with `onValueChange`. */
  value?: number
  /**
   * Uncontrolled initial rating. `0` means unrated.
   * @default 0
   */
  defaultValue?: number
  /** Fires when the rating is committed by a click or a key press. */
  onValueChange?: (value: number) => void
  /** Fires with the `step`-snapped rating under the pointer, and with `null` when it leaves. */
  onHoverChange?: (value: number | null) => void
  /**
   * How many items to render.
   * @default 5
   */
  count?: number
  /**
   * Smallest selectable fraction of an item. Use `0.5` for half icons.
   * @default 1
   */
  step?: number
  /**
   * Icon pair to render. Defaults to a built-in star; pass any 24x24 `currentColor` SVGs, e.g. a matching outline and solid icon from `@appica/icons-react`.
   */
  icon?: RatingIconPair
  /**
   * `'filled'` draws unrated items as muted solid icons, `'outline'` draws them as line icons.
   * @default 'filled'
   */
  variant?: RatingVariant
  /**
   * Lay the items out in a row or a column. A vertical rating fills from the top down.
   * @default 'horizontal'
   */
  orientation?: RatingOrientation
  /**
   * Icon size. A number is read as pixels; a string is used verbatim, so any CSS length works (`'2rem'`, `'1em'` to follow the surrounding text).
   * @default 24
   */
  size?: number | string
  /**
   * Track the pointer with a continuous fill before the rating is committed. Clicking still selects at `step` precision either way.
   * @default true
   */
  hoverable?: boolean
  /**
   * Selecting the current rating again resets it to `0`.
   * @default false
   */
  clearable?: boolean
  /**
   * Blocks interaction and dims the control.
   * @default false
   */
  disabled?: boolean
  /**
   * Renders a non-interactive display of `value`, exposed as a single labeled image.
   * @default false
   */
  readOnly?: boolean
  /** Field name submitted with a form, via a hidden input. */
  name?: string
  /** Accessible name for each item, describing the rating it selects. */
  itemAriaLabel?: (value: number, count: number) => string
}

function Rating({
  value,
  defaultValue = 0,
  onValueChange,
  onHoverChange,
  count = 5,
  step = 1,
  icon = STAR,
  variant = 'filled',
  orientation = 'horizontal',
  size = 24,
  hoverable = true,
  clearable = false,
  disabled = false,
  readOnly = false,
  name,
  itemAriaLabel = defaultItemAriaLabel,
  className,
  style,
  'aria-label': ariaLabel,
  ...props
}: RatingProps) {
  const rtl = useDirection() === 'rtl'
  const vertical = orientation === 'vertical'
  const reduced = useReducedMotion()

  const [uncontrolled, setUncontrolled] = React.useState(defaultValue)
  const current = value ?? uncontrolled

  const [hover, setHover] = React.useState<number | null>(null)
  const hoverRef = React.useRef<number | null>(null)
  const [pressedIndex, setPressedIndex] = React.useState<number | null>(null)
  const itemsRef = React.useRef<Array<HTMLButtonElement | null>>([])

  const progress = useMotionValue(current)
  const settleRef = React.useRef<ReturnType<typeof animate> | null>(null)

  const interactive = !disabled && !readOnly
  const checkedIndex = current > 0 ? Math.ceil(current) - 1 : 0

  const setProgress = React.useCallback(
    (next: number) => {
      settleRef.current?.stop()
      settleRef.current = null
      if (reduced) {
        progress.set(next)
      } else {
        settleRef.current = animate(progress, next, SETTLE_TRANSITION)
      }
    },
    [progress, reduced],
  )

  const previewing = hoverable && hover !== null

  React.useEffect(() => {
    if (!previewing) setProgress(current)
  }, [current, previewing, setProgress])

  const updateHover = (next: number | null) => {
    if (hoverRef.current === next) return
    hoverRef.current = next
    if (hoverable) {
      setHover(next)
      if (next !== null) setProgress(next)
    }
    onHoverChange?.(next)
  }

  const trackPointer = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const span = vertical ? rect.height : rect.width
    if (span === 0) return
    const offset = vertical ? event.clientY - rect.top : event.clientX - rect.left
    const ratio = offset / span
    const exact = clamp((!vertical && rtl ? 1 - ratio : ratio) * count, 0, count)
    updateHover(quantize(exact, step, count))
  }

  const commit = (next: number) => {
    const resolved = clamp(round(next), 0, count)
    if (value === undefined) setUncontrolled(resolved)
    if (resolved !== current) onValueChange?.(resolved)
  }

  const handleItemClick = (event: React.MouseEvent<HTMLButtonElement>, index: number) => {
    const next = (event.detail === 0 ? null : hoverRef.current) ?? index + 1
    commit(clearable && next === current ? 0 : next)
  }

  // Only the item that owns the press may end it: pressing another item blurs
  // this one, and that blur lands after the new item's pointerdown.
  const releasePress = (index: number) => setPressedIndex((cur) => (cur === index ? null : cur))

  const pressProps = (index: number) => ({
    onPointerDown: () => setPressedIndex(index),
    onPointerUp: () => releasePress(index),
    onPointerLeave: () => releasePress(index),
    onPointerCancel: () => releasePress(index),
    onBlur: () => releasePress(index),
    onKeyDown: (event: React.KeyboardEvent) => {
      if (event.key === ' ' || event.key === 'Enter') setPressedIndex(index)
    },
    onKeyUp: () => releasePress(index),
  })

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!interactive) return
    // Radio-group semantics: Down/Right step to the next item, Up/Left to the
    // previous one. Only the horizontal pair mirrors in RTL.
    let next: number
    switch (event.key) {
      case 'ArrowRight':
        next = current + (rtl ? -step : step)
        break
      case 'ArrowLeft':
        next = current + (rtl ? step : -step)
        break
      case 'ArrowDown':
        next = current + step
        break
      case 'ArrowUp':
        next = current - step
        break
      case 'Home':
        next = step
        break
      case 'End':
        next = count
        break
      default:
        return
    }
    event.preventDefault()
    updateHover(null)
    const resolved = clamp(round(next), clearable ? 0 : step, count)
    commit(resolved)
    itemsRef.current[Math.max(0, Math.ceil(resolved) - 1)]?.focus()
  }

  const pointerProps = interactive
    ? {
        onPointerMove: trackPointer,
        onPointerDown: trackPointer,
        onPointerLeave: () => updateHover(null),
        onPointerCancel: () => updateHover(null),
      }
    : {}

  return (
    <LazyMotion features={domAnimation} strict>
      <div
        data-slot="rating"
        data-orientation={orientation}
        role={readOnly ? 'img' : 'radiogroup'}
        aria-label={ariaLabel ?? (readOnly ? `${current} out of ${count}` : undefined)}
        aria-orientation={readOnly ? undefined : orientation}
        {...(disabled ? { 'data-disabled': '' } : {})}
        {...(readOnly ? { 'data-readonly': '' } : {})}
        className={cn(rootClasses, className)}
        style={{ '--rating-size': typeof size === 'number' ? `${size}px` : size, ...style } as React.CSSProperties}
        onKeyDown={interactive ? handleKeyDown : undefined}
        {...pointerProps}
        {...props}
      >
        {Array.from({ length: count }, (_, index) => {
          const visual = (
            <RatingItemVisual
              index={index}
              progress={progress}
              icons={icon}
              variant={variant}
              rtl={rtl}
              vertical={vertical}
              reduced={reduced}
              disabled={disabled}
              lifted={hover !== null && Math.ceil(hover) - 1 === index}
              pressed={pressedIndex === index}
            />
          )

          if (readOnly) {
            return (
              <span key={index} data-slot="rating-item" className={cn('inline-flex', ITEM_PADDING)}>
                {visual}
              </span>
            )
          }

          const checked = Math.ceil(current) === index + 1
          return (
            <button
              key={index}
              type="button"
              role="radio"
              aria-checked={checked}
              aria-label={itemAriaLabel(index + 1, count)}
              tabIndex={index === checkedIndex ? 0 : -1}
              disabled={disabled}
              data-slot="rating-item"
              {...(checked ? { 'data-checked': '' } : {})}
              ref={(node) => {
                itemsRef.current[index] = node
              }}
              className={itemClasses}
              onClick={(event) => handleItemClick(event, index)}
              {...pressProps(index)}
            >
              {visual}
            </button>
          )
        })}
        {name ? <input type="hidden" name={name} value={current} /> : null}
      </div>
    </LazyMotion>
  )
}

export { Rating }
export type { RatingProps, RatingIconPair }
