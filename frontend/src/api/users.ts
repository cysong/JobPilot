import apiClient from './client'
import type { UserPreferences } from '@/types/auth'

export const usersApi = {
  getProfilePreferences: async (): Promise<UserPreferences> => {
    const result = await apiClient.get<UserPreferences, UserPreferences>('/users/profile/preferences')
    return result
  },

  updateProfilePreferences: async (data: UserPreferences): Promise<UserPreferences> => {
    const result = await apiClient.patch<UserPreferences, UserPreferences>('/users/profile/preferences', data)
    return result
  },
}
