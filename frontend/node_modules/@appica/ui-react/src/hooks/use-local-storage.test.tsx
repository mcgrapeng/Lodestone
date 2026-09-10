import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useLocalStorage } from './use-local-storage'

const RAW = { serializer: (v: string) => v, deserializer: (v: string) => v }

afterEach(() => {
  localStorage.clear()
})

describe('useLocalStorage', () => {
  it('returns the default when nothing is stored', () => {
    const { result } = renderHook(() => useLocalStorage('lsq-empty', 'fallback', RAW))
    expect(result.current[0]).toBe('fallback')
  })

  it('reads an existing stored value', () => {
    localStorage.setItem('lsq-existing', 'stored')
    const { result } = renderHook(() => useLocalStorage('lsq-existing', 'fallback', RAW))
    expect(result.current[0]).toBe('stored')
  })

  it('writes a value and reflects it', () => {
    const { result } = renderHook(() => useLocalStorage('lsq-write', 'a', RAW))
    act(() => result.current[1]('b'))
    expect(result.current[0]).toBe('b')
    expect(localStorage.getItem('lsq-write')).toBe('b')
  })

  it('supports functional updates', () => {
    const { result } = renderHook(() => useLocalStorage('lsq-fn', 1, /* JSON */ undefined))
    act(() => result.current[1]((prev) => prev + 1))
    expect(result.current[0]).toBe(2)
    expect(localStorage.getItem('lsq-fn')).toBe('2')
  })

  it('JSON-serializes objects by default and keeps a stable reference', () => {
    const { result, rerender } = renderHook(() => useLocalStorage('lsq-obj', { n: 0 }))
    act(() => result.current[1]({ n: 5 }))
    const first = result.current[0]
    expect(first).toEqual({ n: 5 })
    rerender()
    // Same raw string -> same parsed reference (no infinite re-render).
    expect(result.current[0]).toBe(first)
  })

  it('remove() falls back to the default', () => {
    const { result } = renderHook(() => useLocalStorage('lsq-remove', 'def', RAW))
    act(() => result.current[1]('x'))
    expect(result.current[0]).toBe('x')
    act(() => result.current[2]())
    expect(result.current[0]).toBe('def')
    expect(localStorage.getItem('lsq-remove')).toBeNull()
  })

  it('syncs components in the same tab', () => {
    const a = renderHook(() => useLocalStorage('lsq-sync', 'init', RAW))
    const b = renderHook(() => useLocalStorage('lsq-sync', 'init', RAW))
    act(() => a.result.current[1]('shared'))
    expect(a.result.current[0]).toBe('shared')
    expect(b.result.current[0]).toBe('shared')
  })
})
