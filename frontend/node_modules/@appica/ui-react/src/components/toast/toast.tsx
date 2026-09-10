'use client'

import * as React from 'react'
import { Toast as BaseToast } from '@base-ui/react/toast'
import { type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'
import { useDirection } from '../../hooks/use-direction'
import { buttonVariants } from '../button/button-variants'

type ToastPosition = 'top-left' | 'top-center' | 'top-right' | 'bottom-left' | 'bottom-center' | 'bottom-right'

type ToastSwipeAxis = 'up' | 'down' | 'left' | 'right'

const viewportPositionClasses: Record<ToastPosition, string> = {
  'top-left': 'top-4 left-4',
  'top-center': 'top-4 left-1/2 -translate-x-1/2',
  'top-right': 'top-4 right-4',
  'bottom-left': 'bottom-4 left-4',
  'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
  'bottom-right': 'bottom-4 right-4',
}

const swipeDirectionByPosition: Record<ToastPosition, ToastSwipeAxis[]> = {
  'top-left': ['up', 'left'],
  'top-center': ['up'],
  'top-right': ['up', 'right'],
  'bottom-left': ['down', 'left'],
  'bottom-center': ['down'],
  'bottom-right': ['down', 'right'],
}

const toastAnimationBase =
  '[--gap:0.75rem] [--peek:0.75rem] ' +
  '[--scale:calc(max(0,1-(var(--toast-index)*0.1)))] ' +
  '[--shrink:calc(1-var(--scale))] ' +
  '[--height:var(--toast-frontmost-height,var(--toast-height))] ' +
  'absolute z-[calc(1000-var(--toast-index))] w-full select-none ' +
  'h-[var(--height)] data-expanded:h-[var(--toast-height)] ' +
  'data-ending-style:opacity-0 data-limited:opacity-0 ' +
  '[transition:transform_0.5s_cubic-bezier(0.22,1,0.36,1),opacity_0.5s,height_0.15s] ' +
  'motion-reduce:transition-none'

const toastAnimationBottom =
  'right-0 bottom-0 left-0 origin-bottom ' +
  '[--offset-y:calc(var(--toast-offset-y)*-1+calc(var(--toast-index)*var(--gap)*-1)+var(--toast-swipe-movement-y))] ' +
  '[transform:translateX(var(--toast-swipe-movement-x))_translateY(calc(var(--toast-swipe-movement-y)-(var(--toast-index)*var(--peek))-(var(--shrink)*var(--height))))_scale(var(--scale))] ' +
  'data-expanded:[transform:translateX(var(--toast-swipe-movement-x))_translateY(calc(var(--offset-y)))] ' +
  'motion-safe:data-starting-style:[transform:translateY(150%)] ' +
  'motion-safe:[&[data-ending-style]:not([data-limited]):not([data-swipe-direction])]:[transform:translateY(150%)] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=down]:[transform:translateY(calc(var(--toast-swipe-movement-y)+150%))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=down]:[transform:translateY(calc(var(--toast-swipe-movement-y)+150%))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=left]:[transform:translateX(calc(var(--toast-swipe-movement-x)-150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=left]:[transform:translateX(calc(var(--toast-swipe-movement-x)-150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=right]:[transform:translateX(calc(var(--toast-swipe-movement-x)+150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=right]:[transform:translateX(calc(var(--toast-swipe-movement-x)+150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=up]:[transform:translateY(calc(var(--toast-swipe-movement-y)-150%))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=up]:[transform:translateY(calc(var(--toast-swipe-movement-y)-150%))] ' +
  "after:absolute after:top-full after:left-0 after:h-[calc(var(--gap)+1px)] after:w-full after:content-['']"

const toastAnimationTop =
  'top-0 right-0 left-0 origin-top ' +
  '[--offset-y:calc(var(--toast-offset-y)+(var(--toast-index)*var(--gap))+var(--toast-swipe-movement-y))] ' +
  '[transform:translateX(var(--toast-swipe-movement-x))_translateY(calc(var(--toast-swipe-movement-y)+(var(--toast-index)*var(--peek))+(var(--shrink)*var(--height))))_scale(var(--scale))] ' +
  'data-expanded:[transform:translateX(var(--toast-swipe-movement-x))_translateY(calc(var(--offset-y)))] ' +
  'motion-safe:data-starting-style:[transform:translateY(-150%)] ' +
  'motion-safe:[&[data-ending-style]:not([data-limited]):not([data-swipe-direction])]:[transform:translateY(-150%)] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=down]:[transform:translateY(calc(var(--toast-swipe-movement-y)+150%))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=down]:[transform:translateY(calc(var(--toast-swipe-movement-y)+150%))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=left]:[transform:translateX(calc(var(--toast-swipe-movement-x)-150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=left]:[transform:translateX(calc(var(--toast-swipe-movement-x)-150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=right]:[transform:translateX(calc(var(--toast-swipe-movement-x)+150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=right]:[transform:translateX(calc(var(--toast-swipe-movement-x)+150%))_translateY(var(--offset-y))] ' +
  'motion-safe:data-ending-style:data-[swipe-direction=up]:[transform:translateY(calc(var(--toast-swipe-movement-y)-150%))] ' +
  'motion-safe:data-expanded:data-ending-style:data-[swipe-direction=up]:[transform:translateY(calc(var(--toast-swipe-movement-y)-150%))] ' +
  "after:absolute after:bottom-full after:left-0 after:h-[calc(var(--gap)+1px)] after:w-full after:content-['']"

const ToastPositionContext = React.createContext<ToastPosition>('bottom-right')

interface ToastProviderProps extends BaseToast.Provider.Props {}

function ToastProvider(props: ToastProviderProps) {
  return <BaseToast.Provider {...props} />
}

interface ToasterProps extends Omit<BaseToast.Viewport.Props, 'children'> {
  /**
   * Where the stack is anchored; also sets the default swipe-to-dismiss directions.
   * @default 'bottom-right'
   */
  position?: ToastPosition
  /**
   * Opt in to a countdown progress bar on auto-dismissing toasts.
   * @default false
   */
  progress?: boolean
  /**
   * Provider default (ms) used to size the progress bar for toasts that don't set their own `timeout`. Match your
   * `ToastProvider`'s `timeout`.
   * @default 5000
   */
  timeout?: number
  /**
   * Portal target - scope the toasts to a specific element.
   * @default document.body
   */
  container?: React.ComponentProps<typeof BaseToast.Portal>['container']
  /** Escape hatch forwarded to the underlying `Toast.Portal`. */
  portalProps?: Omit<React.ComponentProps<typeof BaseToast.Portal>, 'children'>
}

function Toaster({
  position = 'bottom-right',
  progress = false,
  timeout = 5000,
  className,
  container,
  portalProps,
  ...viewportProps
}: ToasterProps) {
  const { toasts } = BaseToast.useToastManager<{ icon?: React.ReactNode }>()
  const portal = { ...portalProps, ...(container !== undefined ? { container } : {}) }
  return (
    <ToastPositionContext.Provider value={position}>
      <BaseToast.Portal {...portal}>
        <ToastViewport position={position} className={className} {...viewportProps}>
          {toasts.map((toast) => (
            <Toast key={toast.id} toast={toast} dismissible progress={progress} providerTimeout={timeout}>
              {toast.data?.icon ? <ToastIcon>{toast.data.icon}</ToastIcon> : null}
              {toast.title ? <ToastTitle>{toast.title}</ToastTitle> : null}
              {toast.description ? <ToastDescription>{toast.description}</ToastDescription> : null}
              {toast.actionProps ? (
                <ToastActions>
                  <ToastAction />
                </ToastActions>
              ) : null}
            </Toast>
          ))}
        </ToastViewport>
      </BaseToast.Portal>
    </ToastPositionContext.Provider>
  )
}

interface ToastViewportProps extends BaseToast.Viewport.Props {
  position?: ToastPosition
}

function ToastViewport({ position: positionProp, className, ...props }: ToastViewportProps) {
  const ctxPosition = React.useContext(ToastPositionContext)
  const position = positionProp ?? ctxPosition
  const direction = useDirection()
  return (
    <BaseToast.Viewport
      data-slot="toast-viewport"
      data-position={position}
      dir={direction}
      className={cn(
        'fixed z-50 w-90 max-w-[calc(100vw-2rem)] outline-none',
        viewportPositionClasses[position],
        className,
      )}
      {...props}
    />
  )
}

interface ToastProps extends Omit<BaseToast.Root.Props, 'swipeDirection'> {
  position?: ToastPosition
  dismissible?: boolean
  progress?: boolean
  providerTimeout?: number
  closeLabel?: string
  swipeDirection?: BaseToast.Root.Props['swipeDirection']
}

function Toast({
  position: positionProp,
  dismissible = true,
  progress = false,
  providerTimeout = 5000,
  closeLabel,
  swipeDirection,
  toast,
  className,
  children,
  ...props
}: ToastProps) {
  const ctxPosition = React.useContext(ToastPositionContext)
  const position = positionProp ?? ctxPosition
  const resolvedTimeout = toast.timeout ?? providerTimeout
  const showProgress = progress && resolvedTimeout > 0
  const isBottom = position.startsWith('bottom')

  return (
    <BaseToast.Root
      toast={toast}
      data-slot="toast"
      data-position={position}
      swipeDirection={swipeDirection ?? swipeDirectionByPosition[position]}
      className={cn(
        'group/toast',
        'border-border-overlay bg-background text-foreground rounded-xl border p-4 text-sm backdrop-blur-xl',
        isBottom ? 'shadow-[0_-8px_16px_-4px_var(--shadow-color)]' : 'shadow-lg',
        'grid items-start gap-x-0 gap-y-2',
        'has-data-[slot=toast-icon]:gap-x-3',
        'grid-cols-[auto_1fr_auto]',
        "[grid-template-areas:'icon_title_close']",
        "has-data-[slot=toast-description]:[grid-template-areas:'icon_title_close'_'icon_description_close']",
        "has-data-[slot=toast-actions]:not-has-data-[slot=toast-description]:[grid-template-areas:'icon_title_close'_'icon_actions_actions']",
        "has-data-[slot=toast-actions]:has-data-[slot=toast-description]:[grid-template-areas:'icon_title_close'_'icon_description_close'_'icon_actions_actions']",
        toastAnimationBase,
        isBottom ? toastAnimationBottom : toastAnimationTop,
        className,
      )}
      {...props}
    >
      <BaseToast.Content className="contents">
        {children}
        {dismissible ? closeLabel !== undefined ? <ToastClose closeLabel={closeLabel} /> : <ToastClose /> : null}
      </BaseToast.Content>
      {showProgress ? <ToastProgress key={toast.updateKey} timeout={resolvedTimeout} /> : null}
    </BaseToast.Root>
  )
}

interface ToastIconProps extends React.HTMLAttributes<HTMLSpanElement> {}

function ToastIcon({ className, ...props }: ToastIconProps) {
  return (
    <span
      data-slot="toast-icon"
      className={cn(
        "flex shrink-0 items-center [grid-area:icon] has-[>svg]:h-lh [&>svg:not([class*='size-'])]:size-5",
        className,
      )}
      {...props}
    />
  )
}

interface ToastTitleProps extends BaseToast.Title.Props {}

function ToastTitle({ className, ...props }: ToastTitleProps) {
  return (
    <BaseToast.Title
      data-slot="toast-title"
      className={cn(
        'text-foreground-intense flex w-full items-center gap-2 text-sm font-semibold [grid-area:title]',
        className,
      )}
      {...props}
    />
  )
}

interface ToastDescriptionProps extends BaseToast.Description.Props {}

function ToastDescription({ className, ...props }: ToastDescriptionProps) {
  return (
    <BaseToast.Description
      data-slot="toast-description"
      className={cn('text-foreground text-sm [grid-area:description]', className)}
      {...props}
    />
  )
}

interface ToastActionsProps extends React.HTMLAttributes<HTMLDivElement> {}

function ToastActions({ className, ...props }: ToastActionsProps) {
  return (
    <div
      data-slot="toast-actions"
      className={cn('flex justify-end gap-2 pt-2 [grid-area:actions]', className)}
      {...props}
    />
  )
}

interface ToastActionProps extends BaseToast.Action.Props, VariantProps<typeof buttonVariants> {}

function ToastAction({ className, variant = 'primary', size = 'sm', ...props }: ToastActionProps) {
  return (
    <BaseToast.Action
      data-slot="toast-action"
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}

interface ToastCloseProps extends BaseToast.Close.Props {
  closeLabel?: string
}

function ToastClose({ className, closeLabel = 'Dismiss', children, ...props }: ToastCloseProps) {
  return (
    <BaseToast.Close
      aria-label={closeLabel}
      data-slot="toast-close"
      className={cn(
        'text-foreground-muted -me-1 -mt-1 cursor-pointer self-start rounded-md p-1 outline-none [grid-area:close] motion-safe:transition-colors',
        'hover:text-foreground-intense',
        'focus-visible:ring-ring focus-visible:ring-2',
        className,
      )}
      {...props}
    >
      {children ?? <CloseIcon />}
    </BaseToast.Close>
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

interface ToastProgressProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'style'> {
  timeout: number
}

function ToastProgress({ timeout, className, ...props }: ToastProgressProps) {
  return (
    <div
      data-slot="toast-progress"
      className={cn(
        'pointer-events-none absolute inset-x-0 bottom-0 h-4 overflow-hidden rounded-b-[inherit]',
        'motion-reduce:hidden',
        className,
      )}
      {...props}
    >
      <div
        data-slot="toast-progress-indicator"
        className={cn(
          'bg-primary absolute inset-x-0 bottom-0 h-1 origin-left rtl:origin-right',
          'animate-[toast-progress_linear_forwards]',
          'group-data-expanded/toast:[animation-play-state:paused]',
          'motion-reduce:animate-none',
        )}
        style={{ animationDuration: `${timeout}ms` }}
      />
    </div>
  )
}

type ToastPortalProps = React.ComponentProps<typeof BaseToast.Portal>
function ToastPortal(props: ToastPortalProps) {
  return <BaseToast.Portal {...props} />
}

const useToastManager = BaseToast.useToastManager
const createToastManager = BaseToast.createToastManager

export {
  ToastProvider,
  Toaster,
  ToastViewport,
  ToastPortal,
  Toast,
  ToastIcon,
  ToastTitle,
  ToastDescription,
  ToastActions,
  ToastAction,
  ToastClose,
  ToastProgress,
  useToastManager,
  createToastManager,
}
export type {
  ToastProviderProps,
  ToasterProps,
  ToastViewportProps,
  ToastPortalProps,
  ToastProps,
  ToastIconProps,
  ToastTitleProps,
  ToastDescriptionProps,
  ToastActionsProps,
  ToastActionProps,
  ToastCloseProps,
  ToastProgressProps,
  ToastPosition,
}
