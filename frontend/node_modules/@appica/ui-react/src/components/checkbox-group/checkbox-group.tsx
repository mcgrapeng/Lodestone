import * as React from 'react'
import { CheckboxGroup as BaseCheckboxGroup } from '@base-ui/react/checkbox-group'
import { cn } from '../../internal/utils'

interface CheckboxGroupProps extends React.ComponentProps<typeof BaseCheckboxGroup> {
  /**
   * Stack the boxes in a column, or wrap them into a row.
   * @default 'vertical'
   */
  orientation?: 'horizontal' | 'vertical'
}

function CheckboxGroup({ className, orientation = 'vertical', ...props }: CheckboxGroupProps) {
  const horizontal = orientation === 'horizontal'
  return (
    <BaseCheckboxGroup
      data-slot="checkbox-group"
      className={cn('flex', horizontal ? 'flex-wrap gap-4' : 'flex-col gap-2', className)}
      {...props}
    />
  )
}

export { CheckboxGroup }
export type { CheckboxGroupProps }
