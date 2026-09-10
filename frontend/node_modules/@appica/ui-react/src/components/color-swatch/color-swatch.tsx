'use client'

import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'
import {
  COLOR_CONTROL_GROUP,
  COLOR_SWATCH_SHAPES,
  COLOR_SWATCH_SIZES,
  colorControlCheckerboard,
  colorControlDisabledClasses,
  colorControlSurfaceClasses,
  describeColor,
  normalizeColor,
} from '../../internal/color-control'
import { useColorPickerContext } from '../../internal/color-picker-context'
import { type Color, formatColor } from '../../lib/color'

const CHECKERBOARD_SIZE = '0.3em 0.3em'

const colorSwatchVariants = cva(
  `${COLOR_CONTROL_GROUP} ${colorControlDisabledClasses} relative isolate inline-flex size-[1em] shrink-0 items-center justify-center forced-color-adjust-none [&_svg:not([class*='size-'])]:size-[0.5em]`,
  {
    variants: {
      size: COLOR_SWATCH_SIZES,
      shape: COLOR_SWATCH_SHAPES,
    },
  },
)

type ColorSwatchPresetSize = NonNullable<VariantProps<typeof colorSwatchVariants>['size']>
type ColorSwatchShape = NonNullable<VariantProps<typeof colorSwatchVariants>['shape']>

interface ColorSwatchProps extends Omit<React.ComponentPropsWithoutRef<'span'>, 'color'> {
  /**
   * Color to show. Pass a `Color` or any CSS color string. Inside a `ColorPicker` it
   * can be left off, and the swatch previews whatever the picker currently holds.
   */
  color?: Color | string
  /**
   * Name announced for the color, in place of the description built from the color
   * itself. Use it for the name your palette gives the color, e.g. `'Fire truck red'`.
   */
  colorName?: string
  /**
   * Rounded square or full circle.
   * @default 'rounded'
   */
  shape?: ColorSwatchShape
  /**
   * A preset scale, or a pixel number for an exact size.
   * @default 'md'
   */
  size?: ColorSwatchPresetSize | number
  /**
   * Back a translucent color with a checkerboard, so it reads as translucent rather
   * than as the flat color it composites to. Turn it off to let the swatch blend into
   * whatever sits behind it. An opaque color covers it either way.
   * @default true
   */
  checkerboard?: boolean
  /**
   * Dim the swatch and swap the color for a flat muted fill.
   * @default false
   */
  disabled?: boolean
}

function ColorSwatch({
  color,
  colorName,
  shape = 'rounded',
  size = 'md',
  checkerboard = true,
  disabled: disabledProp,
  className,
  style,
  children,
  'aria-label': ariaLabel,
  ...props
}: ColorSwatchProps) {
  const picker = useColorPickerContext()
  const resolved = color === undefined ? picker?.value : normalizeColor(color)
  if (!resolved) throw new Error('Appica UI: <ColorSwatch> needs a `color`, or a <ColorPicker> to take one from.')

  const disabled = disabledProp || (picker?.disabled ?? false)
  const isNumeric = typeof size === 'number'
  const checkered = checkerboard && resolved.alpha < 1
  const css = formatColor(resolved)

  const fill = checkered
    ? {
        backgroundImage: `linear-gradient(${css}, ${css}), ${colorControlCheckerboard}`,
        backgroundSize: `auto, ${CHECKERBOARD_SIZE}`,
      }
    : { backgroundColor: css }

  return (
    <span
      role="img"
      aria-label={[colorName ?? describeColor(resolved), ariaLabel].filter(Boolean).join(', ')}
      {...props}
      data-slot="color-swatch"
      {...(disabled ? { 'data-disabled': '' } : {})}
      className={cn(colorSwatchVariants({ shape, size: isNumeric ? undefined : size }), className)}
      style={{
        ...(isNumeric ? { fontSize: `${size}px` } : undefined),
        ...(disabled ? undefined : fill),
        ...style,
      }}
    >
      <span data-slot="color-swatch-surface" aria-hidden="true" className={colorControlSurfaceClasses} />
      {children}
    </span>
  )
}

export { ColorSwatch }
export type { ColorSwatchProps }
