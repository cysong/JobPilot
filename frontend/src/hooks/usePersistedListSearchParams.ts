import { useCallback, useEffect, useMemo, useState } from 'react'
import type { SetURLSearchParams } from 'react-router-dom'

type PersistedListSearchParamsOptions = {
  searchParams: URLSearchParams
  setSearchParams: SetURLSearchParams
  storageKey: string
  trackedKeys: string[]
  ttlMs?: number
}

type PersistedSearchSnapshot = {
  version: number
  updatedAt: number
  params: Array<[string, string]>
}

const SNAPSHOT_VERSION = 1
const DEFAULT_TTL_MS = 1000 * 60 * 60 * 24

const readSnapshot = (storageKey: string, ttlMs: number): PersistedSearchSnapshot | null => {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return null

    const snapshot = JSON.parse(raw) as PersistedSearchSnapshot
    const isExpired = Date.now() - snapshot.updatedAt > ttlMs
    const isInvalid =
      snapshot.version !== SNAPSHOT_VERSION ||
      !Array.isArray(snapshot.params) ||
      typeof snapshot.updatedAt !== 'number'

    if (isExpired || isInvalid) {
      localStorage.removeItem(storageKey)
      return null
    }

    return snapshot
  } catch {
    localStorage.removeItem(storageKey)
    return null
  }
}

export const usePersistedListSearchParams = ({
  searchParams,
  setSearchParams,
  storageKey,
  trackedKeys,
  ttlMs = DEFAULT_TTL_MS,
}: PersistedListSearchParamsOptions) => {
  const [isSearchParamsReady, setIsSearchParamsReady] = useState(false)

  const trackedEntries = useMemo(
    () => trackedKeys.flatMap((key) => searchParams.getAll(key).map((value) => [key, value] as [string, string])),
    [searchParams, trackedKeys],
  )

  useEffect(() => {
    if (trackedEntries.length > 0) {
      setIsSearchParamsReady(true)
      return
    }

    const snapshot = readSnapshot(storageKey, ttlMs)
    if (!snapshot || snapshot.params.length === 0) {
      setIsSearchParamsReady(true)
      return
    }

    const nextParams = new URLSearchParams(searchParams)
    snapshot.params.forEach(([key, value]) => nextParams.append(key, value))
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams, storageKey, trackedEntries, ttlMs])

  useEffect(() => {
    if (!isSearchParamsReady) return

    if (trackedEntries.length === 0) {
      localStorage.removeItem(storageKey)
      return
    }

    const snapshot: PersistedSearchSnapshot = {
      version: SNAPSHOT_VERSION,
      updatedAt: Date.now(),
      params: trackedEntries,
    }
    localStorage.setItem(storageKey, JSON.stringify(snapshot))
  }, [isSearchParamsReady, storageKey, trackedEntries])

  const clearPersistedSearchParams = useCallback(() => {
    localStorage.removeItem(storageKey)
  }, [storageKey])

  return {
    isSearchParamsReady,
    clearPersistedSearchParams,
  }
}
