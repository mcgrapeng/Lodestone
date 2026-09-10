'use client'

import * as React from 'react'
import { Switch as BaseSwitch } from '@base-ui/react/switch'
import { LazyMotion, domAnimation, m, useAnimate } from 'motion/react'
import { useDirection } from '../../hooks/use-direction'
import { useReducedMotion } from '../../hooks/use-reduced-motion'
import { cn, useComposedRefs } from '../../internal/utils'

const switchSizes = {
  sm: {
    root: 'h-4 w-7.5',
    thumb: 'size-3',
    thumbWidthKeyframes: ['0.75rem', '1.25rem', '0.75rem'],
    thumbXKeyframes: [0, '0.3125rem', '0.875rem'],
    check: 'size-2.5',
  },
  md: {
    root: 'h-5 w-9.5',
    thumb: 'size-4',
    thumbWidthKeyframes: ['1rem', '1.6875rem', '1rem'],
    thumbXKeyframes: [0, '0.4375rem', '1.125rem'],
    check: 'size-3',
  },
  lg: {
    root: 'h-6 w-11.5',
    thumb: 'size-5',
    thumbWidthKeyframes: ['1.25rem', '2.125rem', '1.25rem'],
    thumbXKeyframes: [0, '0.5rem', '1.375rem'],
    check: 'size-4',
  },
} as const

type SwitchSize = keyof typeof switchSizes
type SizeConfig = (typeof switchSizes)[SwitchSize]

const THUMB_TRANSITION = { duration: 0.25, ease: [0.4, 0, 0.2, 1] satisfies [number, number, number, number] }

type Keyframe = number | string

function applyDirection(keyframes: ReadonlyArray<Keyframe>, dirSign: 1 | -1): Keyframe[] {
  if (dirSign === 1) return [...keyframes]
  return keyframes.map((v) => (typeof v === 'number' ? -v : `-${v}`))
}

function SwitchThumb({
  renderProps,
  state,
  dirSign,
  sizeConfig,
  reduced,
}: {
  renderProps: React.ComponentPropsWithRef<'span'>
  state: { checked: boolean }
  dirSign: 1 | -1
  sizeConfig: SizeConfig
  reduced: boolean
}) {
  const { checked } = state
  const { ref, onDrag, onDragStart, onDragEnd, onAnimationStart, onAnimationEnd, ...htmlProps } = renderProps

  const xKeyframes = React.useMemo(() => {
    const directional = applyDirection(sizeConfig.thumbXKeyframes, dirSign)
    return checked ? directional : directional.reverse()
  }, [checked, dirSign, sizeConfig])

  const xFinal = xKeyframes[xKeyframes.length - 1]

  const [scope, animate] = useAnimate()
  const composedRef = useComposedRefs(ref, scope)
  const prevChecked = React.useRef(checked)
  React.useEffect(() => {
    const toggled = prevChecked.current !== checked
    prevChecked.current = checked
    if (toggled && !reduced) {
      animate(scope.current, { x: xKeyframes, width: sizeConfig.thumbWidthKeyframes }, THUMB_TRANSITION)
    } else {
      animate(scope.current, { x: xFinal }, { duration: 0 })
    }
  }, [checked, sizeConfig, animate, scope, reduced, xKeyframes, xFinal])

  return (
    <m.span {...htmlProps} ref={composedRef} initial={{ x: xFinal }}>
      <m.svg
        className={cn('text-foreground-intense', sizeConfig.check)}
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 12 12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ strokeDasharray: 12 }}
        initial={false}
        animate={{ strokeDashoffset: checked ? 0 : 12 }}
        transition={
          reduced
            ? { duration: 0 }
            : {
                strokeDashoffset: {
                  duration: checked ? 0.3 : 0,
                  ease: 'easeOut',
                  delay: checked ? 0.25 : 0,
                },
              }
        }
      >
        <path d="M3 6l2 2 4-4" />
      </m.svg>
    </m.span>
  )
}

interface SwitchProps extends React.ComponentProps<typeof BaseSwitch.Root> {
  /**
   * Scales the track and thumb together.
   * @default 'md'
   */
  size?: SwitchSize
}

function Switch({ className, size = 'md', ...props }: SwitchProps) {
  const direction = useDirection()
  const dirSign: 1 | -1 = direction === 'rtl' ? -1 : 1
  const sizeConfig = switchSizes[size]
  const reduced = useReducedMotion()

  const ariaInvalid = props['aria-invalid']
  const invalid = ariaInvalid === true || ariaInvalid === 'true'

  return (
    <LazyMotion features={domAnimation} strict>
      <BaseSwitch.Root
        data-slot="switch"
        className={cn(
          'bg-background-strong outline-ring flex shrink-0 rounded-full border border-transparent p-px outline-offset-1',
          sizeConfig.root,
          'transition-background duration-200 motion-reduce:transition-none',
          'data-checked:bg-primary data-checked:outline-ring-primary',
          'data-disabled:not-data-checked:border-border-strong data-disabled:opacity-disabled data-disabled:cursor-not-allowed data-disabled:not-data-checked:border-dashed',
          'data-invalid:border-error data-invalid:not-data-checked:bg-error-subtle data-invalid:outline-ring-error',
          className,
        )}
        {...props}
        {...(invalid ? { 'data-invalid': '' } : {})}
      >
        <BaseSwitch.Thumb
          data-slot="switch-thumb"
          className={cn(
            'group flex items-center justify-center rounded-full bg-white shadow-2xs',
            sizeConfig.thumb,
            'data-checked:bg-primary-foreground',
          )}
          render={(renderProps, state) => (
            <SwitchThumb
              renderProps={renderProps}
              state={state}
              dirSign={dirSign}
              sizeConfig={sizeConfig}
              reduced={reduced}
            />
          )}
        />
      </BaseSwitch.Root>
    </LazyMotion>
  )
}

export { Switch }
export type { SwitchProps }
