export type ApplicationStatus =
    | 'PENDING'
    | 'TAILORING'
    | 'READY'
    | 'APPLIED'
    | 'PHONE_SCREEN'
    | 'INTERVIEWING'
    | 'OFFER'
    | 'REJECTED'
    | 'FAILED';

export type ApplicationResolution =
    | 'ACTIVE'
    | 'JOB_CLOSED'
    | 'USER_SKIPPED'
    | 'STALE_NO_RESPONSE';

export type ApplicationStatusGroup = 'in_progress'

export type TailoringLevel = 'light' | 'moderate' | 'deep'

export interface Application {
    id: string;
    user_id: string;
    job_id: number;
    status: ApplicationStatus;
    resolution: ApplicationResolution;
    source_resume_id: string;
    resume_document_id?: string;
    cover_letter_document_id?: string;
    tailoring_level: TailoringLevel;
    last_error?: string;
    created_at: string;
    resolved_at?: string | null;
    resolution_note?: string | null;
    applied_at?: string | null;
    offered_at?: string | null;
    updated_at: string;

    // Expanded fields for listing
    job?: {
        id: number;
        title: string;
        source?: string | null;
        advertiser_name?: string;
        company_name?: string;
        company_logo?: string;
        location_label?: string | null;
        work_types_label?: string | null;
        salary_label?: string | null;
        classification?: string | null;
        sub_classification?: string | null;
        share_link?: string;
        listed_at?: string | null;
    };
}

export interface ApplicationCompanyRole {
    id: string;
    job_id: number;
    status: ApplicationStatus;
    resolution: ApplicationResolution;
    updated_at: string;
    job: {
        id: number;
        title: string;
        source?: string | null;
        advertiser_name?: string | null;
        company_name?: string | null;
        company_logo?: string | null;
        location_label?: string | null;
        work_types_label?: string | null;
        classification?: string | null;
        sub_classification?: string | null;
        share_link?: string | null;
        listed_at?: string | null;
    };
}

export interface ApplicationCompanyRoleListResponse {
    items: ApplicationCompanyRole[];
}

export interface CreateApplicationRequest {
    job_id: number;
    resume_template_id: string;
    tailoring_level: TailoringLevel;
}

export interface RetryApplicationRequest {
    resume_template_id?: string;
    tailoring_level?: TailoringLevel;
}

export interface UpdateApplicationStatusRequest {
    status: ApplicationStatus;
    note?: string;
}

export interface UpdateApplicationResolutionRequest {
    resolution: ApplicationResolution;
    note?: string;
}

export interface ApplicationListRequest {
    keyword?: string;
    status?: ApplicationStatus;
    status_group?: ApplicationStatusGroup;
    resolution?: ApplicationResolution;
    page: number;
    page_size: number;
}

export interface ApplicationListResponse {
    items: Application[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface StatusHistoryEntry {
    id: string;
    application_id: string;
    from_status: ApplicationStatus | null;
    to_status: ApplicationStatus;
    changed_at: string;
    changed_by_id: number | null;
    note: string | null;
}

export interface StatusHistoryListResponse {
    items: StatusHistoryEntry[];
}

export interface ApplicationFunnelResponse {
    applied: number;
    phone_screens: number;
    interviewing: number;
    offers: number;
}
