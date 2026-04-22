import type { User } from '@/types/auth'

const DICEBEAR_BASE = 'https://api.dicebear.com/9.x/icons/svg'

export function getAvatarUrl(user?: User | null, fallbackSeed = 'User'): string {
  const seed = user?.avatar_seed?.trim() || user?.email || fallbackSeed
  return `${DICEBEAR_BASE}?seed=${encodeURIComponent(seed)}`
}

export function randomAvatarSeed(): string {
  return Math.random().toString(36).slice(2, 12)
}
