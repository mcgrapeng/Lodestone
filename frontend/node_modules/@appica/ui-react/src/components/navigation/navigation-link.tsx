'use client'

import * as React from 'react'
import { mergeProps } from '@base-ui/react/merge-props'
import { useRender } from '@base-ui/react/use-render'
import { cn, focusableProps } from '../../internal/utils'
import { navigationLinkVariants } from './navigation-link-variants'
import {
  useNavigationContext,
  type NavigationOrientation,
  type NavigationSize,
  type NavigationVariant,
  type NavigationActiveLink,
} from './navigation-context'

type NavigationLinkState = {
  active: boolean
  disabled: boolean
}

interface NavigationLinkProps extends useRender.ComponentProps<'a', NavigationLinkState> {
  /**
   * Override the root's variant for this link.
   * @default root
   */
  variant?: NavigationVariant
  /**
   * Override the root's size for this link.
   * @default root
   */
  size?: NavigationSize
  /**
   * Override the root's orientation for this link.
   * @default root
   */
  orientation?: NavigationOrientation
  /** Force the active state, overriding `activeLink`. */
  active?: boolean
  /**
   * Dim the link and remove it from the tab order.
   * @default false
   */
  disabled?: boolean
  /** Matched against the root's `activeLink` to mark this link current. */
  value?: Exclude<NavigationActiveLink, null>
  /**
   * Custom marker for the `indicator` variant.
   * @default chevron
   */
  indicator?: React.ReactNode
}

function NavigationLink({
  className,
  children,
  variant: variantProp,
  size: sizeProp,
  orientation: orientationProp,
  active: activeProp,
  disabled = false,
  value,
  indicator,
  render,
  ...props
}: NavigationLinkProps) {
  const ctx = useNavigationContext()
  const variant: NavigationVariant = variantProp ?? ctx?.variant ?? 'pill'
  const size: NavigationSize = sizeProp ?? ctx?.size ?? 'md'
  const orientation: NavigationOrientation = orientationProp ?? ctx?.orientation ?? 'horizontal'
  const active = activeProp ?? (value !== undefined && ctx?.activeLink === value)

  const content =
    variant === 'indicator' ? (
      <>
        <span data-slot="navigation-link-indicator" aria-hidden>
          {indicator ?? <DefaultIndicator />}
        </span>
        <span data-slot="navigation-link-label">{children}</span>
      </>
    ) : (
      children
    )

  return useRender({
    defaultTagName: 'a',
    render,
    state: { active, disabled } satisfies NavigationLinkState,
    props: mergeProps<'a'>(
      {
        'data-slot': 'navigation-link',
        'data-orientation': orientation,
        'data-active': active || undefined,
        'aria-current': active ? 'page' : undefined,
        ...focusableProps(disabled),
        className: cn(navigationLinkVariants({ variant, size }), className),
        children: content,
      } as unknown as React.AnchorHTMLAttributes<HTMLAnchorElement>,
      props,
    ),
  })
}

function DefaultIndicator() {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M5.558 3.558c.244-.244.641-.244.885 0l4 4c.244.244.244.641 0 .885l-4 4c-.244.244-.641.244-.885 0s-.244-.641 0-.885L9.115 8 5.558 4.442c-.244-.244-.244-.641 0-.885z" />
    </svg>
  )
}

export { NavigationLink }
export type { NavigationLinkProps, NavigationLinkState }
