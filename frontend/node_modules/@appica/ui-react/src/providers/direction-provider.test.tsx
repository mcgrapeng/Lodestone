import { renderHook } from '@testing-library/react'
import { type ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { DirectionProvider } from './direction-provider'
import { useDirection } from '../hooks/use-direction'

describe('DirectionProvider', () => {
  it('defaults to ltr with no provider', () => {
    const { result } = renderHook(() => useDirection())
    expect(result.current).toBe('ltr')
  })

  it('provides the configured direction to descendants', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DirectionProvider dir="rtl">{children}</DirectionProvider>
    )
    const { result } = renderHook(() => useDirection(), { wrapper })
    expect(result.current).toBe('rtl')
  })
})
