import client from './client';
import type {
    Application,
    ApplicationCompanyRoleListResponse,
    ApplicationFunnelResponse,
    ApplicationListRequest,
    ApplicationListResponse,
    CreateApplicationRequest,
    RetryApplicationRequest,
    StatusHistoryEntry,
    StatusHistoryListResponse,
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

    getCompanyRoles: async (id: string) => {
        const result = await client.get<ApplicationCompanyRoleListResponse, ApplicationCompanyRoleListResponse>(
            `/applications/${id}/company-roles`
        );
        return result;
    },

    getByJobId: async (jobId: number) => {
        const result = await client.get<Application, Application>(`/jobs/${jobId}/application`);
        return result || null;
    },

    getFunnel: async () => {
        const result = await client.get<ApplicationFunnelResponse, ApplicationFunnelResponse>(
            '/applications/funnel',
        );
        return result;
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
        if (filters.status_group) {
            params.append('status_group', filters.status_group);
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

    getStatusHistory: async (applicationId: string): Promise<StatusHistoryListResponse> => {
        return client.get<StatusHistoryListResponse, StatusHistoryListResponse>(
            `/applications/${applicationId}/history`
        );
    },

    updateHistoryNote: async (applicationId: string, historyId: string, note: string): Promise<StatusHistoryEntry> => {
        return client.patch<StatusHistoryEntry, StatusHistoryEntry>(
            `/applications/${applicationId}/history/${historyId}/note`,
            { note }
        );
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
