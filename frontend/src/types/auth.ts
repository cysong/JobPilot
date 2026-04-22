/**
 * Authentication related TypeScript types
 */

export const Role = {
  USER: 'USER',
  VIP: 'VIP',
  ADMIN: 'ADMIN',
} as const

export type Role = (typeof Role)[keyof typeof Role]

export interface SalaryExpectation {
  mode: 'exact' | 'range'
  currency: 'NZD'
  period: 'yearly'
  min: number | null
  max: number | null
  value: number | null
}

export interface UserPreferences {
  default_tailoring_level?: 'light' | 'moderate' | 'deep' | null
  job_locations?: string[]
  salary_expectation?: SalaryExpectation | null
}

export interface User {
  id: number
  email: string
  full_name: string
  avatar_seed?: string | null
  role: Role
  is_active: boolean
  email_verified_at?: string | null
  password_changed_at?: string | null
  preferences?: UserPreferences
  created_at: string
  updated_at: string
}

export interface UserProfileUpdateRequest {
  full_name?: string
  avatar_seed?: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

export interface VerifyTokenRequest {
  token: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ChangeEmailRequest {
  new_email: string
  current_password: string
}

export interface MessageResponse {
  message: string
}
