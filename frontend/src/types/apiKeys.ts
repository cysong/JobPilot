/**
 * API Key types mirroring backend schemas in app/modules/api_keys/schemas.py.
 */

export interface ApiKey {
  id: string
  name: string
  prefix: string
  scopes: string[]
  last_used_at: string | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  /** Full plaintext key. Only returned once at creation. */
  plaintext: string
}

export interface ApiKeyCreateRequest {
  name: string
  expires_at?: string | null
  /** Admin-only scopes, e.g. 'matching:labels'. */
  scopes?: string[]
}

/** Scopes an admin can grant (mirrors backend app/modules/auth/scopes.py). */
export const ADMIN_API_KEY_SCOPES: { value: string; label: string }[] = [
  { value: 'matching:labels', label: 'Submit match calibration labels' },
]
