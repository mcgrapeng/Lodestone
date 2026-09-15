import { render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { type ReactNode } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { ThemeProvider } from './theme-provider'
import { getThemeScript } from './theme-script'
import { useTheme } from '../../hooks/use-theme'

afterEach(() => {
  document.documentElement.className = ''
  document.documentElement.style.colorScheme = ''
  localStorage.clear()
})

describe('getThemeScript', () => {
  it('embeds the storage key and reads localStorage + system preference', () => {
    const s = getThemeScript({ storageKey: 'appica-theme' })
    expect(s).toContain('appica-theme')
    expect(s).toContain('localStorage')
    expect(s).toContain('prefers-color-scheme')
    expect(s.startsWith('(')).toBe(true)
  })

  it('inlines a forced theme', () => {
    expect(getThemeScript({ forcedTheme: 'dark' })).toContain('"dark"')
  })
})

describe('ThemeProvider / useTheme', () => {
  it('returns inert values without a provider', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBeUndefined()
    expect(result.current.mounted).toBe(false)
  })

  it('exposes the default theme and reports mounted after hydration', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider defaultTheme="light" enableSystem={false}>
        {children}
      </ThemeProvider>
    )
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.theme).toBe('light')
    expect(result.current.mounted).toBe(true)
  })

  it('resolves "system" to light/dark via the media query', () => {
    // The test stub reports `prefers-color-scheme: dark` -> false, i.e. light.
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider defaultTheme="system">{children}</ThemeProvider>
    )
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.theme).toBe('system')
    expect(result.current.resolvedTheme).toBe('light')
    expect(result.current.systemTheme).toBe('light')
  })

  it('applies the theme class to <html> and persists as a raw string on change', async () => {
    function Probe() {
      const { theme, setTheme } = useTheme()
      return <button onClick={() => setTheme('dark')}>{theme}</button>
    }
    const user = userEvent.setup()
    render(
      <ThemeProvider defaultTheme="light" enableSystem={false}>
        <Probe />
      </ThemeProvider>,
    )
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    await user.click(screen.getByRole('button'))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.classList.contains('light')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('forcedTheme overrides storage and system', () => {
    localStorage.setItem('theme', 'light')
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider forcedTheme="dark">{children}</ThemeProvider>
    )
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.resolvedTheme).toBe('dark')
    expect(result.current.forcedTheme).toBe('dark')
  })

  it('nested ThemeProvider is a passthrough (outer wins)', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider forcedTheme="dark">
        <ThemeProvider forcedTheme="light">{children}</ThemeProvider>
      </ThemeProvider>
    )
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.resolvedTheme).toBe('dark')
  })
})
