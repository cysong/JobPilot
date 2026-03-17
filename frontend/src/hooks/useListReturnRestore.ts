import { useEffect, useRef, useState } from 'react'

import {
  readSessionRecord,
  type ListOrderState,
  type ListPositionState,
  type ListReturnIntent,
  writeSessionRecord,
} from '@/utils/listState'

type UseListReturnRestoreOptions<TId extends string | number> = {
  contextKey: string
  isSearchParamsReady: boolean
  isLoading: boolean
  isError: boolean
  itemIds: TId[]
  positionsStorageKey: string
  returnIntentStorageKey: string
  ordersStorageKey: string
  itemSelector: (itemId: TId) => string
  restoreHighlightMs?: number
}

export const useListReturnRestore = <TId extends string | number>({
  contextKey,
  isSearchParamsReady,
  isLoading,
  isError,
  itemIds,
  positionsStorageKey,
  returnIntentStorageKey,
  ordersStorageKey,
  itemSelector,
  restoreHighlightMs = 2000,
}: UseListReturnRestoreOptions<TId>) => {
  const [highlightedItemId, setHighlightedItemId] = useState<TId | null>(null)
  const previousContextKey = useRef<string | null>(null)

  const handleOpenItem = (itemId: TId) => {
    const positions = readSessionRecord<ListPositionState<TId>>(positionsStorageKey)
    positions[contextKey] = {
      anchorItemId: itemId,
      scrollY: window.scrollY,
      updatedAt: Date.now(),
    }
    writeSessionRecord(positionsStorageKey, positions)
  }

  useEffect(() => {
    if (previousContextKey.current && previousContextKey.current !== contextKey) {
      window.scrollTo({ top: 0, behavior: 'auto' })
    }
    previousContextKey.current = contextKey
  }, [contextKey])

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return

    const intentMap = readSessionRecord<ListReturnIntent<TId>>(returnIntentStorageKey)
    const intent = intentMap.current || null
    if (!intent || intent.contextKey !== contextKey) {
      return
    }

    sessionStorage.removeItem(returnIntentStorageKey)

    const positions = readSessionRecord<ListPositionState<TId>>(positionsStorageKey)
    const position = positions[contextKey]
    const targetItemId = intent.itemId || position?.anchorItemId
    if (!targetItemId) return

    requestAnimationFrame(() => {
      const anchorElement = document.querySelector(itemSelector(targetItemId))
      if (anchorElement instanceof HTMLElement) {
        anchorElement.scrollIntoView({ block: 'center', behavior: 'auto' })
      } else if (position?.scrollY !== undefined) {
        window.scrollTo({ top: position.scrollY, behavior: 'auto' })
      }
      setHighlightedItemId(targetItemId)
      window.setTimeout(() => setHighlightedItemId(null), restoreHighlightMs)
    })
  }, [
    contextKey,
    isError,
    isLoading,
    isSearchParamsReady,
    itemSelector,
    positionsStorageKey,
    restoreHighlightMs,
    returnIntentStorageKey,
  ])

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return

    const orders = readSessionRecord<ListOrderState<TId>>(ordersStorageKey)
    orders[contextKey] = {
      itemIds,
      updatedAt: Date.now(),
    }
    writeSessionRecord(ordersStorageKey, orders)
  }, [contextKey, isError, isLoading, isSearchParamsReady, itemIds, ordersStorageKey])

  return {
    highlightedItemId,
    handleOpenItem,
  }
}
