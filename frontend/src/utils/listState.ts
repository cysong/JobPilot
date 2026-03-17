export type ListPositionState<TId> = {
  anchorItemId: TId
  scrollY: number
  updatedAt: number
}

export type ListOrderState<TId> = {
  itemIds: TId[]
  updatedAt: number
}

export type ListReturnIntent<TId> = {
  contextKey: string
  itemId: TId
}

export const normalizeSearchParams = (params: URLSearchParams): string => {
  const entries = Array.from(params.entries()).sort(([aKey, aVal], [bKey, bVal]) => {
    if (aKey === bKey) return aVal.localeCompare(bVal)
    return aKey.localeCompare(bKey)
  })
  return entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
}

export const getListContextKey = (scope: string, params: URLSearchParams): string => {
  return `${scope}:${normalizeSearchParams(params)}`
}

export const readSessionRecord = <T>(storageKey: string): Record<string, T> => {
  try {
    const raw = sessionStorage.getItem(storageKey)
    return raw ? (JSON.parse(raw) as Record<string, T>) : {}
  } catch {
    return {}
  }
}

export const writeSessionRecord = <T>(storageKey: string, value: Record<string, T>) => {
  sessionStorage.setItem(storageKey, JSON.stringify(value))
}

export const clearSessionStorageKeys = (storageKeys: string[]) => {
  storageKeys.forEach((storageKey) => sessionStorage.removeItem(storageKey))
}
