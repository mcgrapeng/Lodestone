import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useMediaQuery } from './use-media-query'

type Listener = (e: MediaQueryListEvent) => void

function createMatchMediaMock(initial: Record<string, boolean> = {}) {
  const entries = new Map<string, { matches: boolean; listeners: Set<Listener> }>()
  const entry = (query: string) => {
    let e = entries.get(query)
    if (!e) {
      e = { matches: initial[query] ?? false, listeners: new Set() }
      entries.set(query, e)
    }
    return e
  }

  const matchMedia = (query: string): MediaQueryList => {
    const e = entry(query)
    return {
      get matches() {
        return e.matches
      },
      media: query,
      onchange: null,
      addEventListener: (_: string, cb: Listener) => e.listeners.add(cb),
      removeEventListener: (_: string, cb: Listener) => e.listeners.delete(cb),
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    } as unknown as MediaQueryList
  }

  const set = (query: string, matches: boolean) => {
    const e = entry(query)
    e.matches = matches
    e.listeners.forEach((cb) => cb({ matches } as MediaQueryListEvent))
  }

  return { matchMedia, set }
}

describe('useMediaQuery', () => {
  const original = window.matchMedia
  afterEach(() => {
    window.matchMedia = original
  })

  it('returns the current match state for the query', () => {
    const { matchMedia } = createMatchMediaMock({ '(min-width: 768px)': true })
    window.matchMedia = vi.fn(matchMedia)
    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(true)
  })

  it('re-renders when the query match changes', () => {
    const { matchMedia, set } = createMatchMediaMock({ '(min-width: 768px)': false })
    window.matchMedia = vi.fn(matchMedia)
    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(false)

    act(() => set('(min-width: 768px)', true))
    expect(result.current).toBe(true)
  })
})
