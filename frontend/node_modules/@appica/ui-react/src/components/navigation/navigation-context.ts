'use client'

import * as React from 'react'

type NavigationOrientation = 'horizontal' | 'vertical'
type NavigationSize = 'sm' | 'md' | 'lg'
type NavigationVariant = 'pill' | 'line' | 'indicator'
type NavigationActiveLink = string | number | null

interface NavigationContextValue {
  orientation: NavigationOrientation
  variant: NavigationVariant
  size: NavigationSize
  activeLink: NavigationActiveLink
}

const NavigationContext = React.createContext<NavigationContextValue | null>(null)

function useNavigationContext() {
  return React.useContext(NavigationContext)
}

export { NavigationContext, useNavigationContext }
export type { NavigationOrientation, NavigationSize, NavigationVariant, NavigationActiveLink, NavigationContextValue }
