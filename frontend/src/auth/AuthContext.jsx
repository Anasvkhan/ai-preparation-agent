import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api, { setAccessToken, setLogoutHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const applySession = useCallback((data) => {
    setAccessToken(data.access_token)
    setUser(data.user)
  }, [])

  const clearSession = useCallback(() => {
    setAccessToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setLogoutHandler(clearSession)
    // Restore the session from the refresh cookie on page load.
    api
      .post('/auth/refresh')
      .then(({ data }) => applySession(data))
      .catch(() => clearSession())
      .finally(() => setLoading(false))
  }, [applySession, clearSession])

  const login = async (email, password) => applySession((await api.post('/auth/login', { email, password })).data)

  const register = async (name, email, password) =>
    applySession((await api.post('/auth/register', { name, email, password })).data)

  const logout = async () => {
    await api.post('/auth/logout').catch(() => {})
    clearSession()
  }

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, register, logout, applySession }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
