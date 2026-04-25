/**
 * API Key management client.
 */
import apiClient from './client'
import type { ApiKey, ApiKeyCreateRequest, ApiKeyCreated } from '@/types/apiKeys'

export const apiKeysApi = {
  list: async (): Promise<ApiKey[]> => {
    return apiClient.get<ApiKey[], ApiKey[]>('/api-keys')
  },

  create: async (data: ApiKeyCreateRequest): Promise<ApiKeyCreated> => {
    return apiClient.post<ApiKeyCreated, ApiKeyCreated>('/api-keys', data)
  },

  revoke: async (id: string): Promise<void> => {
    await apiClient.delete<void, void>(`/api-keys/${id}`)
  },
}
