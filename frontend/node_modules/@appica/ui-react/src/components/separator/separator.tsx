import * as React from 'react'
import { Separator as BaseSeparator } from '@base-ui/react/separator'
import { cn } from '../../internal/utils'

type SeparatorVariant = 'solid' | 'dashed' | 'dotted' | 'double' | 'gradient' | 'wave' | 'zigzag'

const separatorVariants: Record<SeparatorVariant, string> = {
  solid: 'border-current border-solid data-[orientation=horizontal]:border-t data-[orientation=vertical]:border-l',
  dashed:
    'text-border-strong border-current border-dashed data-[orientation=horizontal]:border-t data-[orientation=vertical]:border-l',
  dotted: 'text-border-strong',
  double:
    'border-current border-double data-[orientation=horizontal]:border-t-[calc(var(--border-width)*3)] data-[orientation=vertical]:border-l-[calc(var(--border-width)*3)]',
  gradient:
    'data-[orientation=horizontal]:h-(--border-width) data-[orientation=horizontal]:bg-[linear-gradient(to_right,transparent,currentColor_26%,currentColor_74%,transparent)] data-[orientation=vertical]:w-(--border-width) data-[orientation=vertical]:bg-[linear-gradient(to_bottom,transparent,currentColor_26%,currentColor_74%,transparent)]',
  wave: '',
  zigzag: '',
}

type DecorativeDim = { w: number; h: number; d: string }
const decorativeVariants: Partial<
  Record<SeparatorVariant, { strokeScale: number; horizontal: DecorativeDim; vertical: DecorativeDim }>
> = {
  dotted: {
    strokeScale: 1.75,
    horizontal: { w: 6, h: 8, d: 'M3 4 L3 4' },
    vertical: { w: 8, h: 6, d: 'M4 3 L4 3' },
  },
  wave: {
    strokeScale: 1.5,
    horizontal: { w: 16, h: 8, d: 'M0 4 Q4 1 8 4 T16 4' },
    vertical: { w: 8, h: 16, d: 'M4 0 Q1 4 4 8 T4 16' },
  },
  zigzag: {
    strokeScale: 1.5,
    horizontal: { w: 16, h: 8, d: 'M0 6 L4 2 L8 6 L12 2 L16 6' },
    vertical: { w: 8, h: 16, d: 'M6 0 L2 4 L6 8 L2 12 L6 16' },
  },
}

function DecorativePattern({ variant, horizontal }: { variant: SeparatorVariant; horizontal: boolean }) {
  const patternId = React.useId()
  const config = decorativeVariants[variant]
  if (!config) return null

  const { w, h, d } = horizontal ? config.horizontal : config.vertical

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className="block"
      width={horizontal ? '100%' : w}
      height={horizontal ? h : '100%'}
    >
      <pattern id={patternId} width={w} height={h} patternUnits="userSpaceOnUse">
        <path
          d={d}
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ strokeWidth: `calc(var(--border-width) * ${config.strokeScale})` }}
        />
      </pattern>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
    </svg>
  )
}

type SeparatorProps = React.ComponentProps<typeof BaseSeparator> & {
  /**
   * Line style. `gradient`, `wave`, `zigzag`, and `dotted` are decorative.
   * @default 'solid'
   */
  variant?: SeparatorVariant
}

function Separator({ className, orientation = 'horizontal', variant = 'solid', children, ...props }: SeparatorProps) {
  const isDecorative = variant in decorativeVariants

  return (
    <BaseSeparator
      data-slot="separator"
      orientation={orientation}
      className={cn(
        'text-border shrink-0 data-[orientation=horizontal]:w-full data-[orientation=vertical]:self-stretch',
        separatorVariants[variant],
        className,
      )}
      {...props}
    >
      {isDecorative ? <DecorativePattern variant={variant} horizontal={orientation === 'horizontal'} /> : children}
    </BaseSeparator>
  )
}

export { Separator }
export type { SeparatorProps }
