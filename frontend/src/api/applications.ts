import client from './client';
import type {
    Application,
    ApplicationListRequest,
    ApplicationListResponse,
    CreateApplicationRequest,
    RetryApplicationRequest,
    UpdateApplicationResolutionRequest,
    UpdateApplicationStatusRequest,
} from '@/types/application';
import type { ResumeExportRequest } from '@/types/resume';
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document';

export const applicationApi = {
    create: async (data: CreateApplicationRequest) => {
        const result = await client.post<Application, Application>('/applications', data);
        return result;
    },

    get: async (id: string) => {
        const result = await client.get<Application, Application>(`/applications/${id}`);
        return result;
    },

    getByJobId: async (jobId: number) => {
        const result = await client.get<Application, Application>(`/jobs/${jobId}/application`);
        return result || null;
    },

    list: async (filters: ApplicationListRequest) => {
        const params = new URLSearchParams();
        params.append('page', filters.page.toString());
        params.append('page_size', filters.page_size.toString());
        if (filters.keyword) {
            params.append('keyword', filters.keyword);
        }
        if (filters.status) {
            params.append('status', filters.status);
        }
        if (filters.resolution && filters.resolution !== 'ACTIVE') {
            params.append('resolution', filters.resolution);
        }

        const result = await client.get<ApplicationListResponse, ApplicationListResponse>(
            `/applications?${params.toString()}`
        );
        return result;
    },

    retryCoverLetter: async (id: string, data?: RetryApplicationRequest) => {
        const result = await client.post<Application, Application>(`/applications/${id}/retry`, data || {});
        return result;
    },

    updateStatus: async (id: string, data: UpdateApplicationStatusRequest) => {
        const result = await client.patch<Application, Application>(`/applications/${id}/status`, data);
        return result;
    },

    updateResolution: async (id: string, data: UpdateApplicationResolutionRequest) => {
        const result = await client.patch<Application, Application>(`/applications/${id}/resolution`, data);
        return result;
    },

    getTailoredResumeForEdit: async (applicationId: string) => {
        const result = await client.get<DocumentEditData, DocumentEditData>(`/applications/${applicationId}/resume/edit`);
        return result;
    },

    updateTailoredResume: async (applicationId: string, data: DocumentUpdatePayload) => {
        const result = await client.patch<Application, Application>(`/applications/${applicationId}/resume`, data);
        return result;
    },

    getCoverLetterForEdit: async (applicationId: string) => {
        const result = await client.get<DocumentEditData, DocumentEditData>(`/applications/${applicationId}/cover-letter/edit`);
        return result;
    },

    updateCoverLetter: async (applicationId: string, data: DocumentUpdatePayload) => {
        const result = await client.patch<Application, Application>(`/applications/${applicationId}/cover-letter`, data);
        return result;
    },

    exportTailoredResumePdf: async (applicationId: string, options?: ResumeExportRequest) => {
        const result = await client.post<Blob, Blob>(`/applications/${applicationId}/resume/export`, {
            template: options?.template || 'modern',
            font_size: options?.font_size || 12,
            include_metadata: options?.include_metadata ?? false
        }, {
            responseType: 'blob'
        });
        return result;
    },

    exportCoverLetterPdf: async (applicationId: string, options?: ResumeExportRequest) => {
        const result = await client.post<Blob, Blob>(`/applications/${applicationId}/cover-letter/export`, {
            template: options?.template || 'modern',
            font_size: options?.font_size || 12,
            include_metadata: options?.include_metadata ?? false
        }, {
            responseType: 'blob'
        });
        return result;
    },
};
