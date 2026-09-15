'use client'

import * as React from 'react'
import { useLocalStorage } from '../../hooks/use-local-storage'
import { useMediaQuery } from '../../hooks/use-media-query'
import { ThemeScript } from './theme-script'

const MEDIA = '(prefers-color-scheme: dark)'
const SYSTEM_THEMES = ['light', 'dark']
const DEFAULT_THEMES = ['light', 'dark']
// Theme is stored as a raw string so the inline no-flash script can read it
// directly with `localStorage.getItem` (no JSON quotes).
const RAW_STRING = { serializer: (v: string) => v, deserializer: (v: string) => v }

export interface ThemeContextValue {
  /** The chosen theme, possibly `'system'`. */
  theme: string | undefined
  setTheme: (value: string | ((prev: string) => string)) => void
  /** The theme actually applied - `'system'` resolved to `'light'`/`'dark'`. */
  resolvedTheme: string | undefined
  systemTheme: 'light' | 'dark' | undefined
  themes: string[]
  forcedTheme: string | undefined
  /** `false` until the client has mounted - guard theme-dependent UI with this. */
  mounted: boolean
}

const ThemeContext = React.createContext<ThemeContextValue | undefined>(undefined)

const defaultContext: ThemeContextValue = {
  theme: undefined,
  setTheme: () => {},
  resolvedTheme: undefined,
  systemTheme: undefined,
  themes: [],
  forcedTheme: undefined,
  mounted: false,
}

export function useThemeContext(): ThemeContextValue {
  return React.useContext(ThemeContext) ?? defaultContext
}

export interface ThemeProviderProps {
  /** The subtree the theme applies to */
  children?: React.ReactNode
  /**
   * Available theme names
   * @default ['light', 'dark']
   */
  themes?: string[]
  /** Force a theme for the whole subtree (overrides storage + OS) */
  forcedTheme?: string
  /**
   * Respect the OS `prefers-color-scheme`
   * @default true
   */
  enableSystem?: boolean
  /**
   * Suppress CSS transitions during a theme switch
   * @default false
   */
  disableTransitionOnChange?: boolean
  /**
   * Set `color-scheme` on `<html>` so native UI matches
   * @default true
   */
  enableColorScheme?: boolean
  /**
   * `localStorage` key for the persisted choice
   * @default 'theme'
   */
  storageKey?: string
  /** Theme used before a choice is stored */
  defaultTheme?: string
  /** Map a theme name to a custom class applied on `<html>` */
  value?: Record<string, string>
  /** CSP nonce forwarded to the inline script */
  nonce?: string
  /** Extra props for the inline `<script>` */
  scriptProps?: React.ScriptHTMLAttributes<HTMLScriptElement>
}

function disableAnimation(nonce?: string) {
  const css = document.createElement('style')
  if (nonce) css.setAttribute('nonce', nonce)
  css.appendChild(
    document.createTextNode(
      '*,*::before,*::after{-webkit-transition:none!important;-moz-transition:none!important;-o-transition:none!important;-ms-transition:none!important;transition:none!important}',
    ),
  )
  document.head.appendChild(css)
  return () => {
    // Force a reflow so the "no transitions" rule applies before the class swap paints.
    ;(() => window.getComputedStyle(document.body))()
    setTimeout(() => {
      document.head.removeChild(css)
    }, 1)
  }
}

export function ThemeProvider(props: ThemeProviderProps) {
  // Nested providers are a no-op passthrough; only the outermost owns state.
  const existing = React.useContext(ThemeContext)
  if (existing) return <>{props.children}</>
  return <Theme {...props} />
}

function Theme({
  children,
  themes = DEFAULT_THEMES,
  forcedTheme,
  enableSystem = true,
  disableTransitionOnChange = false,
  enableColorScheme = true,
  storageKey = 'theme',
  defaultTheme = enableSystem ? 'system' : 'light',
  value,
  nonce,
  scriptProps,
}: ThemeProviderProps) {
  const [theme, setTheme] = useLocalStorage<string>(storageKey, defaultTheme, RAW_STRING)
  const systemDark = useMediaQuery(MEDIA)
  const systemTheme = enableSystem ? (systemDark ? 'dark' : 'light') : undefined

  const [mounted, setMounted] = React.useState(false)
  React.useEffect(() => setMounted(true), [])

  const resolvedTheme = forcedTheme ?? (theme === 'system' ? (systemDark ? 'dark' : 'light') : theme)

  // Keep mutable config out of the apply effect's deps so it fires only on theme change.
  const cfg = React.useRef({ themes, value, enableColorScheme, disableTransitionOnChange, nonce })
  cfg.current = { themes, value, enableColorScheme, disableTransitionOnChange, nonce }

  const firstRun = React.useRef(true)
  React.useEffect(() => {
    // The inline script already set the correct class for the first paint; skip
    // re-applying on mount or we'd risk a flash from the hydration default.
    if (firstRun.current) {
      firstRun.current = false
      return
    }
    if (!resolvedTheme) return
    const c = cfg.current
    const classFor = (t: string) => (c.value && c.value[t] ? c.value[t] : t)
    const enable = c.disableTransitionOnChange ? disableAnimation(c.nonce) : null
    const el = document.documentElement
    el.classList.remove(...c.themes.map(classFor))
    el.classList.add(classFor(resolvedTheme))
    if (c.enableColorScheme && SYSTEM_THEMES.includes(resolvedTheme)) {
      el.style.colorScheme = resolvedTheme
    }
    enable?.()
  }, [resolvedTheme])

  const ctx = React.useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme,
      resolvedTheme,
      systemTheme,
      themes: enableSystem ? [...themes, 'system'] : themes,
      forcedTheme,
      mounted,
    }),
    [theme, setTheme, resolvedTheme, systemTheme, enableSystem, themes, forcedTheme, mounted],
  )

  return (
    <ThemeContext value={ctx}>
      <ThemeScript
        storageKey={storageKey}
        defaultTheme={defaultTheme}
        forcedTheme={forcedTheme}
        themes={themes}
        value={value}
        enableSystem={enableSystem}
        enableColorScheme={enableColorScheme}
        nonce={nonce}
        scriptProps={scriptProps}
      />
      {children}
    </ThemeContext>
  )
}
