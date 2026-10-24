import { useState } from 'react'
import {
  LogOut, Loader2, Menu, X, Shield
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import PageContainer from '../components/PageContainer'

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard' },
  { id: 'feed',       label: 'News Feed' },
  { id: 'studio',     label: 'Post Studio' },
  { id: 'drafts',     label: 'Drafts' },
  { id: 'published',  label: 'Published' },
  { id: 'sources',    label: 'Sources' },
  { id: 'settings',   label: 'Settings' },
]

export default function AppLayout({ children, currentPage, onNavigate, schedulerStatus }) {
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      setLoggingOut(false)
    }
  }

  const navigateTo = (pageId) => {
    onNavigate(pageId)
    setMobileMenuOpen(false)
  }

  const schedulerLabel = schedulerStatus === null
    ? 'Status unavailable'
    : schedulerStatus.running ? 'Scheduler running' : 'Scheduler stopped'
  const schedulerColor = schedulerStatus?.running
    ? 'bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]'
    : schedulerStatus === null
      ? 'bg-[#F8F9FA] text-[#666666] border-[#E5E5E5]'
      : 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]'

  return (
    <div className="min-h-screen bg-white text-[#111111] flex flex-col antialiased">
      {/* ── Sticky Top Horizontal Navigation Bar (approx 72px) ── */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-[#E5E5E5]">
        <PageContainer className="h-[72px] flex items-center justify-between">
          {/* Left: Brand Logo & Desktop Navigation */}
          <div className="flex items-center gap-6 xl:gap-8 min-w-0">
            {/* Wordmark Logo */}
              <button
              onClick={() => navigateTo('dashboard')}
                type="button"
              className="flex items-center gap-2 group cursor-pointer border-none bg-transparent text-left p-0 shrink-0"
              title="Go to Dashboard"
            >
              <span className="text-xl sm:text-2xl font-black tracking-tighter text-[#162238] uppercase flex items-center">
                POLIBRIEF
                <span className="w-2 h-2 rounded-full bg-[#C9A15A] ml-1.5 inline-block" />
              </span>
              <span className="text-[10px] font-bold tracking-widest text-[#767676] uppercase px-2 py-0.5 rounded-full bg-[#F8F9FA] border border-[#E5E5E5]">
                V1
              </span>
            </button>

            {/* Desktop Horizontal Navigation Links */}
            <nav aria-label="Main navigation" className="hidden lg:flex items-center gap-1 xl:gap-2">
              {NAV_ITEMS.map(({ id, label }) => {
                const isActive = currentPage === id
                return (
                  <button
                    key={id}
                    type="button"
                    aria-current={isActive ? 'page' : undefined}
                    onClick={() => navigateTo(id)}
                    className={`px-3.5 xl:px-4 py-1.5 text-xs xl:text-sm font-semibold tracking-normal rounded-full transition-all duration-150 cursor-pointer border whitespace-nowrap ${
                      isActive
                        ? 'bg-[#111111] text-white border-[#111111] shadow-xs'
                        : 'bg-transparent text-[#666666] border-transparent hover:text-[#111111] hover:bg-[#F8F9FA]'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Right: Status Pill, Admin Identity, Logout Action */}
          <div className="hidden lg:flex items-center gap-3 xl:gap-4 shrink-0">
            {/* Active System Status Pill (shown on xl+) */}
            <div className={`hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold ${schedulerColor}`} role="status" aria-live="polite">
              <span className={`w-1.5 h-1.5 rounded-full ${schedulerStatus?.running ? 'bg-[#15803D]' : schedulerStatus === null ? 'bg-[#767676]' : 'bg-[#B45309]'}`} />
              <span className="tracking-wider uppercase text-[10px]">{schedulerLabel}</span>
            </div>

            {/* Administrator Identity Badge */}
            <div className="text-xs font-medium text-[#666666] flex items-center gap-1.5">
              <Shield size={14} className="text-[#162238] shrink-0" />
              <span className="font-semibold text-[#111111]">{user?.username || 'Admin'}</span>
            </div>

            <div className="w-px h-4 bg-[#E5E5E5] shrink-0" />

            {/* Sign Out Button */}
            <button
              type="button"
              onClick={handleLogout}
              disabled={loggingOut}
              className="btn btn-secondary btn-sm text-xs font-semibold cursor-pointer"
              title="Sign out of PoliBrief"
            >
              {loggingOut ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <LogOut size={13} />
              )}
              <span>{loggingOut ? 'Signing out…' : 'Sign Out'}</span>
            </button>
          </div>

          {/* Mobile / Tablet Menu Button (< lg) */}
          <div className="flex lg:hidden items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-full text-[#111111] hover:bg-[#F8F9FA] border border-[#E5E5E5] transition-colors cursor-pointer"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
              aria-controls="app-mobile-navigation"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </PageContainer>

        {/* Mobile Dropdown Drawer */}
        {mobileMenuOpen && (
          <div id="app-mobile-navigation" className="lg:hidden border-t border-[#E5E5E5] bg-white animate-fade-in-up">
            <PageContainer className="py-5 space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pb-4 border-b border-[#E5E5E5]">
                <nav aria-label="Mobile navigation" className="contents">
                {NAV_ITEMS.map(({ id, label }) => {
                  const isActive = currentPage === id
                  return (
                    <button
                      key={id}
                      type="button"
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => navigateTo(id)}
                      className={`text-left px-3.5 py-2.5 rounded-xl text-xs font-bold transition-colors cursor-pointer ${
                        isActive
                          ? 'bg-[#111111] text-white'
                          : 'text-[#666666] hover:bg-[#F8F9FA] hover:text-[#111111]'
                      }`}
                    >
                      {label}
                    </button>
                  )
                })}
                </nav>
              </div>

              <div className="flex items-center justify-between pt-1 flex-wrap gap-3">
                <div className="text-xs text-[#666666] flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${schedulerStatus?.running ? 'bg-[#15803D]' : schedulerStatus === null ? 'bg-[#767676]' : 'bg-[#B45309]'}`} />
                  <span className="flex items-center gap-1.5">
                    <Shield size={13} className="text-[#162238]" />
                    Signed in as <strong className="text-[#111111]">{user?.username || 'Admin'}</strong>
                  </span>
                  <span className="ml-auto">{schedulerLabel}</span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={loggingOut}
                  className="btn btn-secondary btn-sm text-xs font-semibold"
                >
                  {loggingOut ? <Loader2 size={13} className="animate-spin" /> : <LogOut size={13} />}
                  <span>Sign Out</span>
                </button>
              </div>
            </PageContainer>
          </div>
        )}
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 w-full py-8 sm:py-10">
        <PageContainer>
          {children}
        </PageContainer>
      </main>

      {/* ── Minimal Editorial Footer ── */}
      <footer className="border-t border-[#E5E5E5] bg-white py-6 mt-16 sm:mt-20">
        <PageContainer className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#767676]">
          <div className="flex items-center gap-2 flex-wrap justify-center sm:justify-start">
            <span className="font-bold tracking-tight text-[#111111]">POLIBRIEF</span>
            <span>•</span>
            <span>Political News & Facebook Publishing Studio</span>
          </div>
          <div className="flex items-center gap-3 sm:gap-4 flex-wrap justify-center sm:justify-end">
            <span>30-Day Retention Enforced</span>
            <span>•</span>
            <span>Localhost Only</span>
          </div>
        </PageContainer>
      </footer>
    </div>
  )
}
