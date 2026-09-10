'use client'

import * as React from 'react'
import { cn } from '../../internal/utils'
import { ButtonGroupContext, type ButtonGroupVariant, type ButtonGroupSize } from './button-group-context'

const OUTLINED_VARIANTS = new Set<ButtonGroupVariant>(['primary-outline', 'outline', 'light'])

interface ButtonGroupProps extends React.ComponentPropsWithoutRef<'div'> {
  /** Visual style applied to every child `Button`. Inherited unless a button sets its own `variant`. */
  variant?: ButtonGroupVariant
  /** Height/padding applied to every child `Button`. Inherited unless a button sets its own `size`. */
  size?: ButtonGroupSize
  /**
   * Disables every child `Button`. A child can't re-enable itself; the group's `disabled` wins.
   * @default false
   */
  disabled?: boolean
  /**
   * Lay the buttons out in a row or a column; controls which corners are rounded.
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical'
}

function ButtonGroup({
  className,
  variant,
  size,
  disabled,
  orientation = 'horizontal',
  children,
  ...props
}: ButtonGroupProps) {
  const horizontal = orientation === 'horizontal'
  const isOutlined = variant != null && OUTLINED_VARIANTS.has(variant)

  const value = React.useMemo(() => ({ variant, size, disabled }), [variant, size, disabled])

  return (
    <ButtonGroupContext.Provider value={value}>
      <div
        data-slot="button-group"
        role="group"
        className={cn(
          'isolate flex w-fit items-stretch',
          '*:relative *:hover:z-2 *:focus-visible:z-2 *:active:z-2',
          horizontal
            ? [
                '[&>*:not(:first-of-type)]:rounded-s-none [&>*:not(:last-of-type)]:rounded-e-none',
                isOutlined ? '-space-x-(--border-width)' : 'space-x-(--border-width)',
              ]
            : [
                'flex-col',
                '[&>*:not(:first-of-type)]:rounded-t-none [&>*:not(:last-of-type)]:rounded-b-none',
                isOutlined ? '-space-y-(--border-width)' : 'space-y-(--border-width)',
              ],
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </ButtonGroupContext.Provider>
  )
}

export { ButtonGroup }
export type { ButtonGroupProps }
