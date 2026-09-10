import { render, renderHook } from '@testing-library/react'
import { type ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { ReducedMotionProvider } from './reduced-motion-provider'
import { useReducedMotion } from '../hooks/use-reduced-motion'

const ATTR = 'data-disable-animations'

describe('ReducedMotionProvider', () => {
  it('useReducedMotion is false with no provider (test env reports motion allowed)', () => {
    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(false)
  })

  it('forces reduced motion for descendants when disableAnimations is set', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ReducedMotionProvider disableAnimations>{children}</ReducedMotionProvider>
    )
    const { result } = renderHook(() => useReducedMotion(), { wrapper })
    expect(result.current).toBe(true)
  })

  it('writes the data-disable-animations attribute on <html> and removes it on unmount', () => {
    const { unmount } = render(
      <ReducedMotionProvider disableAnimations>
        <span />
      </ReducedMotionProvider>,
    )
    expect(document.documentElement.hasAttribute(ATTR)).toBe(true)
    unmount()
    expect(document.documentElement.hasAttribute(ATTR)).toBe(false)
  })

  it('does not set the attribute when disableAnimations is false', () => {
    render(
      <ReducedMotionProvider>
        <span />
      </ReducedMotionProvider>,
    )
    expect(document.documentElement.hasAttribute(ATTR)).toBe(false)
  })
})
