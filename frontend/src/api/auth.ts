/**
 * Authentication API client
 */
import apiClient from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '@/types/auth'

export const authApi = {
  /**
   * Register a new user account
   */
  register: async (data: RegisterRequest): Promise<User> => {
    const result = await apiClient.post<User, User>('/auth/register', data)
    return result
  },

  /**
   * Login with email and password
   */
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const result = await apiClient.post<TokenResponse, TokenResponse>('/auth/login', data)
    return result
  },

  /**
   * Get current authenticated user information
   */
  getCurrentUser: async (): Promise<User> => {
    const result = await apiClient.get<User, User>('/auth/me')
    return result
  },
}
