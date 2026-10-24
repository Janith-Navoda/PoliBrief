import { useEffect, useState } from 'react'
import { BrowserRouter, useLocation, useNavigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './hooks/useAuth'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import DashboardPage from './pages/DashboardPage'
import NewsFeedPage from './pages/NewsFeedPage'
import SourcesPage from './pages/SourcesPage'
import SettingsPage from './pages/SettingsPage'
import PostStudioPage from './pages/PostStudioPage'
import DraftsPage from './pages/DraftsPage'
import PublishedPostsPage from './pages/PublishedPostsPage'
import { articlesApi, systemApi } from './services/api'

// ─── Loading Screen ───────────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="spinner spinner-lg mx-auto mb-4" />
        <p className="text-xs font-semibold tracking-wider uppercase text-[#707072]">
          Loading PoliBrief…
        </p>
      </div>
    </div>
  )
}

// ─── Page Router ──────────────────────────────────────────────────────────────
function PageRouter({ page, onNavigate, onViewDraft, article, schedulerStatus }) {
  switch (page) {
    case 'dashboard':
      return <DashboardPage onNavigate={onNavigate} onViewDraft={onViewDraft} schedulerStatus={schedulerStatus} />
    case 'feed':
      return <NewsFeedPage onNavigate={onNavigate} onViewDraft={onViewDraft} />
    case 'sources':
      return <SourcesPage />
    case 'studio':
      return <PostStudioPage article={article} onNavigate={onNavigate} />
    case 'drafts':
      return <DraftsPage onNavigate={onNavigate} />
    case 'published':
      return <PublishedPostsPage />
    case 'settings':
      return <SettingsPage />
    default:
      return <DashboardPage onNavigate={onNavigate} />
  }
}

// ─── Authenticated App ────────────────────────────────────────────────────────
function AuthenticatedApp() {
  const location = useLocation()
  const navigate = useNavigate()
  const [selectedArticle, setSelectedArticle] = useState(null)
  const [schedulerStatus, setSchedulerStatus] = useState(null)
  const routePage = location.pathname.split('/').filter(Boolean)[0] || 'dashboard'
  const page = ['dashboard', 'feed', 'sources', 'studio', 'drafts', 'published', 'settings'].includes(routePage)
    ? routePage
    : 'dashboard'

  useEffect(() => {
    let active = true
    const articleId = Number(new URLSearchParams(location.search).get('article'))
    const stateArticle = location.state?.article
    if (!articleId) {
      setSelectedArticle(null)
      return () => { active = false }
    }
    if (stateArticle?.id === articleId) {
      setSelectedArticle(stateArticle)
      return () => { active = false }
    }
    articlesApi.get(articleId)
      .then(res => { if (active) setSelectedArticle(res.data) })
      .catch(() => { if (active) setSelectedArticle(null) })
    return () => { active = false }
  }, [location.key, location.search, location.state])

  useEffect(() => {
    let active = true
    const loadSchedulerStatus = () => {
      systemApi.schedulerStatus()
        .then(res => { if (active) setSchedulerStatus(res.data) })
        .catch(() => { if (active) setSchedulerStatus(null) })
    }
    loadSchedulerStatus()
    const interval = setInterval(loadSchedulerStatus, 30000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  const handleNavigate = (targetPage, article = null) => {
    const path = targetPage === 'dashboard' ? '/' : `/${targetPage}`
    navigate(article ? `${path}?article=${article.id}` : path, {
      state: article ? { article } : null,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleViewDraft = (draftId) => {
    navigate(draftId ? `/drafts?draft_id=${draftId}` : '/drafts')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <AppLayout currentPage={page} onNavigate={handleNavigate} schedulerStatus={schedulerStatus}>
      <PageRouter page={page} onNavigate={handleNavigate} onViewDraft={handleViewDraft} article={selectedArticle} schedulerStatus={schedulerStatus} />
    </AppLayout>
  )
}

// ─── Root Router ──────────────────────────────────────────────────────────────
function RootRouter() {
  const { user, setupComplete, loading } = useAuth()

  if (loading) return <LoadingScreen />
  if (!setupComplete) return <SetupPage />
  if (!user) return <LoginPage />
  return <AuthenticatedApp />
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RootRouter />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#111111',
              color: '#FFFFFF',
              borderRadius: '9999px',
              padding: '12px 24px',
              fontSize: '13px',
              fontWeight: 500,
              boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
            },
            success: {
              iconTheme: { primary: '#FFFFFF', secondary: '#111111' },
            },
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  )
}
