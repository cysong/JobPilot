import client from './client'
import type {
    Resume,
    ResumeListItem,
    CreateResumeRequest,
    UpdateResumeRequest,
    ResumeListResponse,
    ResumeExportRequest
} from '@/types/resume'

export const resumeApi = {
    getResumes: async (page = 1, size = 100) => {
        const response = await client.get<ResumeListResponse>('/resumes', {
            params: { page, size }
        })
        return response.data
    },

    getResumeById: async (id: string) => {
        const response = await client.get<Resume>(`/resumes/${id}`)
        return response.data
    },

    createResume: async (data: CreateResumeRequest) => {
        const response = await client.post<Resume>('/resumes', data)
        return response.data
    },

    updateResume: async (id: string, data: UpdateResumeRequest) => {
        const response = await client.put<Resume>(`/resumes/${id}`, data)
        return response.data
    },

    deleteResume: async (id: string) => {
        await client.delete(`/resumes/${id}`)
    },

    finalizeResume: async (id: string) => {
        const response = await client.patch<Resume>(`/resumes/${id}/finalize`)
        return response.data
    },

    // Returns the blob for the PDF
    exportResume: async (id: string, options?: ResumeExportRequest) => {
        const response = await client.post(`/resumes/${id}/export`, {
            template: options?.template || 'modern',
            font_size: options?.font_size || 12,
            include_metadata: options?.include_metadata ?? true
        }, {
            responseType: 'blob'
        })
        return response.data
    }
}
