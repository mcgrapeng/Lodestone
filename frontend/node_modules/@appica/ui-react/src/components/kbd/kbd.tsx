import * as React from 'react'
import { cn } from '../../internal/utils'

type KbdSize = 'sm' | 'md' | 'lg'

const SIZE_CLASSES: Record<KbdSize, string> = {
  sm: 'h-5 min-w-5 text-xs px-1.25 rounded-2xs',
  md: 'h-6 min-w-6 text-sm px-1.5 rounded-[calc(var(--radius-xs)-0.0625rem)]',
  lg: 'h-7 min-w-7 text-base px-1.75 rounded-xs',
}

interface KbdProps extends React.ComponentProps<'kbd'> {
  /**
   * Height, padding, and text scale. Inherited from a `KbdGroup`.
   * @default 'md'
   */
  size?: KbdSize
}

function Kbd({ className, size = 'md', ...props }: KbdProps) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        'border-border bg-background text-foreground-muted pointer-events-none inline-flex w-fit shrink-0 items-center justify-center border font-sans font-medium whitespace-nowrap select-none',
        'in-data-[slot=tooltip-content]:bg-background-inverse in-data-[slot=tooltip-content]:text-foreground-inverse/75 dark:in-data-[slot=tooltip-content]:border-border-intense/20 in-data-[slot=tooltip-content]:border-white/25',
        SIZE_CLASSES[size],
        className,
      )}
      {...props}
    />
  )
}

interface KbdGroupProps extends React.ComponentProps<'span'> {
  /**
   * Default size applied to each child `Kbd` that doesn't set its own.
   * @default 'md'
   */
  size?: KbdSize
}

function KbdGroup({ className, size = 'md', children, ...props }: KbdGroupProps) {
  return (
    <span data-slot="kbd-group" className={cn('inline-flex items-center gap-0.5 align-middle', className)} {...props}>
      {React.Children.map(children, (child) => {
        if (!React.isValidElement<KbdProps>(child) || child.type !== Kbd) return child
        if (child.props.size !== undefined) return child
        return React.cloneElement(child, { size })
      })}
    </span>
  )
}

export { Kbd, KbdGroup }
export type { KbdProps, KbdGroupProps, KbdSize }
