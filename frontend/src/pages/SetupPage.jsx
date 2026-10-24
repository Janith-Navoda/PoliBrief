import { useState } from 'react'
import { Eye, EyeOff, Shield, AlertCircle, Loader2, ArrowRight } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import api from '../services/api'

export default function SetupPage() {
  const { completeSetup } = useAuth()
  const [form, setForm] = useState({ username: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const validate = () => {
    if (!/^[a-zA-Z0-9_]{3,64}$/.test(form.username))
      return 'Username must be 3–64 characters (letters, numbers, underscore only).'
    if (form.password.length < 10)
      return 'Password must be at least 10 characters long.'
    if (form.password !== form.confirm)
      return 'Passwords do not match.'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    try {
      await api.post('/auth/setup', { username: form.username, password: form.password })
      // Auto-login after setup
      await api.post('/auth/login', { username: form.username, password: form.password })
      completeSetup(form.username)
    } catch (ex) {
      setError(ex.response?.data?.detail || 'Setup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full bg-[#F8F9FA] sm:bg-white text-[#111111] flex items-center justify-center p-4 sm:p-6 lg:p-8 antialiased">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 justify-center">
            <span className="text-3xl sm:text-4xl font-black tracking-tighter text-[#162238] uppercase">
              POLIBRIEF
            </span>
            <span className="w-2.5 h-2.5 rounded-full bg-[#C9A15A] inline-block mb-1" />
          </div>
          <p className="text-xs font-bold tracking-widest uppercase text-[#767676]">
            Initial Environment Setup
          </p>
        </div>

        {/* Setup Card */}
        <div className="card p-8 bg-white border border-[#E5E5E5] rounded-3xl shadow-sm space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-[#111111]">
              Create Administrator Account
            </h2>
            <p className="text-xs text-[#767676]">
              Set up your master credentials to initialize PoliBrief.
            </p>
          </div>

          {error && (
            <div className="alert alert-error">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span className="text-xs leading-relaxed">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="form-label" htmlFor="setup-username">
                Administrator Username
              </label>
              <input
                id="setup-username"
                name="username"
                type="text"
                className="form-input text-xs"
                placeholder="e.g. admin"
                autoComplete="username"
                value={form.username}
                onChange={onChange}
                required
                autoFocus
              />
            </div>

            <div>
              <label className="form-label" htmlFor="setup-password">
                Master Password (min 10 chars)
              </label>
              <div className="relative">
                <input
                  id="setup-password"
                  name="password"
                  type={showPwd ? 'text' : 'password'}
                  className="form-input text-xs pr-10"
                  placeholder="Minimum 10 characters"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={onChange}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#767676] hover:text-[#111111] cursor-pointer"
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                >
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="form-label" htmlFor="setup-confirm">
                Confirm Master Password
              </label>
              <input
                id="setup-confirm"
                name="confirm"
                type={showPwd ? 'text' : 'password'}
                className="form-input text-xs"
                placeholder="Re-enter password to confirm"
                autoComplete="new-password"
                value={form.confirm}
                onChange={onChange}
                required
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary w-full py-3 text-sm font-bold flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    <span>Initialize Application</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </form>

          <div className="pt-4 border-t border-[#E5E5E5] text-center">
            <p className="text-[11px] text-[#767676] leading-relaxed">
              This account has full administrative privileges. Store these credentials safely.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
