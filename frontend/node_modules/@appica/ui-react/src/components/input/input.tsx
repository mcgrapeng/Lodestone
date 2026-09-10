'use client'

import * as React from 'react'
import { Input as BaseInput } from '@base-ui/react/input'
import { type VariantProps } from 'class-variance-authority'
import { cn, useComposedRefs } from '../../internal/utils'
import { inputVariants } from './input-variants'

type InputVariant = NonNullable<VariantProps<typeof inputVariants>['variant']>
type InputSize = NonNullable<VariantProps<typeof inputVariants>['size']>

interface InputProps extends Omit<React.ComponentProps<typeof BaseInput>, 'size'> {
  /**
   * Field appearance - bordered or filled.
   * @default 'outline'
   */
  variant?: InputVariant
  /**
   * Scales height, padding, and text. Named `inputSize` to avoid the native `size` attribute.
   * @default 'md'
   */
  inputSize?: InputSize
  /**
   * Show a clear (✕) button once the field has a value.
   * @default false
   */
  clearable?: boolean
  /** Adornment rendered before the field, inside the frame. */
  startSlot?: React.ReactNode
  /** Adornment rendered after the field, inside the frame. */
  endSlot?: React.ReactNode
  /** Called when the clear button is pressed. */
  onClear?: () => void
  /**
   * Props for the inner `<input>` (its own `className`, handlers, the native `size`
   * attribute, …). `size` here is the character count the control is intrinsically wide,
   * not the scale - that is `inputSize`.
   */
  inputProps?: React.ComponentProps<typeof BaseInput>
}

function setNativeValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function Input({
  className,
  variant = 'outline',
  inputSize = 'md',
  clearable,
  startSlot,
  endSlot,
  onClear,
  inputProps,
  ref,
  ...props
}: InputProps) {
  const innerRef = React.useRef<HTMLInputElement>(null)
  const hasWrapper = Boolean(clearable || startSlot || endSlot)

  const ariaInvalid = props['aria-invalid']
  const invalid = ariaInvalid === true || ariaInvalid === 'true'

  const composedRef = useComposedRefs(ref, innerRef)

  const handleClear = () => {
    if (innerRef.current && props.value === undefined) {
      setNativeValue(innerRef.current, '')
    }
    innerRef.current?.focus()
    onClear?.()
  }

  if (!hasWrapper) {
    return (
      <BaseInput
        data-slot="input"
        ref={composedRef}
        {...inputProps}
        className={cn(
          inputVariants({ variant, size: inputSize, state: 'self' }),
          'placeholder:text-foreground-subtle',
          inputProps?.className,
          className,
        )}
        {...props}
        {...(invalid ? { 'data-invalid': '' } : {})}
      />
    )
  }

  return (
    <div
      data-slot="input-wrapper"
      className={cn(inputVariants({ variant, size: inputSize, state: 'within' }), className)}
      {...(invalid ? { 'data-invalid': '' } : {})}
    >
      {startSlot && (
        <div data-slot="input-start" className="-ms-1 flex shrink-0 items-center">
          {startSlot}
        </div>
      )}
      <BaseInput
        data-slot="input"
        ref={composedRef}
        placeholder={props.placeholder ?? ' '}
        {...inputProps}
        className={cn(
          'peer text-foreground placeholder:text-foreground-subtle h-full min-w-0 flex-1 bg-transparent outline-none disabled:cursor-not-allowed',
          inputProps?.className,
        )}
        {...props}
      />
      {clearable && (
        <button
          data-slot="input-clear"
          type="button"
          onClick={handleClear}
          className="text-foreground-subtle hover:text-foreground pointer-events-none shrink-0 cursor-pointer opacity-0 transition-[opacity,color] duration-200 peer-not-placeholder-shown:pointer-events-auto peer-not-placeholder-shown:opacity-100"
          tabIndex={-1}
          aria-label="Clear input"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="2 2 16 16" fill="currentColor" className="size-[1em]">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      )}
      {endSlot && (
        <div data-slot="input-end" className="-me-1 flex shrink-0 items-center">
          {endSlot}
        </div>
      )}
    </div>
  )
}

export { Input }
export type { InputProps }
