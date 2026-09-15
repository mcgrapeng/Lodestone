'use client'

import { useCallback, useMemo } from 'react'
import { useStorage, type StorageBackend } from './use-local-storage'

export interface UseDismissibleOptions {
  /** Which Web Storage area the dismissal is persisted to. */
  storage?: StorageBackend
}

export interface UseDismissibleReturn {
  /** Whether the surface should show (`true` until dismissed) */
  open: boolean
  /** Mark it dismissed and persist that */
  dismiss: () => void
  /** Clear the dismissal so it shows again */
  reset: () => void
}

/**
 * Tracks whether a dismissible surface (banner, callout, etc.) should still be
 * shown, persisting the dismissal under `key`. SSR-safe (`open` is `true` until
 * the stored value is known) and synced across tabs and components.
 */
export function useDismissible(key: string, { storage = 'local' }: UseDismissibleOptions = {}): UseDismissibleReturn {
  // Raw string flag ('1' = dismissed); empty/default means open.
  const [flag, setFlag, removeFlag] = useStorage<string>(storage, key, '', {
    serializer: (v) => v,
    deserializer: (v) => v,
  })

  const open = flag !== '1'
  const dismiss = useCallback(() => setFlag('1'), [setFlag])
  const reset = useCallback(() => removeFlag(), [removeFlag])

  return useMemo(() => ({ open, dismiss, reset }), [open, dismiss, reset])
}
