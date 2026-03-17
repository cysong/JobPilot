import { useListReturnRestore } from "@/hooks/useListReturnRestore";

const JOB_LIST_POSITIONS_KEY = "jobs:list:positions";
const JOB_LIST_RETURN_INTENT_KEY = "jobs:list:return-intent";
const JOB_LIST_ORDERS_KEY = "jobs:list:orders";

type UseJobListReturnRestoreOptions = {
  contextKey: string;
  isSearchParamsReady: boolean;
  isLoading: boolean;
  isError: boolean;
  itemIds: number[];
};

export const useJobListReturnRestore = ({
  contextKey,
  isSearchParamsReady,
  isLoading,
  isError,
  itemIds,
}: UseJobListReturnRestoreOptions) => {
  const { highlightedItemId, handleOpenItem } = useListReturnRestore<number>({
    contextKey,
    isSearchParamsReady,
    isLoading,
    isError,
    itemIds,
    positionsStorageKey: JOB_LIST_POSITIONS_KEY,
    returnIntentStorageKey: JOB_LIST_RETURN_INTENT_KEY,
    ordersStorageKey: JOB_LIST_ORDERS_KEY,
    itemSelector: (jobId) => `[data-job-id="${jobId}"]`,
  });

  return {
    highlightedJobId: highlightedItemId,
    handleOpenJob: handleOpenItem,
  };
};
