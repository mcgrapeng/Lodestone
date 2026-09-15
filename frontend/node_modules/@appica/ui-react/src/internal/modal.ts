// Shared plumbing for modal/overlay *Content components - the ones that wrap a
// Base UI Portal → Backdrop → Viewport → Popup structure (Dialog, AlertDialog,
// Drawer). Sibling to src/floating.ts (which handles the Positioner-based trio).
//
// As with floating, consumers don't get direct access to the inner Portal,
// Backdrop, or Viewport elements, so *Content must map them itself:
//
//   1. The two Portal props (`container`, `keepMounted`) are promoted to flat
//      props on *Content.
//   2. `portalProps` / `backdropProps` / `viewportProps` escape hatches forward
//      the rest (e.g. `className`, `style`, `render`) without each component
//      re-enumerating it.
//
// The Popup is what *Content represents, so its `className`/`style`/`render`
// stay bound to it (via the regular spread) - reach the other elements through
// the escape hatches.

/** Portal props promoted to flat props on every modal *Content. */
export const MODAL_PORTAL_KEYS = ['container', 'keepMounted'] as const

type ModalPortalKey = (typeof MODAL_PORTAL_KEYS)[number]

/**
 * Flat Portal props + typed escape hatches for the Backdrop/Viewport/Portal,
 * derived from a component's own Base UI types so each *Content stays in
 * lockstep with Base UI. Intersect with the Popup props to build a *Content
 * prop type:
 *
 * ```ts
 * type DialogContentProps = ModalContentProps<
 *   React.ComponentProps<typeof BaseDialog.Popup>,
 *   React.ComponentProps<typeof BaseDialog.Portal>,
 *   React.ComponentProps<typeof BaseDialog.Backdrop>,
 *   React.ComponentProps<typeof BaseDialog.Viewport>
 * > & { closeButton?: boolean }
 * ```
 */
export type ModalContentProps<Popup, Portal, Backdrop, Viewport> = Popup &
  Pick<Portal, Extract<keyof Portal, ModalPortalKey>> & {
    /** Escape hatch: extra props forwarded to the Base UI Portal. */
    portalProps?: Omit<Portal, ModalPortalKey | 'children'>
    /** Escape hatch: props forwarded to the Base UI Backdrop (e.g. `className`, `style`, `render`). */
    backdropProps?: Omit<Backdrop, 'children'>
    /** Escape hatch: props forwarded to the Base UI Viewport (e.g. `className`, `style`, `render`). */
    viewportProps?: Omit<Viewport, 'children'>
  }

export interface SplitModalProps {
  portal: Record<string, unknown>
  popup: Record<string, unknown>
}

/**
 * Partition a modal *Content component's spread props into the Portal and Popup
 * targets. Flat portal props win over the same keys inside `portalProps`.
 *
 * Destructure `className`/`children`, the `backdropProps`/`viewportProps` escape
 * hatches, and any component-specific props (`backdrop`, `closeButton`, …) out of
 * the props object before calling this - everything left that isn't a known
 * Portal prop is treated as a Popup prop.
 */
export function splitModalProps(props: Record<string, unknown>): SplitModalProps {
  const { portalProps, ...rest } = props as {
    portalProps?: Record<string, unknown>
  } & Record<string, unknown>

  const portal: Record<string, unknown> = { ...portalProps }
  const popup: Record<string, unknown> = {}

  for (const key of Object.keys(rest)) {
    const value = rest[key]
    if ((MODAL_PORTAL_KEYS as readonly string[]).includes(key)) {
      if (value !== undefined) portal[key] = value
    } else {
      popup[key] = value
    }
  }

  return { portal, popup }
}
