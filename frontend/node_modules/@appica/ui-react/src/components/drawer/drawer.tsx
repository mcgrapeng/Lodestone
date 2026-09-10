'use client'

import * as React from 'react'
import { Drawer as BaseDrawer } from '@base-ui/react/drawer'
import { cn } from '../../internal/utils'
import { type ModalContentProps, splitModalProps } from '../../internal/modal'
import { buttonVariants } from '../button/button-variants'

type DrawerSide = 'top' | 'bottom' | 'left' | 'right'

const SIDE_TO_SWIPE = {
  top: 'up',
  bottom: 'down',
  left: 'left',
  right: 'right',
} as const satisfies Record<DrawerSide, 'up' | 'down' | 'left' | 'right'>

const DrawerSideContext = React.createContext<DrawerSide>('bottom')
const DrawerDepthContext = React.createContext(0)
const DrawerSnapContext = React.createContext(false)

interface DrawerProps extends Omit<React.ComponentProps<typeof BaseDrawer.Root>, 'swipeDirection'> {
  /**
   * The edge the drawer slides in from.
   * @default 'bottom'
   */
  side?: DrawerSide
}

const Drawer = Object.assign(
  function Drawer({ side = 'bottom', ...props }: DrawerProps) {
    const depth = React.useContext(DrawerDepthContext) + 1
    return (
      <DrawerDepthContext value={depth}>
        <DrawerSnapContext value={props.snapPoints != null}>
          <DrawerSideContext value={side}>
            <BaseDrawer.Root swipeDirection={SIDE_TO_SWIPE[side]} {...props} />
          </DrawerSideContext>
        </DrawerSnapContext>
      </DrawerDepthContext>
    )
  },
  { createHandle: BaseDrawer.createHandle },
)

type DrawerProviderProps = React.ComponentProps<typeof BaseDrawer.Provider>

function DrawerProvider(props: DrawerProviderProps) {
  return <BaseDrawer.Provider {...props} />
}

type DrawerIndentBackgroundProps = React.ComponentProps<typeof BaseDrawer.IndentBackground>

function DrawerIndentBackground({ className, ...props }: DrawerIndentBackgroundProps) {
  return (
    <BaseDrawer.IndentBackground
      data-slot="drawer-indent-background"
      className={cn('bg-background fixed inset-0 -z-10', className)}
      {...props}
    />
  )
}

type DrawerIndentProps = React.ComponentProps<typeof BaseDrawer.Indent>

function DrawerIndent({ className, ...props }: DrawerIndentProps) {
  return (
    <BaseDrawer.Indent
      data-slot="drawer-indent"
      className={cn(
        '[--indent-transition:calc(1-clamp(0,calc(var(--drawer-swipe-progress)*100000),1))]',
        'origin-top overflow-hidden transition-[transform,border-radius] ease-[cubic-bezier(0.32,0.72,0,1)]',
        'motion-safe:duration-[calc(var(--indent-transition)*400ms)] motion-reduce:transition-none',
        'data-active:transform-[scale(calc(0.95+0.03*var(--drawer-swipe-progress)))] data-active:rounded-2xl',
        className,
      )}
      {...props}
    />
  )
}

type DrawerTriggerProps = React.ComponentProps<typeof BaseDrawer.Trigger>

function DrawerTrigger({ className, ...props }: DrawerTriggerProps) {
  return <BaseDrawer.Trigger data-slot="drawer-trigger" className={cn(className)} {...props} />
}

const VIEWPORT_SIDE = {
  bottom: 'items-end justify-center',
  top: 'items-start justify-center',
  left: 'items-stretch justify-start',
  right: 'items-stretch justify-end',
} satisfies Record<DrawerSide, string>

