import * as React from 'react'
import { Fieldset as BaseFieldset } from '@base-ui/react/fieldset'
import { cn } from '../../internal/utils'

type FieldsetProps = React.ComponentProps<typeof BaseFieldset.Root>

function Fieldset({ className, ...props }: FieldsetProps) {
  return <BaseFieldset.Root data-slot="fieldset" className={cn('flex w-full flex-col gap-4', className)} {...props} />
}

type FieldsetLegendProps = React.ComponentProps<typeof BaseFieldset.Legend>

function FieldsetLegend({ className, ...props }: FieldsetLegendProps) {
  return (
    <BaseFieldset.Legend
      data-slot="fieldset-legend"
      className={cn('text-foreground-intense text-lg font-medium', className)}
      {...props}
    />
  )
}

export { Fieldset, FieldsetLegend }
export type { FieldsetProps, FieldsetLegendProps }
