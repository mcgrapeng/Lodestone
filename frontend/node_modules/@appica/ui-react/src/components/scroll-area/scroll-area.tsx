import * as React from 'react'
import { ScrollArea as BaseScrollArea } from '@base-ui/react/scroll-area'
import { cn } from '../../internal/utils'

type ScrollAreaOrientation = 'vertical' | 'horizontal' | 'both'
type ScrollbarVisibility = 'always' | 'auto' | 'never'

const SCROLL_SHADOW_CLASSES = cn(
  'mask-no-repeat mask-intersect',
  'ltr:[mask-image:linear-gradient(to_bottom,transparent_0,black_min(40px,var(--scroll-area-overflow-y-start)),black_calc(100%_-_min(40px,var(--scroll-area-overflow-y-end,40px))),transparent_100%),linear-gradient(to_right,transparent_0,black_min(40px,var(--scroll-area-overflow-x-start)),black_calc(100%_-_min(40px,var(--scroll-area-overflow-x-end,40px))),transparent_100%)]',
  'rtl:[mask-image:linear-gradient(to_bottom,transparent_0,black_min(40px,var(--scroll-area-overflow-y-start)),black_calc(100%_-_min(40px,var(--scroll-area-overflow-y-end,40px))),transparent_100%),linear-gradient(to_left,transparent_0,black_min(40px,var(--scroll-area-overflow-x-start)),black_calc(100%_-_min(40px,var(--scroll-area-overflow-x-end,40px))),transparent_100%)]',
)

const SCROLLBAR_AUTO_CLASSES = cn(
  'pointer-events-none opacity-0',
  'data-[hovering]:pointer-events-auto data-[hovering]:opacity-100',
  'data-[scrolling]:pointer-events-auto data-[scrolling]:opacity-100 data-[scrolling]:duration-0',
)

interface ScrollAreaProps extends React.ComponentProps<typeof BaseScrollArea.Root> {
  /**
   * Which axis (or axes) gets a scrollbar. `both` also renders the corner.
   * @default 'vertical'
   */
  orientation?: ScrollAreaOrientation
  /**
   * Fade the content at scrollable edges via a CSS mask.
   * @default false
   */
  scrollShadow?: boolean
  /**
   * `auto` reveals the bar on hover/scroll; `never` hides it while keeping content scrollable.
   * @default 'always'
   */
  scrollbarVisibility?: ScrollbarVisibility
  /** Props forwarded to the inner scroll viewport - `ref`, `onScroll`, `className`, etc. */
  viewportProps?: Omit<React.ComponentProps<typeof BaseScrollArea.Viewport>, 'children'>
}

function ScrollArea({
  orientation = 'vertical',
  scrollShadow = false,
  scrollbarVisibility = 'always',
  className,
  children,
  viewportProps,
  ...props
}: ScrollAreaProps) {
  const showVertical = scrollbarVisibility !== 'never' && (orientation === 'vertical' || orientation === 'both')
  const showHorizontal = scrollbarVisibility !== 'never' && (orientation === 'horizontal' || orientation === 'both')

  return (
    <BaseScrollArea.Root data-slot="scroll-area" className={cn('relative flex flex-col', className)} {...props}>
      <BaseScrollArea.Viewport
        data-slot="scroll-area-viewport"
        {...viewportProps}
        className={cn(
          'focus-visible:ring-ring min-h-0 w-full flex-1 rounded-[inherit] outline-none focus-visible:ring-2',
          scrollShadow && SCROLL_SHADOW_CLASSES,
          viewportProps?.className,
        )}
      >
        <BaseScrollArea.Content
          data-slot="scroll-area-content"
          {...(orientation === 'vertical' ? { style: { minWidth: 0 } } : {})}
        >
          {children}
        </BaseScrollArea.Content>
      </BaseScrollArea.Viewport>
      {showVertical && <Scrollbar orientation="vertical" visibility={scrollbarVisibility} />}
      {showHorizontal && <Scrollbar orientation="horizontal" visibility={scrollbarVisibility} />}
      {orientation === 'both' && scrollbarVisibility !== 'never' && (
        <BaseScrollArea.Corner data-slot="scroll-area-corner" />
      )}
    </BaseScrollArea.Root>
  )
}

function Scrollbar({
  orientation,
  visibility,
}: {
  orientation: 'vertical' | 'horizontal'
  visibility: ScrollbarVisibility
}) {
  return (
    <BaseScrollArea.Scrollbar
      data-slot="scroll-area-scrollbar"
      data-visibility={visibility}
      orientation={orientation}
      className={cn(
        'm-0.5 flex touch-none select-none',
        'transition-[width,height,opacity] duration-150 ease-out motion-reduce:transition-none',
        'data-[orientation=vertical]:w-1.25 data-[orientation=vertical]:justify-center',
        'data-[orientation=horizontal]:h-1.25 data-[orientation=horizontal]:items-center',
        'data-[orientation=vertical]:hover:w-2',
        'data-[orientation=horizontal]:hover:h-2',
        visibility === 'auto' && SCROLLBAR_AUTO_CLASSES,
      )}
    >
      <BaseScrollArea.Thumb
        data-slot="scroll-area-thumb"
        className={cn(
          'bg-background-strong rounded-full',
          'data-[orientation=vertical]:w-full',
          'data-[orientation=horizontal]:h-full',
        )}
      />
    </BaseScrollArea.Scrollbar>
  )
}

export { ScrollArea }
export type { ScrollAreaProps }
