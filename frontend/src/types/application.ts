export type ApplicationStatus = 'tailoring' | 'ready' | 'failed';

export interface Application {
    id: string;
    user_id: string;
    job_id: number;
    status: ApplicationStatus;
    resume_template_id: string;
    resume_id: string; // Working copy
    cover_letter_id?: string;
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
