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
}
