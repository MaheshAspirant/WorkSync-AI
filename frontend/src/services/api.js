import axios from 'axios'

export const TOKEN_KEY = 'worksync_token'
export const USER_KEY = 'worksync_user'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error) {
  const data = error?.response?.data
  if (data?.error?.message) {
    const details = data.error.details
    if (details?.issues?.length) return `${data.error.message}: ${details.issues.join('; ')}`
    return data.error.message
  }
  if (data?.detail) return typeof data.detail === 'string' ? data.detail : 'Request failed'
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  if (error?.message === 'Network Error') return 'Cannot reach the WorkSync AI API. Is the backend running?'
  return error?.message || 'Something went wrong'
}

export default api
