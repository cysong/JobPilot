export interface ResumeListItem {
    id: string
    title: string
    is_draft: boolean
    created_at: string
    updated_at: string
    document_id?: string
}

export interface Document {
    id: string
    content: string
    format: string
    updated_at: string
}

export interface Resume {
    id: string
    title: string
    is_draft: boolean
    user_id: string
    document_id: string
    created_at: string
    updated_at: string
    document: Document
}

export interface CreateResumeRequest {
    title: string
    content: string
    is_draft?: boolean
}

export interface UpdateResumeRequest {
    title?: string
    content?: string
}

export interface ResumeTitleUpdate {
    title: string
}

export interface ResumeListResponse {
    items: ResumeListItem[]
    total: number
    page: number
    size: number
    pages: number
}

export interface ResumeExportRequest {
    template?: 'modern' | 'classic' | 'minimal'
    font_size?: number
    include_metadata?: boolean
}
