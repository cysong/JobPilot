/**
 * Source metadata API client.
 */
import apiClient from './client'
import type { SourceMeta } from '@/types/sourceMeta'

export const sourceMetaApi = {
  /**
   * List display metadata for all known job sources.
   */
  list: async (): Promise<SourceMeta[]> => {
    return apiClient.get<SourceMeta[], SourceMeta[]>('/jobs/sources/meta')
  },
}
