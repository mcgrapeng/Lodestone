'use client'

import * as React from 'react'
import { Accordion as BaseAccordion } from '@base-ui/react/accordion'
import { cva } from 'class-variance-authority'
import { cn } from '../../internal/utils'

type AccordionVariant = 'default' | 'alt' | 'flush'
type AccordionIcon = 'chevron' | 'plus' | false
type AccordionIconVariant = 'icon' | 'icon-box'
type AccordionIconPosition = 'end' | 'start'

interface AccordionContextValue {
  variant: AccordionVariant
  icon: AccordionIcon
  iconVariant: AccordionIconVariant
  iconPosition: AccordionIconPosition
}

const AccordionContext = React.createContext<AccordionContextValue>({
  variant: 'default',
  icon: 'chevron',
  iconVariant: 'icon',
  iconPosition: 'end',
})

const AccordionItemContext = React.createContext<{ variant: AccordionVariant } | null>(null)

const itemVariants = cva(
  cn(
    'group/accordion-item',
    'has-focus-visible:ring-ring has-focus-visible:ring-3',
    'data-disabled:opacity-disabled data-disabled:pointer-events-none',
  ),
  {
    variants: {
      variant: {
        default: cn(
          'bg-background-subtle border-border-muted',
          'px-5 pb-5 rounded-xl border backdrop-blur-lg',
          'hover:bg-background-muted data-open:bg-background-muted',
          'transition-colors duration-300',
          'hover:border-transparent data-open:border-transparent',
          'motion-reduce:transition-none',
        ),
        alt: cn(
          'bg-background',
          'px-5 pb-5 rounded-xl border border-transparent',
          'hover:border-border data-open:border-border',
          'transition-colors duration-300',
          'motion-reduce:transition-none',
        ),
        flush: 'pb-3.5',
      },
    },
  },
)

const triggerVariants = cva(
  cn(
    'text-foreground-intense flex flex-1 cursor-pointer items-start justify-between gap-3.5',
    'text-lg font-medium outline-none',
    '[&_svg]:pointer-events-none [&_svg]:shrink-0',
    "[&_svg:not([class*='size-'])]:size-5.5",
    "[&_svg:not([class*='stroke-'])]:stroke-[1.85]",
  ),
  {
    variants: {
      variant: {
        default: '-mx-5 -mb-5 p-5',
        alt: '-mx-5 -mb-5 p-5',
        flush: '-mb-3.5 py-3.5',
      },
    },
  },
)

const iconBoxVariants = cva(
  cn(
    'inline-flex items-center justify-center',
    'size-[1.778em]',
    'rounded-[calc(tan(atan2(var(--radius-sm),2rem))*100%)]',
  ),
  {
    variants: {
      variant: {
        default: 'bg-background border-border border',
        alt: 'bg-background-muted',
        flush: 'bg-background border-border border',
      },
    },
  },
)

interface AccordionProps extends React.ComponentProps<typeof BaseAccordion.Root> {
  /**
   * Surface style applied to every item.
   * @default 'default'
   */
  variant?: AccordionVariant
  /**
   * The open/close indicator, or `false` to hide it.
   * @default 'chevron'
   */
  icon?: AccordionIcon
  /**
   * Plain glyph, or wrapped in a tinted tile.
   * @default 'icon'
   */
  iconVariant?: AccordionIconVariant
  /**
   * Place the icon after or before the trigger label.
   * @default 'end'
   */
  iconPosition?: AccordionIconPosition
}

function Accordion({
  variant = 'default',
  icon = 'chevron',
  iconVariant = 'icon',
  iconPosition = 'end',
  className,
  ...props
}: AccordionProps) {
  const ctx = React.useMemo(
    () => ({ variant, icon, iconVariant, iconPosition }),
    [variant, icon, iconVariant, iconPosition],
  )

  return (
    <AccordionContext.Provider value={ctx}>
      <BaseAccordion.Root
        data-slot="accordion"
        className={cn('flex w-full flex-col', variant !== 'flush' && 'gap-1', className)}
        {...props}
      />
    </AccordionContext.Provider>
  )
}

interface AccordionItemProps extends Omit<React.ComponentProps<typeof BaseAccordion.Item>, 'disabled'> {
  /** Override the root's `variant` for this item. */
  variant?: AccordionVariant
  /**
   * Lock this item shut and skip it during keyboard navigation.
   * @default false
   */
  disabled?: boolean | undefined
}

