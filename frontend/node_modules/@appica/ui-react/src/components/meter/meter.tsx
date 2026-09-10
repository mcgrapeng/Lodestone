'use client'

import * as React from 'react'
import { Meter as BaseMeter } from '@base-ui/react/meter'
import { cn } from '../../internal/utils'

type MeterStatus = 'optimum' | 'suboptimum' | 'invalid'

interface MeterStatusClassNames {
  optimum?: string
  suboptimum?: string
  invalid?: string
  default?: string
}

const DEFAULT_STATUS_CLASSES: Required<MeterStatusClassNames> = {
  optimum: 'bg-success-emphasis',
  suboptimum: 'bg-warning-emphasis',
  invalid: 'bg-error-emphasis',
  default: 'bg-primary',
}

const MeterContext = React.createContext<{ indicatorBg: string } | null>(null)

function useMeterContext() {
  const ctx = React.useContext(MeterContext)
  if (!ctx) {
    throw new Error('Meter sub-components must be rendered inside <Meter>')
  }
  return ctx
}

interface MeterProps extends BaseMeter.Root.Props {
  /** Upper edge of the "low" zone. Enables status coloring. */
  low?: number
  /** Lower edge of the "high" zone. Enables status coloring. */
  high?: number
  /** The ideal value; the zone it lands in becomes the green "optimum" zone. Enables status coloring. */
  optimum?: number
  /** Override the indicator background class per status (and the no-threshold `default`). */
  statusClassNames?: MeterStatusClassNames
}

function Meter({
  value,
  min = 0,
  max = 100,
  low,
  high,
  optimum,
  statusClassNames,
  className,
  children,
  ...props
}: MeterProps) {
  const hasThresholds = low !== undefined || high !== undefined || optimum !== undefined
  const status = hasThresholds ? computeStatus(value, min, max, low, high, optimum) : null

  const resolvedClasses = { ...DEFAULT_STATUS_CLASSES, ...statusClassNames }
  const indicatorBg = status === null ? resolvedClasses.default : resolvedClasses[status]
  const ctxValue = React.useMemo(() => ({ indicatorBg }), [indicatorBg])

  return (
    <MeterContext.Provider value={ctxValue}>
      <BaseMeter.Root
        data-slot="meter"
        data-status={status ?? undefined}
        value={value}
        min={min}
        max={max}
        className={cn(
          'grid w-full grid-cols-[1fr_auto] gap-x-2 gap-y-1.5',
          '**:data-[slot=meter-label]:col-start-1 **:data-[slot=meter-label]:row-start-1',
          '**:data-[slot=meter-value]:col-start-2 **:data-[slot=meter-value]:row-start-1 **:data-[slot=meter-value]:justify-self-end',
          '**:data-[slot=meter-progress]:col-span-2',
          className,
        )}
        {...props}
      >
        {children}
      </BaseMeter.Root>
    </MeterContext.Provider>
  )
}

type MeterLabelProps = BaseMeter.Label.Props

function MeterLabel({ className, ...props }: MeterLabelProps) {
  return (
    <BaseMeter.Label
      data-slot="meter-label"
      className={cn('text-foreground-intense text-sm font-medium', className)}
      {...props}
    />
  )
}

type MeterValueProps = BaseMeter.Value.Props

function MeterValue({ className, ...props }: MeterValueProps) {
  return <BaseMeter.Value data-slot="meter-value" className={cn('text-foreground text-sm', className)} {...props} />
}

type MeterProgressProps = BaseMeter.Track.Props

function MeterProgress({ className, ...props }: MeterProgressProps) {
  const { indicatorBg } = useMeterContext()
  return (
    <BaseMeter.Track
      data-slot="meter-progress"
      className={cn('bg-background-strong relative h-1.5 w-full overflow-hidden rounded-full', className)}
      {...props}
    >
      <BaseMeter.Indicator
        data-slot="meter-indicator"
        className={cn(
          'rounded-full transition-[width,background-color] duration-300 motion-reduce:transition-none',
          indicatorBg,
        )}
      />
    </BaseMeter.Track>
  )
}

function computeStatus(
  value: number,
  min: number,
  max: number,
  low: number | undefined,
  high: number | undefined,
  optimum: number | undefined,
): MeterStatus {
  const resolvedLow = low ?? min
  const resolvedHigh = high ?? max
  const resolvedOpt = optimum ?? (min + max) / 2

  const zone = (v: number): 0 | 1 | 2 => (v < resolvedLow ? 0 : v > resolvedHigh ? 2 : 1)

  const optZone = zone(resolvedOpt)
  const valZone = zone(value)

  if (valZone === optZone) return 'optimum'
  if (Math.abs(valZone - optZone) === 1) return 'suboptimum'
  return 'invalid'
}

export { Meter, MeterLabel, MeterValue, MeterProgress }
export type { MeterProps, MeterLabelProps, MeterValueProps, MeterProgressProps, MeterStatusClassNames }
