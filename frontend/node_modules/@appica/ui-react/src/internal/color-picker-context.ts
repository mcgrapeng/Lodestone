'use client'

// The channel ColorPicker uses to drive the controls composed inside it. A control
// with no `value` of its own reads the picker's color and writes back to it, which is
// what lets an area, a slider and a palette share one value without any prop wiring.
// Internal: nothing here is re-exported from the package.

import * as React from 'react'
import { normalizeColor } from './color-control'
import type { Color, ColorFormat } from '../lib/color'

export interface ColorPickerContextValue {
  value: Color
  setValue: (color: Color) => void
  commitValue: (color: Color) => void
  format: ColorFormat
  disabled: boolean
}

export const ColorPickerContext = React.createContext<ColorPickerContextValue | null>(null)

/** The enclosing picker, or `null` when the control stands on its own. */
export function useColorPickerContext(): ColorPickerContextValue | null {
  return React.useContext(ColorPickerContext)
}

/** The enclosing picker, for the parts that only exist inside one. */
export function useRequiredColorPickerContext(part: string): ColorPickerContextValue {
  const context = React.useContext(ColorPickerContext)
  if (!context) throw new Error(`Appica UI: <${part}> must be used within <ColorPicker>.`)
  return context
}

export interface ColorControlOptions {
  value?: Color | string
  defaultValue: Color | string
  onValueChange?: (value: Color) => void
  onValueCommitted?: (value: Color) => void
  disabled?: boolean
}

export interface ColorControl {
  color: Color
  disabled: boolean
  setColor: (color: Color) => void
  commitColor: (color: Color) => void
}

/**
 * Resolves a control's color from, in order: its own `value`, the enclosing picker,
 * its own state. Writes go to the picker and to the callbacks either way, so a
 * control stays reportable even when the picker owns the value.
 */
export function useColorControl({
  value,
  defaultValue,
  onValueChange,
  onValueCommitted,
  disabled = false,
}: ColorControlOptions): ColorControl {
  const picker = useColorPickerContext()
  const [uncontrolled, setUncontrolled] = React.useState<Color>(() => normalizeColor(defaultValue))

  const controlled = value !== undefined
  const color = controlled ? normalizeColor(value) : (picker?.value ?? uncontrolled)

  return {
    color,
    disabled: disabled || (picker?.disabled ?? false),
    setColor: (next) => {
      if (!controlled && !picker) setUncontrolled(next)
      picker?.setValue(next)
      onValueChange?.(next)
    },
    commitColor: (next) => {
      picker?.commitValue(next)
      onValueCommitted?.(next)
    },
  }
}
