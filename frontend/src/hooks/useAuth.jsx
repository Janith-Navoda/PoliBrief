import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [setupComplete, setSetupComplete] = useState(null)  // null = loading
  const [loading, setLoading] = useState(true)

  const checkStatus = useCallback(async () => {
    try {
      const { data } = await authApi.status()
      setSetupComplete(data.setup_complete)
      if (data.authenticated) {
        setUser({ username: data.username })
      } else {
        setUser(null)
      }
    } catch {
      setSetupComplete(false)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    checkStatus()
    // Listen for 401 events from API interceptor
    const handle = () => { setUser(null) }
    window.addEventListener('pb:unauthorized', handle)
    return () => window.removeEventListener('pb:unauthorized', handle)
  }, [checkStatus])

  const login = async (username, password) => {
    const { data } = await authApi.login(username, password)
    setUser({ username: data.username })
    return data
  }

  const logout = async () => {
    await authApi.logout()
    setUser(null)
  }

  const completeSetup = (username) => {
    setSetupComplete(true)
    setUser({ username })
  }

  return (
    <AuthContext.Provider value={{ user, setupComplete, loading, login, logout, completeSetup, checkStatus }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
