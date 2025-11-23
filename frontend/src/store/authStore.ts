/**
 * Authentication Zustand store with persistence
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/auth'
import { authApi } from '@/api/auth'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  setUser: (user: User) => void
  setToken: (token: string) => void
  login: (token: string, user: User) => void
  logout: () => void
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: true,
        }),

      setToken: (token) => {
        localStorage.setItem('access_token', token)
        set({ token })
      },

      login: (token, user) => {
        localStorage.setItem('access_token', token)
        set({
          token,
          user,
          isAuthenticated: true,
          isLoading: false,
        })
      },

      logout: () => {
        localStorage.removeItem('access_token')
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
        })
      },

      initialize: async () => {
        const token = localStorage.getItem('access_token')

        if (!token) {
          set({ isLoading: false, isAuthenticated: false })
          return
        }

        try {
          const user = await authApi.getCurrentUser()
          set({
            user,
            token,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (error) {
          // Token invalid or expired
          localStorage.removeItem('access_token')
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
          })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
