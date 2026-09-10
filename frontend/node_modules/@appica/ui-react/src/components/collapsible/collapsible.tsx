import * as React from 'react'
import { Collapsible as BaseCollapsible } from '@base-ui/react/collapsible'
import { cn } from '../../internal/utils'

type CollapsibleProps = React.ComponentProps<typeof BaseCollapsible.Root>

function Collapsible({ className, ...props }: CollapsibleProps) {
  return <BaseCollapsible.Root data-slot="collapsible" className={cn(className)} {...props} />
}

type CollapsibleTriggerProps = React.ComponentProps<typeof BaseCollapsible.Trigger>

function CollapsibleTrigger({ className, ...props }: CollapsibleTriggerProps) {
  return (
    <BaseCollapsible.Trigger
      data-slot="collapsible-trigger"
      className={cn(
        'outline-ring cursor-pointer select-none',
        'data-disabled:opacity-disabled data-disabled:pointer-events-none',
        className,
      )}
      {...props}
    />
  )
}

type CollapsibleContentProps = React.ComponentProps<typeof BaseCollapsible.Panel>

function CollapsibleContent({ className, ...props }: CollapsibleContentProps) {
  return (
    <BaseCollapsible.Panel
      data-slot="collapsible-content"
      className={cn(
        'overflow-hidden',
        'h-(--collapsible-panel-height)',
        'data-ending-style:h-0 data-starting-style:h-0',
        'transition-[height] duration-400 ease-[cubic-bezier(0.32,0.72,0,1)]',
        'motion-reduce:transition-none',
        className,
      )}
      {...props}
    />
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
export type { CollapsibleProps, CollapsibleTriggerProps, CollapsibleContentProps }
