// Server-safe: a pure inline-script generator plus a <script> component.
// No 'use client' - `getThemeScript` can be called in any environment (Vite
// main entry, Astro `is:inline`, etc.) and `ThemeScript` can render in a
// Server Component <head>.

import * as React from 'react'

export interface ThemeScriptOptions {
  storageKey?: string
  defaultTheme?: string
  forcedTheme?: string
  themes?: string[]
  value?: Record<string, string>
  enableSystem?: boolean
  enableColorScheme?: boolean
}

// Serialized via `.toString()` and injected as an inline <script> that runs
// before hydration to set the theme class on <html> with no flash. It must be
// fully self-contained (no external references) so the stringified output is
// valid, runnable code.
function themeScript(
  storageKey: string,
  defaultTheme: string,
  forcedTheme: string | null,
  themes: string[],
  value: Record<string, string> | null,
  enableSystem: boolean,
  enableColorScheme: boolean,
) {
  const el = document.documentElement
  const system = ['light', 'dark']
  const classFor = (t: string) => (value && value[t] ? value[t] : t)
  const updateDOM = (theme: string) => {
    el.classList.remove(...themes.map(classFor))
    el.classList.add(classFor(theme))
    if (enableColorScheme && system.indexOf(theme) !== -1) {
      el.style.colorScheme = theme
    }
  }
  if (forcedTheme) {
    updateDOM(forcedTheme)
  } else {
    try {
      const stored = localStorage.getItem(storageKey) || defaultTheme
      const resolved =
        enableSystem && stored === 'system'
          ? window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light'
          : stored
      updateDOM(resolved)
    } catch (e) {
      // storage unavailable - leave the default
    }
  }
}

/**
 * Returns the inline no-flash script as a string, ready to drop into a
 * `<script>` before hydration. Use this directly when your framework doesn't
 * render React on the server (e.g. a Vite SPA `index.html`, or Astro
 * `<script is:inline>`); otherwise prefer the `<ThemeScript />` component.
 */
export function getThemeScript(options: ThemeScriptOptions = {}): string {
  const {
    storageKey = 'theme',
    enableSystem = true,
    defaultTheme = enableSystem ? 'system' : 'light',
    forcedTheme,
    themes = ['light', 'dark'],
    value,
    enableColorScheme = true,
  } = options
  // JSON.stringify turns `undefined` into `null` inside arrays, so slicing the
  // brackets yields a valid argument list (unlike a manual comma-join).
  const args = JSON.stringify([
    storageKey,
    defaultTheme,
    forcedTheme ?? null,
    themes,
    value ?? null,
    enableSystem,
    enableColorScheme,
  ]).slice(1, -1)
  return `(${themeScript.toString()})(${args})`
}

export interface ThemeScriptProps extends ThemeScriptOptions {
  nonce?: string
  scriptProps?: React.ScriptHTMLAttributes<HTMLScriptElement>
}

/**
 * Renders the inline no-flash script. The `<ThemeProvider>` mounts this for you;
 * render it manually (e.g. in a Next.js `<head>`) only if you need to control its
 * placement.
 */
export function ThemeScript({ nonce, scriptProps, ...options }: ThemeScriptProps) {
  return (
    <script
      {...scriptProps}
      suppressHydrationWarning
      nonce={typeof window === 'undefined' ? nonce : ''}
      dangerouslySetInnerHTML={{ __html: getThemeScript(options) }}
    />
  )
}
