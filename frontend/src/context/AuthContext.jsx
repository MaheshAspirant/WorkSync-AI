import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import api, { TOKEN_KEY, USER_KEY } from '../services/api'

const AuthContext = createContext(null)

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser)
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [loading, setLoading] = useState(Boolean(localStorage.getItem(TOKEN_KEY)))

  useEffect(() => {
    let active = true
    if (!token) {
      setLoading(false)
      return undefined
    }
    api
      .get('/auth/me')
      .then((response) => {
        if (!active) return
        setUser(response.data)
        localStorage.setItem(USER_KEY, JSON.stringify(response.data))
      })
      .catch(() => {
        if (!active) return
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        setToken(null)
        setUser(null)
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    const { access_token: accessToken, user: profile } = response.data
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(profile))
    setToken(accessToken)
    setUser(profile)
    return profile
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
    window.location.assign('/login')
  }

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      role: user?.role || null,
      isAuthenticated: Boolean(token && user),
      login,
      logout,
      setUser,
    }),
    [user, token, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
