import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'
import { ApiError } from '@/types/api'

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const redirectToLogin = () => {
  const currentPath = window.location.pathname
  if (currentPath !== '/login' && currentPath !== '/register') {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
  }
}

const handleApiError = (error: ApiError) => {
  if (error.code === 401 || error.code === 419) {
    redirectToLogin()
  }
  if (error.code === 403) {
    // Permission denied; surface message to UI layer
    // Consumers can catch ApiError and show UI message
  }
  if (error.code === 1001 || error.code === 1002) {
    // Business limits; let UI handle via ApiError
  }
}

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for unified format handling
apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse<unknown>>) => {
    const contentType = response.headers['content-type']
    const isBinary =
      response.request?.responseType === 'blob' ||
      (typeof contentType === 'string' && contentType.includes('application/pdf'))

    // Pass through binary responses (export/download)
    if (isBinary) {
      return response.data
    }

    const payload = response.data as ApiResponse<unknown>
    const looksLikeApiResponse =
      payload &&
      typeof payload === 'object' &&
      'code' in payload &&
      'message' in payload &&
      'data' in payload

    if (looksLikeApiResponse) {
      if (payload.code === 0) {
        return payload.data
      }
      const apiError = new ApiError(
        Number(payload.code),
        String(payload.message ?? 'Request failed'),
        response.status,
        payload.data,
      )
      handleApiError(apiError)
      return Promise.reject(apiError)
    }

    // Fallback: return raw data for non-standard responses
    return response.data
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    const status = error.response?.status
    const payload = error.response?.data

    if (payload && typeof payload === 'object' && 'code' in payload && 'message' in payload) {
      const apiError = new ApiError(
        Number((payload as any).code),
        String((payload as any).message ?? 'Request failed'),
        status,
        (payload as any).data,
      )
      handleApiError(apiError)
      return Promise.reject(apiError)
    }

    if (status === 401 || status === 419) {
      redirectToLogin()
    }

    return Promise.reject(error)
  }
)

export default apiClient
