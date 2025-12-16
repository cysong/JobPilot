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

export interface Application {
    id: string;
    user_id: string;
    job_id: number;
    status: ApplicationStatus;
    source_resume_id: string;
    resume_document_id?: string;
    cover_letter_document_id?: string;
    tailoring_level: string;
    last_error?: string;
    created_at: string;
    updated_at: string;

    // Expanded fields for listing
    job?: {
        id: number;
        title: string;
        advertiser_name?: string;
        company_name?: string;
        company_logo?: string;
    };
}

export interface CreateApplicationRequest {
    job_id: number;
    resume_template_id: string;
    tailoring_level: 'light';
}

export interface ApplicationListResponse {
    items: Application[];
    total: number;
    page: number;
    size: number;
    total_pages: number;
}
