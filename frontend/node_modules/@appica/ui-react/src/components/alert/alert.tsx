'use client'

import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { AnimatePresence, LazyMotion, domAnimation, m } from 'motion/react'
import { cn } from '../../internal/utils'
import { useReducedMotion } from '../../hooks/use-reduced-motion'
import { useDismissible } from '../../hooks/use-dismissible'

const alertVariants = cva(
  cn(
    'group/alert relative rounded-xl border p-5 text-foreground backdrop-blur-xl',
    'grid w-full items-start',
    "[grid-template-columns:auto_1fr_auto] [grid-template-areas:'icon_title_close'_'._description_.'_'._actions_actions']",
    '@min-[460px]:data-[layout=inline]:items-center',
    '@min-[460px]:data-[layout=inline]:[grid-template-columns:auto_auto_1fr_auto_auto]',
    "@min-[460px]:data-[layout=inline]:[grid-template-areas:'icon_title_description_actions_close']",
  ),
  {
    variants: {
      variant: {
        default: 'bg-background border-border',
        primary: 'bg-primary-subtle border-primary-soft',
        secondary: 'bg-secondary-subtle border-secondary-soft',
        error: 'bg-error-subtle border-error-soft',
        success: 'bg-success-subtle border-success-soft',
        warning: 'bg-warning-subtle border-warning-soft',
        info: 'bg-info-subtle border-info-soft',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

type AlertVariant = NonNullable<VariantProps<typeof alertVariants>['variant']>

const alertIconColor: Record<AlertVariant, string> = {
  default: 'text-foreground-intense',
  primary: 'text-primary',
  secondary: 'text-secondary-emphasis',
  error: 'text-error-emphasis',
  success: 'text-success-emphasis',
  warning: 'text-warning-emphasis',
  info: 'text-info-emphasis',
}

const AlertVariantContext = React.createContext<AlertVariant>('default')

const exitDefault = {
  opacity: 0,
  scale: 0.88,
  filter: 'blur(12px)',
  height: 0,
} as const

const exitReduced = { opacity: 0 } as const

const transition = {
  default: { duration: 0.32, ease: [0.4, 0, 0.2, 1] as const },
  height: { duration: 0.3, ease: [0.4, 0, 0.2, 1] as const, delay: 0.18 },
} as const

type AlertLayout = 'block' | 'inline'

interface AlertProps extends React.HTMLAttributes<HTMLDivElement>, Omit<VariantProps<typeof alertVariants>, 'variant'> {
  /**
   * Color scheme; also drives the `AlertIcon` accent.
   * @default 'default'
   */
  variant?: VariantProps<typeof alertVariants>['variant']
  /**
   * Stack the parts (`block`) or flow them on one row when wide enough (`inline`).
   * @default 'block'
   */
  layout?: AlertLayout
  /**
   * Render a close button that hides the alert (with an exit animation).
   * @default false
   */
  dismissible?: boolean
  /** Controlled visibility. Pair with `onOpenChange`. */
  open?: boolean
  /** Called when the alert is dismissed (with `false`). */
  onOpenChange?: (open: boolean) => void
  /** Remember the dismissal under this key so the alert stays hidden on return (uncontrolled). */
  persistKey?: string
  /**
   * Which Web Storage backs `persistKey`.
   * @default 'local'
   */
  persistStorage?: 'local' | 'session'
  /**
   * Accessible label for the close button.
   * @default 'Dismiss'
   */
  closeLabel?: string
}

function Alert({
  variant,
  layout = 'block',
  dismissible = false,
  open,
  onOpenChange,
  persistKey,
  persistStorage = 'local',
  closeLabel = 'Dismiss',
  role = 'alert',
  className,
  children,
  style,
  ...props
}: AlertProps) {
  const reduced = useReducedMotion()

  const [internalOpen, setInternalOpen] = React.useState(true)
  const persisted = useDismissible(persistKey ?? '', { storage: persistStorage })

  const isControlled = open !== undefined
  const usingPersisted = !isControlled && persistKey != null

  const actualOpen = isControlled ? open : usingPersisted ? persisted.open : internalOpen
  const shouldRender = actualOpen

  const handleDismiss = React.useCallback(() => {
    if (isControlled) {
      onOpenChange?.(false)
      return
    }
    if (usingPersisted) {
      persisted.dismiss()
    } else {
      setInternalOpen(false)
    }
    onOpenChange?.(false)
  }, [isControlled, usingPersisted, persisted, onOpenChange])

  return (
    <AlertVariantContext.Provider value={variant ?? 'default'}>
      <LazyMotion features={domAnimation} strict>
        <AnimatePresence initial={false}>
          {shouldRender && (
            <m.div
              key="alert"
              initial={false}
              exit={reduced ? exitReduced : exitDefault}
              transition={reduced ? { duration: 0 } : transition}
              className="@container overflow-hidden"
            >
              <div
                role={role}
                data-slot="alert"
                data-layout={layout}
                style={style}
                className={cn(alertVariants({ variant }), className)}
                {...props}
              >
                {children}
                {dismissible && (
                  <button
                    type="button"
                    aria-label={closeLabel}
                    data-slot="alert-close"
                    onClick={handleDismiss}
                    className={cn(
                      'text-foreground-muted cursor-pointer rounded-md p-1 transition-colors outline-none [grid-area:close]',
                      'hover:text-foreground-intense',
                      'focus-visible:ring-ring focus-visible:ring-2',
                      'self-start @min-[460px]:group-data-[layout=inline]/alert:self-center',
                      'ms-3 -me-1 -mt-1 @min-[460px]:group-data-[layout=inline]/alert:my-0',
                    )}
                  >
                    <CloseIcon />
                  </button>
                )}
              </div>
            </m.div>
          )}
        </AnimatePresence>
      </LazyMotion>
    </AlertVariantContext.Provider>
  )
}

function CloseIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
      className="size-4"
    >
      <path d="M11.523 3.522c.264-.264.691-.264.955 0s.264.691 0 .955L8.955 8l3.522 3.522c.264.264.264.691 0 .955s-.691.264-.955 0L8 8.955l-3.522 3.522c-.264.264-.691.264-.955 0s-.264-.691 0-.955L7.045 8 3.522 4.478c-.264-.264-.264-.691 0-.955s.691-.264.955 0L8 7.045l3.523-3.522z" />
    </svg>
  )
}

interface AlertIconProps extends React.HTMLAttributes<HTMLSpanElement> {}

function AlertIcon({ className, ...props }: AlertIconProps) {
  const variant = React.useContext(AlertVariantContext)
  return (
    <span
      data-slot="alert-icon"
      className={cn(
        "me-3 flex h-lh shrink-0 items-center [grid-area:icon] [&_svg:not([class*='size-'])]:size-5",
        alertIconColor[variant],
        className,
      )}
      {...props}
    />
  )
}

interface AlertTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  /**
   * Heading level, so the alert fits the page's heading outline.
   * @default 'h5'
   */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'div'
}

function AlertTitle({ className, as: As = 'h5', ...props }: AlertTitleProps) {
  return (
    <As
      data-slot="alert-title"
      className={cn(
        'text-foreground-intense self-center font-semibold [grid-area:title]',
        'text-base @min-[460px]:group-data-[layout=inline]/alert:me-3 @min-[460px]:group-data-[layout=inline]/alert:text-sm',
        className,
      )}
      {...props}
    />
  )
}

interface AlertDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {}

function AlertDescription({ className, ...props }: AlertDescriptionProps) {
  return (
    <p
      data-slot="alert-description"
      className={cn(
        'text-foreground text-sm [grid-area:description]',
        'mt-2 @min-[460px]:group-data-[layout=inline]/alert:mt-0',
        className,
      )}
      {...props}
    />
  )
}

interface AlertActionProps extends React.HTMLAttributes<HTMLDivElement> {}

function AlertAction({ className, ...props }: AlertActionProps) {
  return (
    <div
      data-slot="alert-action"
      className={cn(
        'flex justify-end gap-2 [grid-area:actions]',
        'pt-2 @min-[460px]:group-data-[layout=inline]/alert:ms-3 @min-[460px]:group-data-[layout=inline]/alert:pt-0',
        className,
      )}
      {...props}
    />
  )
}

export { Alert, AlertIcon, AlertTitle, AlertDescription, AlertAction }
export type { AlertProps, AlertIconProps, AlertTitleProps, AlertDescriptionProps, AlertActionProps }
