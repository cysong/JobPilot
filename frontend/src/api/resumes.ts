import client from './client'
import type {
    Resume,
    ResumeListItem,
    CreateResumeRequest,
    UpdateResumeRequest,
    ResumeListResponse,
    ResumeExportRequest
} from '@/types/resume'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'

export const resumeApi = {
    getResumes: async (page = 1, size = 100) => {
        const result = await client.get<ResumeListResponse, ResumeListResponse>('/resumes', {
            params: { page, size }
        })
        return result
    },

    getResumeForEdit: async (id: string) => {
        const result = await client.get<DocumentEditData, DocumentEditData>(`/resumes/${id}/edit`)
        return result
    },

    updateResumeContent: async (id: string, data: DocumentUpdatePayload) => {
        const result = await client.patch<Resume, Resume>(`/resumes/${id}`, data)
        return result
    },

    getResumeById: async (id: string) => {
        const result = await client.get<Resume, Resume>(`/resumes/${id}`)
        return result
    },

    createResume: async (data: CreateResumeRequest) => {
        const result = await client.post<Resume, Resume>('/resumes', data)
        return result
    },

    updateResume: async (id: string, data: UpdateResumeRequest) => {
        const result = await client.put<Resume, Resume>(`/resumes/${id}`, data)
        return result
    },

    deleteResume: async (id: string) => {
        await client.delete(`/resumes/${id}`)
    },

    finalizeResume: async (id: string) => {
        const result = await client.patch<Resume, Resume>(`/resumes/${id}/finalize`)
        return result
    },

    // Returns the blob for the PDF
    exportResume: async (id: string, options?: ResumeExportRequest) => {
        const result = await client.post<Blob, Blob>(`/resumes/${id}/export`, {
            template: options?.template || 'modern',
            font_size: options?.font_size || 12,
            include_metadata: options?.include_metadata ?? false
        }, {
            responseType: 'blob'
        })
        return result
    }
}
