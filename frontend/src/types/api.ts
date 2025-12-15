export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export class ApiError extends Error {
  code: number
  status?: number
  data?: unknown

  constructor(code: number, message: string, status?: number, data?: unknown) {
    super(message)
    this.code = code
    this.status = status
    this.data = data
    this.name = 'ApiError'
  }
}
