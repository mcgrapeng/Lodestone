'use client'

import * as React from 'react'
import { Button as BaseButton } from '@base-ui/react/button'
import { type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'
import { ButtonGroupContext } from '../button-group/button-group-context'
import { buttonVariants } from './button-variants'

interface ButtonProps extends BaseButton.Props, Omit<VariantProps<typeof buttonVariants>, 'variant' | 'size'> {
  /**
   * Visual style.
   * @default 'primary'
   */
  variant?: VariantProps<typeof buttonVariants>['variant']
  /**
   * Height and padding. The `icon-*` sizes are square, for icon-only buttons.
   * @default 'md'
   */
  size?: VariantProps<typeof buttonVariants>['size']
}

function Button({ className, variant, size, disabled, ...props }: ButtonProps) {
  const group = React.useContext(ButtonGroupContext)
  const resolvedVariant = variant ?? group?.variant
  const resolvedSize = size ?? group?.size
  const resolvedDisabled = disabled || group?.disabled
  return (
    <BaseButton
      data-slot="button"
      disabled={resolvedDisabled}
      className={cn(buttonVariants({ variant: resolvedVariant, size: resolvedSize }), className)}
      {...props}
    />
  )
}

export { Button }
export type { ButtonProps }
