/**
 * Authentication API client
 */
import apiClient from './client'
import type {
  ChangeEmailRequest,
  ChangePasswordRequest,
  ForgotPasswordRequest,
  LoginRequest,
  MessageResponse,
  RegisterRequest,
  ResetPasswordRequest,
  TokenResponse,
  User,
  VerifyTokenRequest,
} from '@/types/auth'

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

  forgotPassword: async (data: ForgotPasswordRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/forgot-password', data)
    return result
  },

  resetPassword: async (data: ResetPasswordRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/reset-password', data)
    return result
  },

  verifyEmail: async (data: VerifyTokenRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/verify-email', data)
    return result
  },

  resendVerificationEmail: async (): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/resend-verification-email')
    return result
  },

  changePassword: async (data: ChangePasswordRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/change-password', data)
    return result
  },

  requestEmailChange: async (data: ChangeEmailRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/change-email/request', data)
    return result
  },

  confirmEmailChange: async (data: VerifyTokenRequest): Promise<MessageResponse> => {
    const result = await apiClient.post<MessageResponse, MessageResponse>('/auth/change-email/confirm', data)
    return result
  },
}
