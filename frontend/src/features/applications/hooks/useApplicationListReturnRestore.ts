import { useEffect, useRef, useState } from 'react'

import {
  readSessionRecord,
  type ListOrderState,
  type ListPositionState,
  type ListReturnIntent,
  writeSessionRecord,
} from '@/utils/listState'

const APPLICATION_LIST_POSITIONS_KEY = 'applications:list:positions'
const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'
const RESTORE_HIGHLIGHT_MS = 2000

type UseApplicationListReturnRestoreOptions = {
  contextKey: string
  isSearchParamsReady: boolean
  isLoading: boolean
  isError: boolean
  itemIds: string[]
}

export const useApplicationListReturnRestore = ({
  contextKey,
  isSearchParamsReady,
  isLoading,
  isError,
  itemIds,
}: UseApplicationListReturnRestoreOptions) => {
  const [highlightedApplicationId, setHighlightedApplicationId] = useState<string | null>(null)
  const previousContextKey = useRef<string | null>(null)

  const handleOpenApplication = (applicationId: string) => {
    const positions = readSessionRecord<ListPositionState<string>>(APPLICATION_LIST_POSITIONS_KEY)
    positions[contextKey] = {
      anchorItemId: applicationId,
      scrollY: window.scrollY,
      updatedAt: Date.now(),
    }
    writeSessionRecord(APPLICATION_LIST_POSITIONS_KEY, positions)
  }

  useEffect(() => {
    if (previousContextKey.current && previousContextKey.current !== contextKey) {
      window.scrollTo({ top: 0, behavior: 'auto' })
    }
    previousContextKey.current = contextKey
  }, [contextKey])

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return

    const intentMap = readSessionRecord<ListReturnIntent<string>>(APPLICATION_LIST_RETURN_INTENT_KEY)
    const intent = intentMap.current || null
    if (!intent || intent.contextKey !== contextKey) {
      return
    }

    sessionStorage.removeItem(APPLICATION_LIST_RETURN_INTENT_KEY)

    const positions = readSessionRecord<ListPositionState<string>>(APPLICATION_LIST_POSITIONS_KEY)
    const position = positions[contextKey]
    const targetApplicationId = intent.itemId || position?.anchorItemId
    if (!targetApplicationId) return

    requestAnimationFrame(() => {
      const anchorElement = document.querySelector(`[data-application-id="${targetApplicationId}"]`)
      if (anchorElement instanceof HTMLElement) {
        anchorElement.scrollIntoView({ block: 'center', behavior: 'auto' })
      } else if (position?.scrollY !== undefined) {
        window.scrollTo({ top: position.scrollY, behavior: 'auto' })
      }
      setHighlightedApplicationId(targetApplicationId)
      window.setTimeout(() => setHighlightedApplicationId(null), RESTORE_HIGHLIGHT_MS)
    })
  }, [contextKey, isError, isLoading, isSearchParamsReady])

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return

    const orders = readSessionRecord<ListOrderState<string>>(APPLICATION_LIST_ORDERS_KEY)
    orders[contextKey] = {
      itemIds,
      updatedAt: Date.now(),
    }
    writeSessionRecord(APPLICATION_LIST_ORDERS_KEY, orders)
  }, [contextKey, isError, isLoading, isSearchParamsReady, itemIds])

  return {
    highlightedApplicationId,
    handleOpenApplication,
  }
}
