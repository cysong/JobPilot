import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import { usePersistedListSearchParams } from '@/hooks/usePersistedListSearchParams'
import { clearSessionStorageKeys, getListContextKey } from '@/utils/listState'
import { cloneSearchParams, setOptionalSearchParam } from '@/utils/searchParams'
import type { ApplicationResolution, ApplicationStatus, ApplicationStatusGroup } from '@/types/application'

const APPLICATION_LIST_POSITIONS_KEY = 'applications:list:positions'
const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'
const APPLICATION_LIST_SEARCH_SNAPSHOT_KEY = 'applications:list:search-snapshot'
const APPLICATION_TRACKED_SEARCH_KEYS = ['page', 'page_size', 'keyword', 'status', 'status_group', 'resolution']

export const useApplicationListState = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentPage = parseInt(searchParams.get('page') || '1')
  const pageSize = parseInt(searchParams.get('page_size') || '20')
  const keywordParam = searchParams.get('keyword') || ''
  const statusParam = (searchParams.get('status') as ApplicationStatus | null) || null
  const statusGroupParam = (searchParams.get('status_group') as ApplicationStatusGroup | null) || null
  const resolutionParam = (searchParams.get('resolution') as ApplicationResolution | null) || null
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

  const updateSearchParams = (next: {
    keyword?: string
    status?: string | null
    statusGroup?: string | null
    resolution?: string | null
    page?: number
  }) => {
    const newParams = cloneSearchParams(searchParams)
    const nextKeyword = next.keyword ?? keywordParam
    const nextStatus = next.status === undefined ? statusParam : next.status
    const nextStatusGroup = next.statusGroup === undefined ? statusGroupParam : next.statusGroup
    const nextResolution = next.resolution === undefined ? resolutionParam : next.resolution
    const nextPage = next.page ?? 1

    setOptionalSearchParam(newParams, 'keyword', nextKeyword)
    setOptionalSearchParam(newParams, 'status', nextStatus)
    setOptionalSearchParam(newParams, 'status_group', nextStatusGroup)
    setOptionalSearchParam(newParams, 'resolution', nextResolution)

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
    if (value === 'in_progress') {
      updateSearchParams({ status: null, statusGroup: 'in_progress', page: 1 })
      return
    }
    updateSearchParams({
      status: value === 'all' ? null : value,
      statusGroup: null,
      page: 1,
    })
  }

  const handleResolutionChange = (value: string) => {
    updateSearchParams({ resolution: value === 'ACTIVE' ? null : value, page: 1 })
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
    statusGroupParam,
    resolutionParam,
    contextKey,
    keyword,
    setKeyword,
    isSearchParamsReady,
    handleSearch,
    handleClearSearch,
    handleStatusChange,
    handleResolutionChange,
    handleReset,
    updateSearchParams,
  }
}
