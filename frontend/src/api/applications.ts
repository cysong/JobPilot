import client from './client';
import type { Application, ApplicationListResponse, CreateApplicationRequest } from '@/types/application';

export const applicationApi = {
    create: async (data: CreateApplicationRequest) => {
        const response = await client.post<Application>('/applications', data);
        return response.data;
    },

    get: async (id: string) => {
        const response = await client.get<Application>(`/applications/${id}`);
        return response.data;
    },

    list: async (page = 1, size = 20) => {
        const response = await client.get<ApplicationListResponse>('/applications', {
            params: { page, size }
        });
        return response.data;
    },

    retryCoverLetter: async (id: string) => {
        const response = await client.post<Application>(`/applications/${id}/retry-coverletter`);
        return response.data;
    }
};