const POPUP_SIDE = {
  bottom: cn(
    'w-full origin-bottom [height:var(--drawer-height,auto)] max-h-full [--stack-extent:var(--drawer-frontmost-height,var(--drawer-height,0px))]',
    'data-nested-drawer-open:[height:var(--drawer-frontmost-height,auto)] data-nested-drawer-open:overflow-hidden',
    '[transform:translateY(calc(var(--drawer-swipe-movement-y)-var(--stack-offset)))_scale(var(--stack-scale))]',
    'data-starting-style:[transform:translateY(calc(100%+0.5rem))] data-ending-style:[transform:translateY(calc(100%+0.5rem))]',
  ),
  top: cn(
    'w-full origin-top [height:var(--drawer-height,auto)] max-h-full [--stack-extent:var(--drawer-frontmost-height,var(--drawer-height,0px))]',
    'data-nested-drawer-open:[height:var(--drawer-frontmost-height,auto)] data-nested-drawer-open:overflow-hidden',
    '[transform:translateY(calc(var(--drawer-swipe-movement-y)+var(--stack-offset)))_scale(var(--stack-scale))]',
    'data-starting-style:[transform:translateY(calc(-100%-0.5rem))] data-ending-style:[transform:translateY(calc(-100%-0.5rem))]',
  ),
  left: cn(
    'h-full w-96 max-w-full origin-left [--stack-extent:25rem]',
    '[transform:translateX(calc(var(--drawer-swipe-movement-x)+var(--stack-offset)))_scale(var(--stack-scale))]',
    'data-starting-style:[transform:translateX(calc(-100%-0.5rem))] data-ending-style:[transform:translateX(calc(-100%-0.5rem))]',
  ),
  right: cn(
    'h-full w-96 max-w-full origin-right [--stack-extent:25rem]',
    '[transform:translateX(calc(var(--drawer-swipe-movement-x)-var(--stack-offset)))_scale(var(--stack-scale))]',
    'data-starting-style:[transform:translateX(calc(100%+0.5rem))] data-ending-style:[transform:translateX(calc(100%+0.5rem))]',
  ),
} satisfies Record<DrawerSide, string>

const POPUP_SNAP_SIDE = {
  bottom: cn(
    'h-[calc(100dvh-1rem)] w-full min-h-0 origin-bottom shadow-[0_-24px_32px_-12px_var(--shadow-color)]',
    '[--snap-offset:var(--drawer-snap-point-offset,0px)]',
    '[transform:translateY(calc(var(--drawer-snap-point-offset,0px)+var(--drawer-swipe-movement-y)))]',
    'data-starting-style:[transform:translateY(calc(100%+0.5rem))] data-ending-style:[transform:translateY(calc(100%+0.5rem))]',
  ),
  top: cn(
    'h-[calc(100dvh-1rem)] w-full min-h-0 origin-top',
    '[--snap-offset:var(--drawer-snap-point-offset,0px)]',
    '[transform:translateY(calc(var(--drawer-snap-point-offset,0px)+var(--drawer-swipe-movement-y)))]',
    'data-starting-style:[transform:translateY(calc(-100%-0.5rem))] data-ending-style:[transform:translateY(calc(-100%-0.5rem))]',
  ),
} satisfies Record<'top' | 'bottom', string>

const SHADOW_SIDE = {
  bottom: 'shadow-[0_-24px_32px_-12px_var(--shadow-color)]',
  top: 'shadow-2xl',
  left: 'shadow-[24px_0_32px_-12px_var(--shadow-color)]',
  right: 'shadow-[-24px_0_32px_-12px_var(--shadow-color)]',
} satisfies Record<DrawerSide, string>

const HANDLE_SIDE = {
  bottom:
    'before:absolute before:top-1.5 before:left-1/2 before:h-1 before:w-11.5 before:-translate-x-1/2 before:rounded-full',
  top: 'before:absolute before:bottom-1.5 before:left-1/2 before:h-1 before:w-11.5 before:-translate-x-1/2 before:rounded-full',
  left: 'before:absolute before:inset-e-1.5 before:top-1/2 before:h-11.5 before:w-1 before:-translate-y-1/2 before:rounded-full',
  right:
    'before:absolute before:inset-s-1.5 before:top-1/2 before:h-11.5 before:w-1 before:-translate-y-1/2 before:rounded-full',
} satisfies Record<DrawerSide, string>

const FRAME_PAD_SIDE = {
  bottom: 'pt-4!',
  top: 'pb-4!',
  left: 'pe-4!',
  right: 'ps-4!',
} satisfies Record<DrawerSide, string>

const CONTENT_RECLAIM_SIDE = {
  bottom: 'overflow-hidden [&>[data-slot=drawer-header]]:-mt-4 [&>[data-slot=drawer-close-button]]:top-0',
  top: 'overflow-hidden [&>[data-slot=drawer-footer]]:-mb-4',
  left: 'overflow-hidden [&>:not([data-slot=drawer-close-button])]:-me-4 [&>[data-slot=drawer-close-button]]:inset-e-0',
  right: 'overflow-hidden [&>:not([data-slot=drawer-close-button])]:-ms-4',
} satisfies Record<DrawerSide, string>

