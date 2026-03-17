import { useEffect, useRef, useState } from "react";

import {
  readSessionRecord,
  type ListOrderState,
  type ListPositionState,
  type ListReturnIntent,
  writeSessionRecord,
} from "@/utils/listState";

const JOB_LIST_POSITIONS_KEY = "jobs:list:positions";
const JOB_LIST_RETURN_INTENT_KEY = "jobs:list:return-intent";
const JOB_LIST_ORDERS_KEY = "jobs:list:orders";
const RESTORE_HIGHLIGHT_MS = 2000;

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
  const [highlightedJobId, setHighlightedJobId] = useState<number | null>(null);
  const previousContextKey = useRef<string | null>(null);

  const handleOpenJob = (jobId: number) => {
    const positions = readSessionRecord<ListPositionState<number>>(JOB_LIST_POSITIONS_KEY);
    positions[contextKey] = {
      anchorItemId: jobId,
      scrollY: window.scrollY,
      updatedAt: Date.now(),
    };
    writeSessionRecord(JOB_LIST_POSITIONS_KEY, positions);
  };

  useEffect(() => {
    if (previousContextKey.current && previousContextKey.current !== contextKey) {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
    previousContextKey.current = contextKey;
  }, [contextKey]);

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return;

    const intentMap = readSessionRecord<ListReturnIntent<number>>(JOB_LIST_RETURN_INTENT_KEY);
    const intent = intentMap.current || null;
    if (!intent || intent.contextKey !== contextKey) {
      return;
    }

    sessionStorage.removeItem(JOB_LIST_RETURN_INTENT_KEY);

    const positions = readSessionRecord<ListPositionState<number>>(JOB_LIST_POSITIONS_KEY);
    const position = positions[contextKey];
    const targetJobId = intent.itemId || position?.anchorItemId;
    if (!targetJobId) return;

    requestAnimationFrame(() => {
      const anchorElement = document.querySelector(`[data-job-id="${targetJobId}"]`);
      if (anchorElement instanceof HTMLElement) {
        anchorElement.scrollIntoView({ block: "center", behavior: "auto" });
      } else if (position?.scrollY !== undefined) {
        window.scrollTo({ top: position.scrollY, behavior: "auto" });
      }
      setHighlightedJobId(targetJobId);
      window.setTimeout(() => setHighlightedJobId(null), RESTORE_HIGHLIGHT_MS);
    });
  }, [contextKey, isError, isLoading, isSearchParamsReady]);

  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return;

    const orders = readSessionRecord<ListOrderState<number>>(JOB_LIST_ORDERS_KEY);
    orders[contextKey] = {
      itemIds,
      updatedAt: Date.now(),
    };
    writeSessionRecord(JOB_LIST_ORDERS_KEY, orders);
  }, [contextKey, isError, isLoading, isSearchParamsReady, itemIds]);

  return {
    highlightedJobId,
    handleOpenJob,
  };
};
