import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'
import { ApiError } from '@/types/api'

const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8000/api/v1')

const rawClient: AxiosInstance = axios.create({
  baseURL,
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
rawClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

const unwrapResponse = <TResult>(response: AxiosResponse<ApiResponse<TResult> | TResult>): TResult => {
  const contentType = response.headers['content-type']
  const isBinary =
    response.config.responseType === 'blob' ||
    (typeof contentType === 'string' && contentType.includes('application/pdf'))

  if (isBinary) {
    return response.data as TResult
  }

  const payload = response.data
  const looksLikeApiResponse =
    payload &&
    typeof payload === 'object' &&
    'code' in payload &&
    'message' in payload &&
    'data' in payload

  if (looksLikeApiResponse) {
    const apiPayload = payload as ApiResponse<TResult>
    if (apiPayload.code === 0) {
      return apiPayload.data
    }

    const apiError = new ApiError(
      Number(apiPayload.code),
      String(apiPayload.message ?? 'Request failed'),
      response.status,
      apiPayload.data,
    )
    handleApiError(apiError)
    throw apiError
  }

  return payload as TResult
}

const toApiError = (error: AxiosError<ApiResponse<unknown>>): never => {
  const status = error.response?.status
  const payload = error.response?.data

  if (payload && typeof payload === 'object' && 'code' in payload && 'message' in payload) {
    const apiError = new ApiError(
      Number((payload as ApiResponse<unknown>).code),
      String((payload as ApiResponse<unknown>).message ?? 'Request failed'),
      status,
      (payload as ApiResponse<unknown>).data,
    )
    handleApiError(apiError)
    throw apiError
  }

  if (status === 401 || status === 419) {
    redirectToLogin()
  }

  throw error
}

const request = async <TResult>(config: AxiosRequestConfig): Promise<TResult> => {
  try {
    const response = await rawClient.request<ApiResponse<TResult> | TResult>(config)
    return unwrapResponse<TResult>(response)
  } catch (error) {
    return toApiError(error as AxiosError<ApiResponse<unknown>>)
  }
}

const apiClient = {
  get: <TResponse = unknown, TResult = TResponse>(url: string, config?: AxiosRequestConfig) =>
    request<TResult>({ ...config, method: 'get', url }),
  post: <TResponse = unknown, TResult = TResponse>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TResult>({ ...config, method: 'post', url, data }),
  put: <TResponse = unknown, TResult = TResponse>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TResult>({ ...config, method: 'put', url, data }),
  patch: <TResponse = unknown, TResult = TResponse>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TResult>({ ...config, method: 'patch', url, data }),
  delete: <TResponse = unknown, TResult = TResponse>(url: string, config?: AxiosRequestConfig) =>
    request<TResult>({ ...config, method: 'delete', url }),
}

export default apiClient
