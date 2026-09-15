'use client'

import { createContext, use, useEffect, useMemo, type ReactNode } from 'react'

export interface ReducedMotionContextValue {
  disableAnimations: boolean
}

const DEFAULT_CONTEXT: ReducedMotionContextValue = {
  disableAnimations: false,
}

const ReducedMotionContext = createContext<ReducedMotionContextValue>(DEFAULT_CONTEXT)

export interface ReducedMotionProviderProps {
  /** The subtree to opt out of animation */
  children: ReactNode
  /**
   * Force-disable animations regardless of the OS preference
   * @default false
   */
  disableAnimations?: boolean
}

const ATTR = 'data-disable-animations'

/**
 * Opts a subtree out of animation. The JS channel (`useReducedMotion()`) is
 * scoped to this provider's React subtree; the CSS channel (the
 * `motion-reduce:` variant) is driven by a `data-disable-animations` attribute
 * written to `<html>`, so it applies page-wide while mounted and covers
 * portaled popups.
 *
 * Optional - components already respect the OS `prefers-reduced-motion`
 * preference with no provider. Reach for this only to force-disable animations.
 */
export function ReducedMotionProvider({ children, disableAnimations = false }: ReducedMotionProviderProps) {
  useEffect(() => {
    if (!disableAnimations) return
    const html = document.documentElement
    html.setAttribute(ATTR, '')
    return () => {
      html.removeAttribute(ATTR)
    }
  }, [disableAnimations])

  const value = useMemo<ReducedMotionContextValue>(() => ({ disableAnimations }), [disableAnimations])

  return <ReducedMotionContext value={value}>{children}</ReducedMotionContext>
}

export function useReducedMotionContext(): ReducedMotionContextValue {
  return use(ReducedMotionContext)
}
