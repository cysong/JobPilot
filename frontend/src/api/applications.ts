import client from './client';
import type { Application, ApplicationListResponse, CreateApplicationRequest } from '@/types/application';

export const applicationApi = {
    create: async (data: CreateApplicationRequest) => {
        const result = await client.post<Application, Application>('/applications', data);
        return result;
    },

    get: async (id: string) => {
        const result = await client.get<Application, Application>(`/applications/${id}`);
        return result;
    },

    list: async (page = 1, size = 20) => {
        const result = await client.get<ApplicationListResponse, ApplicationListResponse>('/applications', {
            params: { page, size }
        });
        return result;
    },

    retryCoverLetter: async (id: string) => {
        const result = await client.post<Application, Application>(`/applications/${id}/retry-coverletter`);
        return result;
    }
};
