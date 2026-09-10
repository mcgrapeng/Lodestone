'use client'

import * as React from 'react'
import { mergeProps } from '@base-ui/react/merge-props'
import { useRender } from '@base-ui/react/use-render'
import { cva, type VariantProps } from 'class-variance-authority'
import { AnimatePresence, LazyMotion, domAnimation, m } from 'motion/react'
import { cn, focusableProps } from '../../internal/utils'
import { useReducedMotion } from '../../hooks/use-reduced-motion'
import { buttonVariants } from '../button/button-variants'

const chipSizeVariants = cva('', {
  variants: {
    size: {
      sm: "h-6 gap-0.75 rounded-xs px-2 text-xs has-data-[icon=end]:pe-1.5 has-data-[icon=start]:ps-1.5 [&_svg:not([class*='size-'])]:size-3.5",
      md: "h-8 gap-1 rounded-sm px-3 text-sm has-data-[icon=end]:pe-2 has-data-[icon=start]:ps-2 [&_svg:not([class*='size-'])]:size-4",
      lg: "h-10 gap-1.25 rounded-md px-3.5 text-base has-data-[icon=end]:pe-2.5 has-data-[icon=start]:ps-2.5 [&_svg:not([class*='size-'])]:size-4.5",
    },
  },
  defaultVariants: { size: 'md' },
})

type ChipVariant = 'soft' | 'outline' | 'primary' | 'secondary' | 'destructive'
type ChipSize = NonNullable<VariantProps<typeof chipSizeVariants>['size']>

type ChipState = {
  variant: ChipVariant
  size: ChipSize
  dismissible: boolean
}

interface ChipGroupContextValue {
  register: (dismiss: () => void) => () => void
  variant?: ChipVariant
  size?: ChipSize
}

const ChipGroupContext = React.createContext<ChipGroupContextValue | null>(null)

interface ChipProps extends Omit<useRender.ComponentProps<'button', ChipState>, 'render'> {
  /**
   * Visual style, from the shared [`Button`](/ui/components/react/button) palette. Inherited from `ChipGroup`.
   * @default 'soft'
   */
  variant?: ChipVariant
  /**
   * Height, padding, text, and icon size. Inherited from `ChipGroup`.
   * @default 'md'
   */
  size?: ChipSize
  /** Replace the underlying element (e.g. an `<a>`), or compose it with another component. */
  render?: useRender.ComponentProps<'button', ChipState>['render']
  /**
   * Render a close button; clicking the chip dismisses it with an exit animation.
   * @default false
   */
  dismissible?: boolean
  /**
   * Controlled visibility for a **dismissible** chip - pair with `onOpenChange` to own dismissal in your own state.
   * (For a non-dismissible chip, render it conditionally instead.)
   */
  open?: boolean
  /**
   * The **intent** signal - fires with `false` the moment a dismiss is requested. Use it with `open` for controlled
   * mode: update your state here.
   */
  onOpenChange?: (open: boolean) => void
  /**
   * The **completion** signal - fires once the exit animation finishes. Use it in uncontrolled mode to drop the chip
   * from state after it's animated out.
   */
  onDismiss?: () => void
  /**
   * Accessible label for the dismiss action (rendered as `sr-only` text).
   * @default 'Dismiss'
   */
  closeLabel?: string
}

const exitDefault = {
  opacity: 0,
  scale: 0.85,
  filter: 'blur(8px)',
} as const

const exitReduced = { opacity: 0 } as const

const transition = { duration: 0.28, ease: [0.4, 0, 0.2, 1] as const } as const
const reducedTransition = { duration: 0 } as const

const closeIconSize: Record<ChipSize, string> = {
  sm: 'size-3',
  md: 'size-3.5',
  lg: 'size-4',
}