type DrawerContentProps = ModalContentProps<
  React.ComponentProps<typeof BaseDrawer.Popup>,
  React.ComponentProps<typeof BaseDrawer.Portal>,
  React.ComponentProps<typeof BaseDrawer.Backdrop>,
  React.ComponentProps<typeof BaseDrawer.Viewport>
> & {
  /**
   * Render the × button in the corner.
   * @default true
   */
  closeButton?: boolean
  /**
   * Accessible label for the close button.
   * @default 'Close'
   */
  closeLabel?: string
  /** Render the dimmed backdrop. Defaults to `true` at the top level, off when nested. */
  backdrop?: boolean
  /**
   * Wrap the panel in a translucent glass frame. Turned off, the drawer is a plain solid
   * card and the handle sits inside it, the way a nested drawer looks. Needs `backdrop`:
   * without one the panel is always solid.
   * @default true
   */
  frame?: boolean
}

function DrawerContent({
  className,
  children,
  closeButton = true,
  closeLabel = 'Close',
  backdrop,
  frame = true,
  backdropProps,
  viewportProps,
  ...props
}: DrawerContentProps) {
  const side = React.useContext(DrawerSideContext)
  const depth = React.useContext(DrawerDepthContext)
  const hasSnap = React.useContext(DrawerSnapContext)
  const forceBackdrop = backdropProps?.forceRender === true
  const showBackdrop = forceBackdrop || (backdrop ?? depth <= 1)
  // The frame is a rim of blurred page around the panel, so it only reads against the
  // backdrop. Without one - a nested drawer, or `backdrop={false}` - it collapses to a
  // plain solid card with the handle inside.
  const showFrame = frame && showBackdrop
  const snapSide = hasSnap && (side === 'bottom' || side === 'top') ? side : null
  const { portal, popup } = splitModalProps(props)

  return (
    <BaseDrawer.Portal {...portal}>
      {showBackdrop && (
        <BaseDrawer.Backdrop
          data-slot="drawer-backdrop"
          {...backdropProps}
          className={cn(
            'fixed inset-0 z-50 bg-black/30 backdrop-blur-sm supports-[-webkit-touch-callout:none]:absolute',
            'opacity-[calc(1-var(--drawer-swipe-progress))]',
            'motion-safe:transition-opacity motion-safe:duration-400 motion-safe:ease-out',
            'data-ending-style:opacity-0 data-starting-style:opacity-0 data-swiping:duration-0',
            backdropProps?.className as string | undefined,
          )}
        />
      )}
      <BaseDrawer.Viewport
        data-slot="drawer-viewport"
        {...viewportProps}
        className={cn(
          'fixed inset-0 z-50 flex overflow-hidden p-2',
          VIEWPORT_SIDE[side],
          snapSide && 'touch-none',
          viewportProps?.className as string | undefined,
        )}
      >
        <BaseDrawer.Popup
          data-slot="drawer-popup"
          {...(showFrame ? { 'data-frame': '' } : {})}
          className={cn(
            'relative flex min-h-0 flex-col rounded-2xl border',
            snapSide
              ? cn(
                  'bg-background border-border-overlay before:bg-background-strong',
                  showFrame &&
                    cn(
                      'data-expanded:before:bg-background data-expanded:border-white/15 data-expanded:p-1.5',
                      'data-expanded:bg-white/10 data-expanded:shadow-none data-expanded:backdrop-blur-sm',
                    ),
                )
              : showFrame
                ? 'before:bg-background border-white/15 bg-white/10 p-1.5 backdrop-blur-sm'
                : 'bg-background border-border-overlay before:bg-background-strong',
            'isolate outline-none',
            (hasSnap || !showFrame) && SHADOW_SIDE[side],
            FRAME_PAD_SIDE[side],
            HANDLE_SIDE[side],
            'motion-safe:transition-[transform,height] motion-safe:duration-400 motion-safe:ease-[cubic-bezier(0.32,1.2,0.4,1)]',
            'data-ending-style:motion-safe:duration-300 data-ending-style:motion-safe:ease-out',
            'data-nested-drawer-swiping:duration-0 data-swiping:duration-0 data-swiping:select-none',
            snapSide
              ? cn('touch-none', POPUP_SNAP_SIDE[snapSide])
              : cn(
                  '[--stack-progress:clamp(0,var(--drawer-swipe-progress,0),1)] [--stack-step:0.05]',
                  '[--stack-count:max(0,calc(var(--nested-drawers,0)-var(--stack-progress)))]',
                  '[--stack-scale:clamp(0,calc(1-var(--stack-step)*var(--stack-count)),1)]',
                  '[--stack-shrink:calc(1-var(--stack-scale))]',
                  '[--stack-peek:calc(var(--stack-count)*1.5rem)]',
                  '[--stack-offset:calc(var(--stack-peek)+var(--stack-shrink)*var(--stack-extent))]',
                  POPUP_SIDE[side],
                ),
            className,
          )}
          {...popup}
        >
          <div
            data-slot="drawer-content"
            className={cn(
              'relative flex min-h-0 flex-col not-has-[>[data-slot=drawer-footer]]:pb-6 not-has-[>[data-slot=drawer-header]]:pt-6 [&>[data-slot=drawer-header]+[data-slot=drawer-footer]]:pt-0',
              showFrame || snapSide
                ? 'bg-background rounded-[calc(var(--radius-2xl)*5/6)]'
                : CONTENT_RECLAIM_SIDE[side],
              snapSide ? 'h-[calc(100dvh-1.5rem-var(--snap-offset,0))]' : 'flex-1',
            )}
          >
            {children}
            {closeButton && (
              <BaseDrawer.Close
                aria-label={closeLabel}
                data-slot="drawer-close-button"
                className={cn(buttonVariants({ variant: 'outline', size: 'icon-sm' }), 'absolute inset-e-3 top-3 z-10')}
              >
                <CloseIcon />
              </BaseDrawer.Close>
            )}
          </div>
        </BaseDrawer.Popup>
      </BaseDrawer.Viewport>
    </BaseDrawer.Portal>
  )
}

