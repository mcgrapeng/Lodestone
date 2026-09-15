// Shared plumbing for floating *Content components - the ones that wrap a Base UI
// Portal → Positioner → Popup trio (Popover, Tooltip, PreviewCard, Menu, Select,
// Combobox, Autocomplete, …).
//
// Consumers of this library don't get direct access to the inner Portal/Positioner
// elements the way a copy-paste (shadcn-style) component would. So every *Content
// must map the Base UI surface itself. This module keeps that mapping consistent:
//
//   1. The common Positioner positioning props (+ the two Portal props) are
//      promoted to flat props on *Content - Radix/shadcn ergonomics.
//   2. `positionerProps` / `portalProps` escape hatches forward the long tail
//      (e.g. `style`, `render`) without each component re-enumerating it.
//
// `className`/`style`/`render` are intentionally NOT promoted: *Content represents
// the Popup, so those stay bound to it. Use the escape hatches to reach the
// Positioner/Portal element instead.

/**
 * Positioner props promoted to flat props on every floating *Content.
 * Mirrors Base UI's `UseAnchorPositioningSharedParameters` (v1.5.0).
 */
export const FLOATING_POSITIONER_KEYS = [
  'side',
  'sideOffset',
  'align',
  'alignOffset',
  'anchor',
  'positionMethod',
  'collisionBoundary',
  'collisionPadding',
  'collisionAvoidance',
  'sticky',
  'arrowPadding',
  'disableAnchorTracking',
] as const

/** Portal props promoted to flat props on every floating *Content. */
export const FLOATING_PORTAL_KEYS = ['container', 'keepMounted'] as const

type PositionerKey = (typeof FLOATING_POSITIONER_KEYS)[number]
type PortalKey = (typeof FLOATING_PORTAL_KEYS)[number]

/**
 * Flat positioning/portal props + typed escape hatches, derived from a
 * component's own Positioner and Portal prop types so each *Content stays in
 * lockstep with Base UI. Intersect with the Popup props to build a *Content
 * prop type:
 *
 * ```ts
 * type PopoverContentProps = React.ComponentProps<typeof BasePopover.Popup> &
 *   FloatingContentProps<
 *     React.ComponentProps<typeof BasePopover.Positioner>,
 *     React.ComponentProps<typeof BasePopover.Portal>
 *   > & { arrow?: boolean }
 * ```
 */
export type FloatingContentProps<Positioner, Portal> = Pick<Positioner, Extract<keyof Positioner, PositionerKey>> &
  Pick<Portal, Extract<keyof Portal, PortalKey>> & {
    /** Escape hatch: extra props forwarded to the Base UI Positioner (e.g. `style`, `render`). */
    positionerProps?: Omit<Positioner, PositionerKey | 'children'>
    /** Escape hatch: extra props forwarded to the Base UI Portal (e.g. `style`, `render`). */
    portalProps?: Omit<Portal, PortalKey | 'children'>
  }

export interface SplitFloatingProps {
  positioner: Record<string, unknown>
  portal: Record<string, unknown>
  popup: Record<string, unknown>
}

/**
 * Partition a *Content component's spread props into its three Base UI targets.
 *
 * - Flat positioning/portal props win over the same keys inside
 *   `positionerProps`/`portalProps` (the flat prop is the documented primary API).
 * - Anything left that isn't a known Positioner/Portal prop is treated as a Popup prop.
 *
 * Destructure `className`/`children` (and any component-specific props) out of the
 * props object before calling this - they should not reach the generic Popup spread.
 */
export function splitFloatingProps(props: Record<string, unknown>): SplitFloatingProps {
  const { positionerProps, portalProps, ...rest } = props as {
    positionerProps?: Record<string, unknown>
    portalProps?: Record<string, unknown>
  } & Record<string, unknown>

  const positioner: Record<string, unknown> = { ...positionerProps }
  const portal: Record<string, unknown> = { ...portalProps }
  const popup: Record<string, unknown> = {}

  for (const key of Object.keys(rest)) {
    const value = rest[key]
    if ((FLOATING_POSITIONER_KEYS as readonly string[]).includes(key)) {
      if (value !== undefined) positioner[key] = value
    } else if ((FLOATING_PORTAL_KEYS as readonly string[]).includes(key)) {
      if (value !== undefined) portal[key] = value
    } else {
      popup[key] = value
    }
  }

  return { positioner, portal, popup }
}