function Chip({
  className,
  variant,
  size,
  render,
  dismissible = false,
  open,
  onOpenChange,
  onDismiss,
  closeLabel = 'Dismiss',
  children,
  onClick,
  ...props
}: ChipProps) {
  const group = React.useContext(ChipGroupContext)
  const resolvedVariant: ChipVariant = variant ?? group?.variant ?? 'soft'
  const resolvedSize: ChipSize = size ?? group?.size ?? 'md'

  const reduced = useReducedMotion()
  const [internalOpen, setInternalOpen] = React.useState(true)
  const isControlled = open !== undefined
  const actualOpen = isControlled ? open : internalOpen

  const triggerDismiss = React.useCallback(() => {
    if (!isControlled) setInternalOpen(false)
    onOpenChange?.(false)
  }, [isControlled, onOpenChange])

  React.useEffect(() => {
    if (!group || !dismissible) return
    return group.register(triggerDismiss)
  }, [group, dismissible, triggerDismiss])

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    onClick?.(event as React.MouseEvent<HTMLButtonElement>)
    if (event.defaultPrevented) return
    if (dismissible) triggerDismiss()
  }

  const composedChildren = dismissible ? (
    <>
      {children}
      <ChipCloseIcon size={resolvedSize} />
      <span className="sr-only">{closeLabel}</span>
    </>
  ) : (
    children
  )

  const chipElement = useRender({
    defaultTagName: 'button',
    render,
    state: { variant: resolvedVariant, size: resolvedSize, dismissible } satisfies ChipState,
    props: mergeProps<'button'>(
      {
        'data-slot': 'chip',
        'data-dismissible': dismissible || undefined,
        type: render ? undefined : 'button',
        ...focusableProps(props.disabled),
        className: cn(
          buttonVariants({ variant: resolvedVariant }),
          chipSizeVariants({ size: resolvedSize }),
          dismissible && 'group/chip',
          className,
        ),
        onClick: handleClick,
        children: composedChildren,
      } as unknown as React.ButtonHTMLAttributes<HTMLButtonElement>,
      props,
    ),
  })

  if (!dismissible) return chipElement

  return (
    <LazyMotion features={domAnimation} strict>
      <AnimatePresence initial={false} onExitComplete={() => onDismiss?.()}>
        {actualOpen && (
          <m.span
            key="chip"
            initial={false}
            exit={reduced ? exitReduced : exitDefault}
            transition={reduced ? reducedTransition : transition}
            className="inline-flex align-middle"
          >
            {chipElement}
          </m.span>
        )}
      </AnimatePresence>
    </LazyMotion>
  )
}

interface ChipCloseIconProps {
  size: ChipSize
}

function ChipCloseIcon({ size }: ChipCloseIconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
      data-slot="chip-close-icon"
      data-icon="end"
      className={cn(
        closeIconSize[size],
        'opacity-60 transition-opacity duration-200 group-hover/chip:opacity-100 motion-reduce:transition-none',
      )}
    >
      <path d="M11.523 3.522c.264-.264.691-.264.955 0s.264.691 0 .955L8.955 8l3.522 3.522c.264.264.264.691 0 .955s-.691.264-.955 0L8 8.955l-3.522 3.522c-.264.264-.691.264-.955 0s-.264-.691 0-.955L7.045 8 3.522 4.478c-.264-.264-.264-.691 0-.955s.691-.264.955 0L8 7.045l3.523-3.522z" />
    </svg>
  )
}

interface ChipGroupHandle {
  clearAll: () => void
}

interface ChipGroupProps extends React.ComponentPropsWithoutRef<'div'> {
  /** Exposes `clearAll()`, which dismisses every `dismissible` child. */
  ref?: React.Ref<ChipGroupHandle>
  /** Default `variant` for every child chip; a chip may override it. */
  variant?: ChipVariant
  /** Default `size` for every child chip; a chip may override it. */
  size?: ChipSize
}

function ChipGroup({ ref, className, variant, size, children, ...props }: ChipGroupProps) {
  const dismissersRef = React.useRef<Set<() => void>>(null as unknown as Set<() => void>)
  if (dismissersRef.current === null) {
    dismissersRef.current = new Set<() => void>()
  }

  React.useImperativeHandle(
    ref,
    () => ({
      clearAll: () => {
        dismissersRef.current.forEach((dismiss) => dismiss())
      },
    }),
    [],
  )

  const contextValue = React.useMemo<ChipGroupContextValue>(
    () => ({
      register: (dismiss) => {
        dismissersRef.current.add(dismiss)
        return () => {
          dismissersRef.current.delete(dismiss)
        }
      },
      variant,
      size,
    }),
    [variant, size],
  )

  return (
    <ChipGroupContext.Provider value={contextValue}>
      <div data-slot="chip-group" className={cn('flex flex-wrap items-center gap-2', className)} {...props}>
        {children}
      </div>
    </ChipGroupContext.Provider>
  )
}

export { Chip, ChipGroup }
export type { ChipProps, ChipGroupProps, ChipGroupHandle }