type DrawerHeaderProps = React.ComponentPropsWithoutRef<'div'>

function DrawerHeader({ className, ...props }: DrawerHeaderProps) {
  return <div data-slot="drawer-header" className={cn('flex shrink-0 flex-col gap-2 p-6', className)} {...props} />
}

type DrawerTitleProps = React.ComponentProps<typeof BaseDrawer.Title>

function DrawerTitle({ className, ...props }: DrawerTitleProps) {
  return (
    <BaseDrawer.Title
      data-slot="drawer-title"
      className={cn('text-foreground-intense text-2xl font-semibold', className)}
      {...props}
    />
  )
}

type DrawerDescriptionProps = React.ComponentProps<typeof BaseDrawer.Description>

function DrawerDescription({ className, ...props }: DrawerDescriptionProps) {
  return (
    <BaseDrawer.Description
      data-slot="drawer-description"
      className={cn('text-foreground-muted text-sm', className)}
      {...props}
    />
  )
}

type DrawerBodyProps = React.ComponentProps<typeof BaseDrawer.Content>

function DrawerBody({ className, ...props }: DrawerBodyProps) {
  return (
    <BaseDrawer.Content
      data-slot="drawer-body"
      className={cn('min-h-0 flex-1 overflow-y-auto px-6', className)}
      {...props}
    />
  )
}

type DrawerFooterProps = React.ComponentPropsWithoutRef<'div'>

function DrawerFooter({ className, ...props }: DrawerFooterProps) {
  return <div data-slot="drawer-footer" className={cn('flex flex-col gap-2 p-6', className)} {...props} />
}

type DrawerCloseProps = React.ComponentProps<typeof BaseDrawer.Close>

function DrawerClose({ className, ...props }: DrawerCloseProps) {
  return <BaseDrawer.Close data-slot="drawer-close" className={cn(className)} {...props} />
}

function CloseIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M11.594 3.594c.225-.225.588-.225.813 0s.225.588 0 .812L8.813 8l3.594 3.594c.225.225.225.588 0 .813s-.588.225-.812 0L8 8.812l-3.594 3.594c-.225.225-.588.225-.812 0s-.225-.588 0-.812L7.188 8 3.594 4.406c-.225-.225-.225-.588 0-.812s.588-.225.813 0L8 7.187l3.594-3.594z" />
    </svg>
  )
}

export {
  Drawer,
  DrawerProvider,
  DrawerIndent,
  DrawerIndentBackground,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerBody,
  DrawerFooter,
  DrawerClose,
}
export type {
  DrawerProps,
  DrawerProviderProps,
  DrawerIndentProps,
  DrawerIndentBackgroundProps,
  DrawerTriggerProps,
  DrawerContentProps,
  DrawerHeaderProps,
  DrawerTitleProps,
  DrawerDescriptionProps,
  DrawerBodyProps,
  DrawerFooterProps,
  DrawerCloseProps,
}
