'use client'

import { useCallback, useRef, useSyncExternalStore } from 'react'

export type StorageBackend = 'local' | 'session'

export interface UseStorageOptions<T> {
  /** Serialize a value to its stored string form. Defaults to `JSON.stringify`. */
  serializer?: (value: T) => string
  /** Parse the stored string back into a value. Defaults to `JSON.parse`. */
  deserializer?: (raw: string) => T
}

export type UseStorageReturn<T> = readonly [T, (value: T | ((prev: T) => T)) => void, () => void]

// Same-tab fan-out: the `storage` event only fires in *other* tabs, so we keep a
// per-backend, per-key registry to sync components within the current tab.
const registries: Record<StorageBackend, Map<string, Set<() => void>>> = {
  local: new Map(),
  session: new Map(),
}

function subscribers(backend: StorageBackend, key: string) {
  const reg = registries[backend]
  let set = reg.get(key)
  if (!set) {
    set = new Set()
    reg.set(key, set)
  }
  return set
}

function notify(backend: StorageBackend, key: string) {
  registries[backend].get(key)?.forEach((cb) => cb())
}

function getStore(backend: StorageBackend): Storage | null {
  try {
    return backend === 'session' ? window.sessionStorage : window.localStorage
  } catch {
    // SSR, privacy mode, or disabled storage.
    return null
  }
}

// A single `storage` listener shared by every hook instance - installed at the
// first subscriber, removed at zero - dispatching through the registries above.
let globalListenerCount = 0

function handleGlobalStorage(e: StorageEvent) {
  for (const backend of ['local', 'session'] as StorageBackend[]) {
    const store = getStore(backend)
    if (e.storageArea && store && e.storageArea !== store) continue
    if (e.key === null) {
      // storage.clear() invalidates every key in this backend.
      registries[backend].forEach((set) => set.forEach((cb) => cb()))
    } else {
      registries[backend].get(e.key)?.forEach((cb) => cb())
    }
  }
}

function addGlobalStorageListener() {
  if (globalListenerCount === 0 && typeof window !== 'undefined') {
    window.addEventListener('storage', handleGlobalStorage)
  }
  globalListenerCount++
}

function removeGlobalStorageListener() {
  globalListenerCount--
  if (globalListenerCount === 0 && typeof window !== 'undefined') {
    window.removeEventListener('storage', handleGlobalStorage)
  }
}

// Cache parsed values keyed by `backend:key`, invalidated by the raw string.
// Without this, `JSON.parse` in the snapshot would return a fresh object every
// render and drive `useSyncExternalStore` into an infinite loop.
const parseCache = new Map<string, { raw: string; value: unknown }>()

/**
 * SSR-safe `localStorage`/`sessionStorage` hook. Reads via `useSyncExternalStore`
 * (server and first client render return `defaultValue`), syncs across tabs via
 * the `storage` event, and syncs other components in the same tab via an internal
 * registry. Returns `[value, setValue, remove]`.
 *
 * Values are JSON-serialized by default; pass a `serializer`/`deserializer` to
 * store raw strings (e.g. a theme name the no-flash script reads directly).
 *
 * Prefer the `useLocalStorage` / `useSessionStorage` wrappers unless the backend
 * is chosen at runtime.
 */
export function useStorage<T>(
  backend: StorageBackend,
  key: string,
  defaultValue: T,
  options: UseStorageOptions<T> = {},
): UseStorageReturn<T> {
  // Stabilize so subscribe/snapshot identities depend only on backend+key.
  const defaultRef = useRef(defaultValue)
  const serializeRef = useRef(options.serializer)
  const deserializeRef = useRef(options.deserializer)
  serializeRef.current = options.serializer
  deserializeRef.current = options.deserializer

  const read = useCallback((): T => {
    // An empty key means "no persistence" - behave like storage is unavailable
    // instead of touching `getItem('')` and registering a listener.
    if (!key) return defaultRef.current
    const store = getStore(backend)
    let raw: string | null = null
    try {
      raw = store?.getItem(key) ?? null
    } catch {
      raw = null
    }
    if (raw === null) return defaultRef.current

    const id = backend + ':' + key
    const cached = parseCache.get(id)
    if (cached && cached.raw === raw) return cached.value as T

    let value: T
    try {
      value = deserializeRef.current ? deserializeRef.current(raw) : (JSON.parse(raw) as T)
    } catch {
      value = defaultRef.current
    }
    parseCache.set(id, { raw, value })
    return value
  }, [backend, key])

  const subscribe = useCallback(
    (onChange: () => void) => {
      if (!key) return () => {}
      const set = subscribers(backend, key)
      set.add(onChange)
      addGlobalStorageListener()
      return () => {
        set.delete(onChange)
        removeGlobalStorageListener()
      }
    },
    [backend, key],
  )

  const getServerSnapshot = useCallback(() => defaultRef.current, [])

  const value = useSyncExternalStore(subscribe, read, getServerSnapshot)

  const setValue = useCallback(
    (update: T | ((prev: T) => T)) => {
      if (!key) return
      const next = typeof update === 'function' ? (update as (prev: T) => T)(read()) : update
      try {
        const raw = serializeRef.current ? serializeRef.current(next) : JSON.stringify(next)
        getStore(backend)?.setItem(key, raw)
      } catch {
        // ignore write failures (quota, privacy mode, SSR)
      }
      notify(backend, key)
    },
    [backend, key, read],
  )

  const remove = useCallback(() => {
    if (!key) return
    try {
      getStore(backend)?.removeItem(key)
    } catch {
      // ignore
    }
    notify(backend, key)
  }, [backend, key])

  return [value, setValue, remove] as const
}

export function useLocalStorage<T>(key: string, defaultValue: T, options?: UseStorageOptions<T>): UseStorageReturn<T> {
  return useStorage('local', key, defaultValue, options)
}

export function useSessionStorage<T>(
  key: string,
  defaultValue: T,
  options?: UseStorageOptions<T>,
): UseStorageReturn<T> {
  return useStorage('session', key, defaultValue, options)
}
