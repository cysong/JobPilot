import { useListReturnRestore } from '@/hooks/useListReturnRestore'

const APPLICATION_LIST_POSITIONS_KEY = 'applications:list:positions'
const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'

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
  const { highlightedItemId, handleOpenItem } = useListReturnRestore<string>({
    contextKey,
    isSearchParamsReady,
    isLoading,
    isError,
    itemIds,
    positionsStorageKey: APPLICATION_LIST_POSITIONS_KEY,
    returnIntentStorageKey: APPLICATION_LIST_RETURN_INTENT_KEY,
    ordersStorageKey: APPLICATION_LIST_ORDERS_KEY,
    itemSelector: (applicationId) => `[data-application-id="${applicationId}"]`,
  })

  return {
    highlightedApplicationId: highlightedItemId,
    handleOpenApplication: handleOpenItem,
  }
}
