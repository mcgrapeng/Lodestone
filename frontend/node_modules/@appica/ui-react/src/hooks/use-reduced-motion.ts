'use client'

import { useMediaQuery } from './use-media-query'
import { useReducedMotionContext } from '../providers/reduced-motion-provider'

const QUERY = '(prefers-reduced-motion: reduce)'

/**
 * Returns `true` when animations should be skipped - either because the OS
 * exposes `prefers-reduced-motion: reduce` or because a parent
 * `<ReducedMotionProvider disableAnimations>` opted out globally.
 */
export function useReducedMotion(): boolean {
  const osPrefersReduced = useMediaQuery(QUERY)
  const { disableAnimations } = useReducedMotionContext()
  return disableAnimations || osPrefersReduced
}
