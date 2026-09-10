'use client'

import * as React from 'react'
import type { ButtonProps } from '../button/button'

type ButtonGroupVariant = NonNullable<ButtonProps['variant']>
type ButtonGroupSize = NonNullable<ButtonProps['size']>

interface ButtonGroupContextValue {
  variant?: ButtonGroupVariant
  size?: ButtonGroupSize
  disabled?: boolean
}

const ButtonGroupContext = React.createContext<ButtonGroupContextValue | null>(null)

export { ButtonGroupContext }
export type { ButtonGroupContextValue, ButtonGroupVariant, ButtonGroupSize }
