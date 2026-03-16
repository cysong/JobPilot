export type ApplicationStatus =
    | 'Pending'
    | 'Tailoring'
    | 'Ready'
    | 'Applied'
    | 'PhoneScreen'
    | 'Interviewing'
    | 'Offer'
    | 'Rejected'
    | 'Failed';

export type TailoringLevel = 'light' | 'moderate' | 'deep'

export interface Application {
    id: string;
    user_id: string;
    job_id: number;
    status: ApplicationStatus;
    source_resume_id: string;
    resume_document_id?: string;
    cover_letter_document_id?: string;
    tailoring_level: TailoringLevel;
    last_error?: string;
    created_at: string;
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
        classification?: string | null;
        sub_classification?: string | null;
        share_link?: string;
        is_expired?: boolean;
        manual_expired?: boolean;
    };
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

export interface ApplicationListRequest {
    keyword?: string;
    status?: ApplicationStatus;
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
