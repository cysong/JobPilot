/**
 * Authentication related TypeScript types
 */

export const Role = {
  USER: 'USER',
  VIP: 'VIP',
  ADMIN: 'ADMIN',
} as const

export type Role = (typeof Role)[keyof typeof Role]

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
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
