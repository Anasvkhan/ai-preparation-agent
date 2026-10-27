import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true, // sends the httpOnly refresh cookie to /api/auth/*
})

// The access token lives only in memory; the refresh cookie restores it after a page reload.
let accessToken = null
let onLogout = () => {}

export function setAccessToken(token) {
  accessToken = token
}

export function setLogoutHandler(handler) {
  onLogout = handler
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

let refreshing = null

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && !original._retried && !isAuthCall) {
      original._retried = true
      try {
        refreshing ??= api.post('/auth/refresh').finally(() => (refreshing = null))
        const { data } = await refreshing
        setAccessToken(data.access_token)
        return api(original)
      } catch {
        onLogout()
      }
    }
    return Promise.reject(error)
  },
)

export function errorMessage(err, fallback = 'Something went wrong') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg.replace(/^Value error, /, '')
  return fallback
}

export default api
