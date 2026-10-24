import { useState } from 'react'
import { Eye, EyeOff, AlertCircle, Loader2, ArrowRight } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export default function LoginPage() {
  const { login } = useAuth()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.username, form.password)
    } catch (ex) {
      const msg = ex.response?.data?.detail
      if (ex.response?.status === 429) {
        setError('Too many login attempts. Please wait 5 minutes.')
      } else {
        setError(msg || 'Invalid username or password.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full bg-white text-[#111111] flex flex-col items-center justify-center p-4 sm:p-6 lg:p-8 antialiased selection:bg-[#111111] selection:text-white">
      {/* ── Login Content Container (constrained to 420–460px) ── */}
      <div className="w-full max-w-[440px] flex flex-col items-center">
        {/* ── Brand Header (separated by ~32px from card) ── */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 justify-center mb-2">
            <span className="text-3xl sm:text-4xl font-black tracking-tighter text-[#162238] uppercase">
              POLIBRIEF
            </span>
            <span className="w-2.5 h-2.5 rounded-full bg-[#C9A15A] inline-block" />
          </div>
          <p className="text-[11px] sm:text-xs font-bold tracking-widest uppercase text-[#767676]">
            Political News &amp; Facebook Studio
          </p>
        </div>

        {/* ── Login Card (desktop padding 32–40px, mobile 24px) ── */}
        <div className="w-full bg-white border border-[#E5E5E5] rounded-3xl p-6 sm:p-10 shadow-[0_4px_24px_rgba(0,0,0,0.03)]">
          {/* Card Title & Subtitle */}
          <div className="mb-7">
            <h1 className="text-xl sm:text-2xl font-bold text-[#111111] tracking-tight">
              Administrator Sign In
            </h1>
            <p className="text-xs sm:text-sm text-[#767676] mt-1.5 leading-relaxed">
              Private access • Localhost deployment
            </p>
          </div>

          {/* Validation / Error Message */}
          {error && (
            <div
              role="alert"
              className="mb-6 p-3.5 rounded-xl bg-[#FEE2E2] border border-[#FECACA] text-[#991B1B] text-xs flex items-start gap-2.5 leading-relaxed animate-fade-in-up"
            >
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Sign In Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username Input Group */}
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="block text-xs font-bold tracking-wide uppercase text-[#111111]"
              >
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                autoFocus
                placeholder="Enter administrator username"
                value={form.username}
                onChange={onChange}
                className="w-full h-11 sm:h-12 px-4 rounded-xl border border-[#E5E5E5] bg-white text-sm text-[#111111] placeholder:text-[#999999] outline-none transition-all duration-150 focus:border-[#111111] focus:ring-1 focus:ring-[#111111]"
              />
            </div>

            {/* Password Input Group */}
            <div className="space-y-2">
              <label
                htmlFor="password"
                className="block text-xs font-bold tracking-wide uppercase text-[#111111]"
              >
                Password
              </label>
              <div className="relative flex items-center">
                <input
                  id="password"
                  name="password"
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  placeholder="Enter administrator password"
                  value={form.password}
                  onChange={onChange}
                  className="w-full h-11 sm:h-12 pl-4 pr-12 rounded-xl border border-[#E5E5E5] bg-white text-sm text-[#111111] placeholder:text-[#999999] outline-none transition-all duration-150 focus:border-[#111111] focus:ring-1 focus:ring-[#111111]"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-2 text-[#767676] hover:text-[#111111] rounded-lg transition-colors cursor-pointer flex items-center justify-center"
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                >
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Submit Action (44–48px height, full-width, pill shape) */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full h-11 sm:h-12 rounded-full bg-[#111111] text-white hover:bg-black font-bold text-sm tracking-wide transition-all duration-150 shadow-xs hover:shadow active:scale-[0.99] disabled:opacity-45 disabled:cursor-not-allowed disabled:pointer-events-none flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Signing in…</span>
                  </>
                ) : (
                  <>
                    <span>Sign In</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Card Footer Helper */}
          <div className="mt-8 pt-6 border-t border-[#E5E5E5] text-center">
            <p className="text-xs text-[#767676] leading-relaxed">
              PoliBrief is a private local application.
              <span className="block mt-1.5 text-[11px]">
                To reset credentials, run{' '}
                <code className="inline-block bg-[#F8F9FA] px-1.5 py-0.5 rounded text-[#111111] font-mono border border-[#E5E5E5]">
                  python scripts/setup_admin.py
                </code>
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
