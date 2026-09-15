'use client'

import * as React from 'react'
import { OTPField as BaseOTPField } from '@base-ui/react/otp-field'
import { type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'
import { inputVariants } from '../input/input-variants'

type OTPFieldVariant = NonNullable<VariantProps<typeof inputVariants>['variant']>
type OTPFieldSize = NonNullable<VariantProps<typeof inputVariants>['size']>

interface OTPFieldContextValue {
  variant: OTPFieldVariant
  size: OTPFieldSize
}

const OTPFieldContext = React.createContext<OTPFieldContextValue | null>(null)

function useOTPFieldContext() {
  const ctx = React.useContext(OTPFieldContext)
  if (!ctx) {
    throw new Error('OTPField sub-components must be rendered inside <OTPField>')
  }
  return ctx
}

const INPUT_SQUARE: Record<OTPFieldSize, string> = {
  sm: 'w-8',
  md: 'w-10',
  lg: 'w-12',
}

const SEPARATOR_SIZE: Record<OTPFieldSize, string> = {
  sm: 'w-3 [&_svg]:size-3',
  md: 'w-4 [&_svg]:size-3.5',
  lg: 'w-5 [&_svg]:size-4.5',
}

interface OTPFieldProps extends Omit<React.ComponentProps<typeof BaseOTPField.Root>, 'className'> {
  /**
   * Slot appearance - bordered or filled.
   * @default 'outline'
   */
  variant?: OTPFieldVariant
  /**
   * Scales every slot.
   * @default 'md'
   */
  size?: OTPFieldSize
  /** Extra classes on the root, merged via `tailwind-merge`. */
  className?: string
}

function OTPField({ variant = 'outline', size = 'md', className, children, ...props }: OTPFieldProps) {
  const ctx = React.useMemo<OTPFieldContextValue>(() => ({ variant, size }), [variant, size])

  return (
    <OTPFieldContext.Provider value={ctx}>
      <BaseOTPField.Root data-slot="otp-field" className={cn('flex w-fit items-center gap-1', className)} {...props}>
        {children}
      </BaseOTPField.Root>
    </OTPFieldContext.Provider>
  )
}

type OTPFieldInputProps = React.ComponentProps<typeof BaseOTPField.Input>

function OTPFieldInput({ className, ...props }: OTPFieldInputProps) {
  const { variant, size } = useOTPFieldContext()

  const ariaInvalid = props['aria-invalid']
  const invalid = ariaInvalid === true || ariaInvalid === 'true'

  return (
    <BaseOTPField.Input
      data-slot="otp-field-input"
      className={cn(
        inputVariants({ variant, size, state: 'self' }),
        'px-0 text-center focus:placeholder:text-transparent',
        INPUT_SQUARE[size],
        className,
      )}
      {...props}
      {...(invalid ? { 'data-invalid': '' } : {})}
    />
  )
}

type OTPFieldSeparatorProps = React.ComponentProps<typeof BaseOTPField.Separator>

function OTPFieldSeparator({ className, children, ...props }: OTPFieldSeparatorProps) {
  const { size } = useOTPFieldContext()

  return (
    <BaseOTPField.Separator
      data-slot="otp-field-separator"
      className={cn('text-border-strong flex items-center justify-center', SEPARATOR_SIZE[size], className)}
      {...props}
    >
      {children ?? <SeparatorMark />}
    </BaseOTPField.Separator>
  )
}

function SeparatorMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 4" fill="none">
      <path d="M2 2H18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export { OTPField, OTPFieldInput, OTPFieldSeparator }
export type { OTPFieldProps, OTPFieldInputProps, OTPFieldSeparatorProps }
