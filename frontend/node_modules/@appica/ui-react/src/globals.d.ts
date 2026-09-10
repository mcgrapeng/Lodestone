/**
 * Restores the legacy global `JSX` namespace that `@types/react@19` removed.
 *
 * React 19's types switched to `export namespace JSX` from `react/jsx-runtime`,
 * which TypeScript 5.1+ resolves via `"jsx": "react-jsx"`. IDE-bundled
 * TypeScript services often lag behind that resolution, surfacing spurious
 * "Property 'div' does not exist on type 'JSX.IntrinsicElements'" errors even
 * though `tsc` on the command line is clean. This ambient augmentation
 * proxies the global namespace back to `React.JSX` so the editor agrees with
 * the build.
 */

import type * as React from 'react'

declare global {
  // Minimal `process.env` typing for dev-only guards (`process.env.NODE_ENV`).
  // The package does not depend on `@types/node`; bundlers replace this at build time.
  // eslint-disable-next-line no-var
  var process: { env: Record<string, string | undefined> }

  namespace JSX {
    type ElementType = React.JSX.ElementType
    interface Element extends React.JSX.Element {}
    interface ElementClass extends React.JSX.ElementClass {}
    interface ElementAttributesProperty extends React.JSX.ElementAttributesProperty {}
    interface ElementChildrenAttribute extends React.JSX.ElementChildrenAttribute {}
    interface IntrinsicAttributes extends React.JSX.IntrinsicAttributes {}
    interface IntrinsicClassAttributes<T> extends React.JSX.IntrinsicClassAttributes<T> {}
    interface IntrinsicElements extends React.JSX.IntrinsicElements {}
    type LibraryManagedAttributes<C, P> = React.JSX.LibraryManagedAttributes<C, P>
  }
}

export {}
