/**
 * Job-related TypeScript types
 */

export interface Job {
  id: number
  source: string | null
  source_id: string
  title: string
  abstract: string | null

  // Salary
  salary_label: string | null

  // Work type
  work_types_label: string | null

  // Location
  location_label: string | null
  location_city: string | null
  country: string | null

  // Company
  advertiser_name: string | null
  company_name: string | null
  company_logo: string | null

  // Classification
  classification: string | null
  sub_classification: string | null

  // Dates
  listed_at: string | null
  expires_at: string | null

  // Status flags
  is_expired: boolean
  manual_expired?: boolean
  manual_expired_by?: number | null
  manual_expired_at?: string | null
  manual_expired_note?: string | null
  status: string | null

  // Share link
  share_link: string | null

  // User-specific metadata
  is_viewed?: boolean
  last_viewed_at?: string | null
  has_application?: boolean
}

export interface JobDetail extends Job {
  content: string | null
  content_cn: string | null

  // Contact info
  phone_number: string | null
  contact_phone: string | null
  contact_email: string | null

  // Work type details
  work_type_ids: string | null

  // Location details
  location_area: string | null
  location_ids: string | null
  country_code: string | null
  suburb: string | null
  region: string | null
  state: string | null
  postcode: string | null
  broader_location_name: string | null

  // Advertiser details
  advertiser_id: string | null
  advertiser_is_verified: boolean
  advertiser_registration_date: string | null
  is_private_advertiser: boolean

  // Classification details
  classification_id: string | null
  sub_classification_id: string | null
  classifications_label: string | null

  // Branding
  product_bullets: string | null
  branding_id: string | null
  branding_cover_url: string | null
  branding_thumbnail_url: string | null
  branding_logo_url: string | null
  display_tags: string | null

  // Company details
  company_profile_id: string | null
  company_slug: string | null
  company_description: string | null
  company_industry: string | null
  company_size: string | null
  company_website: string | null
  should_display_reviews: boolean

  // Normalized fields
  normalised_role_title: string | null
  normalised_organisation_name: string | null

  // Other metadata
  source_zone: string | null
  ad_product_type: string | null
  has_role_requirements: boolean
  restricted_application_label: string | null

  // Verification flags
  is_link_out: boolean
  is_verified: boolean

  // Timestamps
  created_at: string | null
  updated_at: string | null

  // Analysis
  analysis?: JobAnalysis | null
}

