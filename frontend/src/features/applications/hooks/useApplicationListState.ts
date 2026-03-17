import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import { usePersistedListSearchParams } from '@/hooks/usePersistedListSearchParams'
import { clearSessionStorageKeys, getListContextKey } from '@/utils/listState'
import { cloneSearchParams, setOptionalSearchParam } from '@/utils/searchParams'
import type { ApplicationStatus } from '@/types/application'

const APPLICATION_LIST_POSITIONS_KEY = 'applications:list:positions'
const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'
const APPLICATION_LIST_SEARCH_SNAPSHOT_KEY = 'applications:list:search-snapshot'
const APPLICATION_TRACKED_SEARCH_KEYS = ['page', 'page_size', 'keyword', 'status']

export const useApplicationListState = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentPage = parseInt(searchParams.get('page') || '1')
  const pageSize = parseInt(searchParams.get('page_size') || '20')
  const keywordParam = searchParams.get('keyword') || ''
  const statusParam = (searchParams.get('status') as ApplicationStatus | null) || null
  const contextKey = getListContextKey('applications:list', searchParams)
  const [keyword, setKeyword] = useState(keywordParam)
  const { isSearchParamsReady, clearPersistedSearchParams } = usePersistedListSearchParams({
    searchParams,
    setSearchParams,
    storageKey: APPLICATION_LIST_SEARCH_SNAPSHOT_KEY,
    trackedKeys: APPLICATION_TRACKED_SEARCH_KEYS,
  })

  useEffect(() => {
    setKeyword(keywordParam)
  }, [keywordParam])

  const updateSearchParams = (next: { keyword?: string; status?: string | null; page?: number }) => {
    const newParams = cloneSearchParams(searchParams)
    const nextKeyword = next.keyword ?? keywordParam
    const nextStatus = next.status === undefined ? statusParam : next.status
    const nextPage = next.page ?? 1

    setOptionalSearchParam(newParams, 'keyword', nextKeyword)
    setOptionalSearchParam(newParams, 'status', nextStatus)

    newParams.set('page', nextPage.toString())
    newParams.set('page_size', pageSize.toString())
    setSearchParams(newParams)
  }

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    updateSearchParams({ keyword, page: 1 })
  }

  const handleClearSearch = () => {
    setKeyword('')
    updateSearchParams({ keyword: '', page: 1 })
  }

  const handleStatusChange = (value: string) => {
    updateSearchParams({ status: value === 'all' ? null : value, page: 1 })
  }

  const handleReset = () => {
    clearPersistedSearchParams()
    setKeyword('')
    clearSessionStorageKeys([
      APPLICATION_LIST_POSITIONS_KEY,
      APPLICATION_LIST_RETURN_INTENT_KEY,
      APPLICATION_LIST_ORDERS_KEY,
    ])
    setSearchParams(new URLSearchParams(), { replace: true })
  }

  return {
    searchParams,
    currentPage,
    pageSize,
    keywordParam,
    statusParam,
    contextKey,
    keyword,
    setKeyword,
    isSearchParamsReady,
    handleSearch,
    handleClearSearch,
    handleStatusChange,
    handleReset,
    updateSearchParams,
  }
}