function AccordionItem({ className, variant, ...props }: AccordionItemProps) {
  const root = React.useContext(AccordionContext)
  const resolvedVariant = variant ?? root.variant
  const itemCtx = React.useMemo(() => ({ variant: resolvedVariant }), [resolvedVariant])

  return (
    <AccordionItemContext.Provider value={itemCtx}>
      <BaseAccordion.Item
        data-slot="accordion-item"
        className={cn(itemVariants({ variant: resolvedVariant }), className)}
        {...props}
      />
    </AccordionItemContext.Provider>
  )
}

interface AccordionTriggerProps extends React.ComponentProps<typeof BaseAccordion.Trigger> {
  /** Override the root's icon for this trigger. */
  icon?: AccordionIcon
  /** Override the root's icon style. */
  iconVariant?: AccordionIconVariant
  /** Override the root's icon position. */
  iconPosition?: AccordionIconPosition
}

function AccordionTrigger({ className, children, icon, iconVariant, iconPosition, ...props }: AccordionTriggerProps) {
  const root = React.useContext(AccordionContext)
  const item = React.useContext(AccordionItemContext)
  const variant = item?.variant ?? root.variant
  const resolvedIcon = icon ?? root.icon
  const resolvedIconVariant = iconVariant ?? root.iconVariant
  const resolvedIconPosition = iconPosition ?? root.iconPosition

  const svgSize =
    resolvedIconVariant === 'icon-box'
      ? resolvedIcon === 'chevron'
        ? 'size-[56%]'
        : 'size-[50%]'
      : resolvedIcon === 'plus'
        ? 'size-[1em]'
        : 'size-[1.12em]'
  let iconNode: React.ReactNode = null
  if (resolvedIcon !== false) {
    const svg = resolvedIcon === 'plus' ? <PlusIcon className={svgSize} /> : <ChevronIcon className={svgSize} />
    const inner =
      resolvedIconVariant === 'icon-box' ? (
        <span data-slot="accordion-trigger-icon-box" className={iconBoxVariants({ variant })}>
          {svg}
        </span>
      ) : (
        svg
      )
    iconNode = <span className="inline-flex h-lh items-center">{inner}</span>
  }

  return (
    <BaseAccordion.Header data-slot="accordion-header" className="flex">
      <BaseAccordion.Trigger
        data-slot="accordion-trigger"
        className={cn(triggerVariants({ variant }), className)}
        {...props}
      >
        {resolvedIconPosition === 'start' && iconNode}
        <span className="flex flex-1 items-start gap-3.5 text-start">{children}</span>
        {resolvedIconPosition === 'end' && iconNode}
      </BaseAccordion.Trigger>
    </BaseAccordion.Header>
  )
}

type AccordionContentProps = React.ComponentProps<typeof BaseAccordion.Panel>

function AccordionContent({ className, children, ...props }: AccordionContentProps) {
  const root = React.useContext(AccordionContext)
  const item = React.useContext(AccordionItemContext)
  const variant = item?.variant ?? root.variant

  return (
    <BaseAccordion.Panel
      data-slot="accordion-content"
      className={cn(
        'overflow-hidden',
        'h-(--accordion-panel-height)',
        'data-ending-style:h-0 data-starting-style:h-0',
        'transition-[height] duration-400 ease-[cubic-bezier(0.32,0.72,0,1)]',
        'motion-reduce:transition-none',
        className,
      )}
      {...props}
    >
      <div className="pt-3">{children}</div>
    </BaseAccordion.Panel>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      data-slot="accordion-icon"
      className={cn(
        'transition-transform duration-300 ease-out motion-reduce:transition-none',
        'group-data-open/accordion-item:rotate-180',
        className,
      )}
    >
      <path d="M14.47 6.97A.75.75 0 0 1 15.53 8.03l-5 5a.75.75 0 0 1-1.061 0l-5-5A.75.75 0 0 1 5.53 6.97l4.47 4.47 4.47-4.47z" />
    </svg>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      aria-hidden="true"
      data-slot="accordion-icon"
      className={cn(
        'transition-transform duration-300 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none',
        'group-data-open/accordion-item:rotate-180',
        className,
      )}
    >
      <path d="M4.167 10 L15.833 10" />
      <path
        d="M10 4.167 L10 15.833"
        className="origin-center transition-transform duration-300 ease-[cubic-bezier(0.65,0,0.35,1)] group-data-open/accordion-item:rotate-90 motion-reduce:transition-none"
      />
    </svg>
  )
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
export type { AccordionProps, AccordionItemProps, AccordionTriggerProps, AccordionContentProps }
