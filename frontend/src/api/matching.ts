import apiClient from './client'
import type {
  MatchLabelCreate,
  MatchLabelInfo,
  ResumeRoleFamilyResponse,
  RoleFamilyInfo,
  TitleFamilyListParams,
  TitleFamilyListResponse,
  TitleFamilyUpdateResponse,
} from '@/types/matching'

export const matchingApi = {
  getRoleFamilies: () => apiClient.get<RoleFamilyInfo[], RoleFamilyInfo[]>('/matching/role-families'),

  setResumeRoleFamily: (resumeId: string, roleFamily: string | null) =>
    apiClient.put<ResumeRoleFamilyResponse, ResumeRoleFamilyResponse>(
      `/matching/resumes/${resumeId}/role-family`,
      { role_family: roleFamily },
    ),

  // Admin
  createLabel: (data: MatchLabelCreate) =>
    apiClient.post<MatchLabelInfo, MatchLabelInfo>('/admin/matching/labels', data),

  getTitleFamilies: (params: TitleFamilyListParams) => {
    const search = new URLSearchParams()
    if (params.q) search.append('q', params.q)
    if (params.role_family) search.append('role_family', params.role_family)
    if (params.status) search.append('status', params.status)
    search.append('limit', String(params.limit ?? 50))
    search.append('offset', String(params.offset ?? 0))
    return apiClient.get<TitleFamilyListResponse, TitleFamilyListResponse>(
      `/admin/matching/title-families?${search.toString()}`,
    )
  },

  updateTitleFamily: (title: string, roleFamily: string | null) =>
    apiClient.put<TitleFamilyUpdateResponse, TitleFamilyUpdateResponse>('/admin/matching/title-families', {
      title,
      role_family: roleFamily,
    }),
}
