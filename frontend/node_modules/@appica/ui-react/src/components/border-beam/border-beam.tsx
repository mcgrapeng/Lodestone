import * as React from 'react'
import { cn } from '../../internal/utils'

type BorderBeamTrigger = 'hover' | 'press'

interface BorderBeamProps extends React.ComponentProps<'div'> {
  /**
   * Beam color. It lights the head of the comet and fades to transparent along the tail, so pass a solid color
   * rather than a gradient.
   * @default 'var(--primary)'
   */
  color?: string
  /**
   * How much of the border the comet spans, in percent of one lap.
   * @default 10
   */
  length?: number
  /**
   * Beam thickness in px.
   * @default 1
   */
  thickness?: number
  /**
   * Seconds for one full lap around the border.
   * @default 5
   */
  speed?: number
  /**
   * Seconds before the first lap starts. Negative values start the beam mid-lap, which is how you desynchronize a
   * group of cards.
   * @default 0
   */
  delay?: number
  /**
   * Reveal only on interaction. `'hover'` is pointer-only; `'press'` works on touch. Combine via an array. Omit for
   * always-on.
   */
  revealOn?: BorderBeamTrigger | BorderBeamTrigger[]
  /** Controlled visibility for programmatic states (loading, etc.); OR-ed with `revealOn`. */
  reveal?: boolean
  /**
   * With `revealOn="hover"`, keep the beam visible on touch devices (which have no hover) instead of hidden.
   * @default false
   */
  showOnTouch?: boolean
  /**
   * Scale the beam down while pressed, to track a child `Button`'s own active-press scale.
   * @default false
   */
  pressScale?: boolean
}

/* A conic sweep clipped to the border ring by an XOR mask (same trick as GradientGlow's border), so the comet follows
   the wrapper's radius at any corner. The RTL mirror uses `transform`, not `scale`, so it composes with `pressScale`
   instead of losing to it. */
const RING_MASK = 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)'

function BorderBeam({
  color = 'var(--primary)',
  length = 10,
  thickness = 1,
  speed = 5,
  delay = 0,
  revealOn,
  reveal,
  showOnTouch = false,
  pressScale = false,
  className,
  style,
  children,
  ...props
}: BorderBeamProps) {
  const triggers = revealOn == null ? [] : Array.isArray(revealOn) ? revealOn : [revealOn]
  const managed = triggers.length > 0 || reveal !== undefined
  const grouped = managed || pressScale

  return (
    <div
      data-slot="border-beam"
      data-reveal={managed ? triggers.join(' ') : undefined}
      data-revealed={reveal ? '' : undefined}
      data-show-on-touch={showOnTouch ? '' : undefined}
      className={cn('relative rounded-xl', grouped && 'group/beam', className)}
      style={
        { '--border-beam-duration': `${speed}s`, '--border-beam-delay': `${delay}s`, ...style } as React.CSSProperties
      }
      {...props}
    >
      {children}
      <span
        aria-hidden
        data-slot="border-beam-ring"
        className={cn(
          'pointer-events-none absolute inset-0 rounded-[inherit] rtl:transform-[scaleX(-1)]',
          'motion-safe:animate-border-beam motion-reduce:hidden',
          managed && 'opacity-0 [animation-play-state:paused]',
          managed &&
            triggers.includes('hover') &&
            'group-hover/beam:opacity-100 group-hover/beam:[animation-play-state:running]',
          managed &&
            triggers.includes('hover') &&
            showOnTouch &&
            'hover-none:opacity-100 hover-none:[animation-play-state:running]',
          managed &&
            triggers.includes('press') &&
            'group-active/beam:opacity-100 group-active/beam:[animation-play-state:running]',
          managed && reveal && 'opacity-100 [animation-play-state:running]',
          pressScale && 'group-active/beam:translate-y-px group-active/beam:scale-[0.97]',
          managed && pressScale
            ? '[transition:opacity_500ms_ease-out,scale_150ms_ease-out,translate_150ms_ease-out]'
            : managed
              ? 'transition-opacity duration-500 ease-out'
              : pressScale
                ? '[transition:scale_150ms_ease-out,translate_150ms_ease-out]'
                : undefined,
        )}
        style={{
          background: `conic-gradient(from var(--border-beam-angle), transparent, ${color} ${length}%, transparent calc(${length}% * 1.2))`,
          padding: thickness,
          WebkitMask: RING_MASK,
          WebkitMaskComposite: 'xor',
          mask: RING_MASK,
          maskComposite: 'exclude',
        }}
      />
    </div>
  )
}

export { BorderBeam }
export type { BorderBeamProps }
