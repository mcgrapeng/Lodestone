import * as React from 'react'
import { cn } from '../../internal/utils'

type SkeletonEffect = 'shimmer' | 'pulse' | 'none'

interface SkeletonProps extends React.ComponentProps<'div'> {
  /**
   * Animation played while the placeholder is visible. All effects honor `prefers-reduced-motion`.
   * @default 'shimmer'
   */
  effect?: SkeletonEffect
}

const effectClasses: Record<SkeletonEffect, string> = {
  shimmer: 'skeleton-shimmer',
  pulse: 'motion-safe:animate-pulse',
  none: '',
}

function Skeleton({ effect = 'shimmer', className, ...props }: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      data-effect={effect}
      aria-hidden="true"
      className={cn(
        'text-foreground-muted relative block shrink-0 overflow-hidden rounded-md bg-current/10 backdrop-blur-xl',
        effectClasses[effect],
        className,
      )}
      {...props}
    />
  )
}

export { Skeleton }
export type { SkeletonProps }