export interface JobListResponse {
  items: Job[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SavedJobStatusResponse {
  is_saved: boolean
  saved_at: string | null
}

export interface JobViewedStatusResponse {
  is_viewed: boolean
  first_viewed_at: string | null
  last_viewed_at: string | null
  view_count: number
}

export interface SavedJobListItem {
  job: Job
  saved_at: string
}

export interface SavedJobListResponse {
  items: SavedJobListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface JobFiltersRequest {
  // Search
  keyword?: string

  // Filters
  location_cities?: string[]
  work_types?: string[]
  companies?: string[]
  sources?: string[]
  view_status?: 'all' | 'viewed' | 'unviewed'

  // Date range
  listed_after?: string
  listed_before?: string

  // Expiration filter
  hide_expired?: boolean

  // Pagination
  page: number
  page_size: number

  // Sorting
  sort_by: string
  sort_order: 'asc' | 'desc'
}

export interface JobFiltersOptions {
  location_cities: string[]
  work_types: string[]
  companies: string[]
  sources: string[]
}

export interface JobAnalysis {
  id: string
  job_id: number

  // Skills
  required_skills: string[]
  preferred_skills: string[]
  certifications: string[]
  tech_stack: string[]

  // Responsibilities
  seniority: string | null
  key_responsibilities: string[]
  experience_years: string | null
  education_requirement: string | null

  // Soft Skills
  soft_skills: string[]
  company_culture_keywords: string[]

  // Insights
  hiring_priorities: string[]
  cn_content: string | null

  // Metadata
  analysis_version: string
  created_at: string
  updated_at: string
}

/**
 * Brief job info for match list
 */
export interface JobBriefInfo {
  id: number
  source: string | null
  title: string
  advertiser_name: string | null
  company_name: string | null
  location_label: string | null
  work_types_label: string | null
  salary_label: string | null
  listed_at: string | null
  is_expired?: boolean
  manual_expired?: boolean

  // Additional fields for UI completeness
  company_logo: string | null
  abstract: string | null
  classification: string | null
  sub_classification: string | null
  is_viewed?: boolean
  last_viewed_at?: string | null
  has_application?: boolean
}

/**
 * Brief resume info for matches
 */
export interface ResumeBriefInfo {
  id: string
  title: string
}

/**
 * Matching v3 (docs/job_matching_v3_design.md §3, §7)
 */
export type MatchTier = 'A' | 'B' | 'C' | 'D'
export type MatchView = 'recommended' | 'rejected'

export interface MatchLabelInfo {
  id: string
  label: string
  reason_tags: string[]
  note: string | null
  created_at: string
}

export interface MatchSummary {
  id: string
  status: string
  tier: MatchTier | null
  tier_reason: string | null
  tech_level: 'strong' | 'partial' | 'weak' | null
  experience_level: 'strong' | 'partial' | 'none' | null
  family_relation: 'same' | 'adjacent'
  location_check: 'not_applicable' | 'remote' | 'matched' | 'unknown' | 'rejected'
  reject_code: string | null
  reject_reason: string | null
  reject_quote: string | null
  judged_at: string | null
  recommended_resume: ResumeBriefInfo | null
  application_status: string | null
  label: MatchLabelInfo | null // admins only
}

export interface MatchListItem {
  job: JobBriefInfo
  match: MatchSummary
}

export interface MatchCounts {
  A: number
  B: number
  C: number
  rejected: number
  pending: number
}

export interface MatchListResponse {
  items: MatchListItem[]
  total: number
  counts: MatchCounts
}

export interface MatchEvidence {
  job_quote: string | null
  resume_quote: string | null
}

export interface MatchTechItem {
  requirement: string
  is_core: boolean
  relation: 'same' | 'substitute' | 'missing'
  evidence: MatchEvidence
}

export interface MatchConditionCheck {
  requirement?: string
  required_languages?: string[]
  country?: string | null
  quote: string | null
  satisfied: boolean | null
}

export interface MatchDetail extends MatchSummary {
  job_id: number
  tech_items: MatchTechItem[]
  relevant_years: number | null
  required_years: number | null
  experience_evidence: MatchEvidence[]
  work_rights: MatchConditionCheck | null
  security_clearance: MatchConditionCheck | null
  work_location: MatchConditionCheck | null
  languages: MatchConditionCheck | null
  other_constraints: { requirement: string; quote: string }[]
  seniority_mismatch: boolean | null
  is_different_track: boolean | null
  people_management: {
    required: boolean
    job_quote: string | null
    candidate_has: boolean
    resume_quote: string | null
  } | null
  /** The LLM's tier before code-level ceilings (set only when one applied). */
  llm_tier: MatchTier | null
  tier_adjustments: string[]
  model: string | null
  prompt_version: string | null
}

/**
 * Request params for job matches API
 */
export interface JobMatchFiltersRequest {
  view?: MatchView
  tiers?: MatchTier[]
  limit?: number
  offset?: number
}

export interface SavedJobsRequest {
  page: number
  page_size: number
}

export interface JobExpirationUpdateRequest {
  manual_expired: boolean
  note?: string
}

export interface JobExpirationStatusResponse {
  job_id: number
  is_expired: boolean
  manual_expired: boolean
  manual_expired_by: number | null
  manual_expired_at: string | null
  manual_expired_note: string | null
}

export interface EnqueueJobRequest {
  url: string
}

export interface EnqueueJobResponse {
  enqueued: boolean
  source?: string | null
  source_id?: string | null
  reason?: string | null
  existing_job_id?: number | null
}
