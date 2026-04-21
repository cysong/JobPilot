/**
 * Display metadata for a job source.
 *
 * Served by GET /api/v1/jobs/sources/meta. The backend owns labels, brand
 * colors, and behavior flags; the icon asset itself is bundled in the
 * frontend and looked up by `key` in `src/config/sourceIcons.ts`.
 */
export interface SourceMeta {
  key: string
  label: string
  brand_color: string | null
  external_apply: boolean
  enabled: boolean
}
