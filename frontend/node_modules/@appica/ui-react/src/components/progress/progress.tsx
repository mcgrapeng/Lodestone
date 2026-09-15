import * as React from 'react'
import { Progress as BaseProgress } from '@base-ui/react/progress'
import { cn } from '../../internal/utils'

type ProgressVariant = 'bar' | 'circular'

type ProgressLabelProps = BaseProgress.Label.Props
type ProgressValueProps = BaseProgress.Value.Props

interface ProgressProps extends Omit<BaseProgress.Root.Props, 'value'> {
  /**
   * Horizontal track or SVG ring.
   * @default 'bar'
   */
  variant?: ProgressVariant
  /**
   * Diameter of the ring in pixels (`circular` only).
   * @default 56
   */
  size?: number
  /**
   * Track weight in pixels. Defaults to `6` for `bar`, `4` for `circular`.
   * @default 6` / `4
   */
  thickness?: number
  /**
   * Any CSS color for the fill (e.g. `var(--success-emphasis)`).
   * @default primary token
   */
  indicatorColor?: string
  /** Current value, from `min` to `max`. Pass `null` for an indeterminate state. */
  value?: number | null
}

function Progress({
  variant = 'bar',
  size,
  thickness,
  indicatorColor,
  className,
  style,
  children,
  value,
  min = 0,
  max = 100,
  ...props
}: ProgressProps) {
  const resolvedThickness = thickness ?? (variant === 'circular' ? 4 : 6)
  const resolvedSize = size ?? 56

  const rootStyle = {
    ...style,
    '--progress-color': indicatorColor ?? 'var(--primary)',
  } as unknown as React.CSSProperties

  return (
    <BaseProgress.Root
      data-slot="progress"
      data-variant={variant}
      value={value ?? null}
      min={min}
      max={max}
      style={rootStyle}
      className={cn(
        'grid w-full gap-x-2 gap-y-1.5',
        // bar
        'data-[variant=bar]:grid-cols-[1fr_auto]',
        'data-[variant=bar]:**:data-[slot=progress-label]:col-start-1 data-[variant=bar]:**:data-[slot=progress-label]:row-start-1',
        'data-[variant=bar]:**:data-[slot=progress-value]:col-start-2 data-[variant=bar]:**:data-[slot=progress-value]:row-start-1 data-[variant=bar]:**:data-[slot=progress-value]:justify-self-end',
        'data-[variant=bar]:**:data-[slot=progress-track]:col-span-2',
        // circular
        'data-[variant=circular]:w-fit data-[variant=circular]:justify-items-center',
        'data-[variant=circular]:**:data-[slot=progress-circular]:col-start-1 data-[variant=circular]:**:data-[slot=progress-circular]:row-start-1',
        'data-[variant=circular]:**:data-[slot=progress-value]:col-start-1 data-[variant=circular]:**:data-[slot=progress-value]:row-start-1 data-[variant=circular]:**:data-[slot=progress-value]:place-self-center',
        'data-[variant=circular]:**:data-[slot=progress-label]:row-start-2',
        className,
      )}
      {...props}
    >
      {children}
      {variant === 'bar' ? (
        <BaseProgress.Track
          data-slot="progress-track"
          className="bg-background-strong relative w-full overflow-hidden rounded-full"
          style={{ height: resolvedThickness }}
        >
          <BaseProgress.Indicator
            data-slot="progress-indicator"
            className="rounded-full bg-(--progress-color) transition-[width] duration-300 motion-reduce:transition-none"
          />
        </BaseProgress.Track>
      ) : (
        <ProgressCircular value={value ?? null} min={min} max={max} size={resolvedSize} thickness={resolvedThickness} />
      )}
    </BaseProgress.Root>
  )
}

interface ProgressCircularProps {
  value: number | null
  min: number
  max: number
  size: number
  thickness: number
}

function ProgressCircular({ value, min, max, size, thickness }: ProgressCircularProps) {
  const indeterminate = value == null
  const pct = indeterminate ? 0 : Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))
  const center = size / 2
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  return (
    <svg
      data-slot="progress-circular"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden="true"
      className="overflow-visible"
    >
      <circle
        data-slot="progress-track"
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        strokeWidth={thickness}
        className="stroke-background-strong"
      />
      <circle
        data-slot="progress-indicator"
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        strokeWidth={thickness}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${center} ${center})`}
        style={{ stroke: 'var(--progress-color)' }}
        className="transition-[stroke-dashoffset] duration-300 motion-reduce:transition-none"
      />
    </svg>
  )
}

function ProgressLabel({ className, ...props }: BaseProgress.Label.Props) {
  return (
    <BaseProgress.Label
      data-slot="progress-label"
      className={cn('text-foreground-intense text-sm font-medium', className)}
      {...props}
    />
  )
}

function ProgressValue({ className, ...props }: BaseProgress.Value.Props) {
  return (
    <BaseProgress.Value data-slot="progress-value" className={cn('text-foreground text-sm', className)} {...props} />
  )
}

export { Progress, ProgressLabel, ProgressValue }
export type { ProgressProps, ProgressLabelProps, ProgressValueProps }
