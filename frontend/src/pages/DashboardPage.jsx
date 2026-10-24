import { useEffect, useState } from 'react'
import {
  Newspaper, FileText, Send, RefreshCw,
  TrendingUp, Clock, AlertCircle,
  Activity, PenSquare, ArrowRight, ExternalLink, Building
} from 'lucide-react'
import { systemApi, articlesApi, draftsApi, publishingApi } from '../services/api'
import { formatPoliTimestamp } from '../utils/dateTime'
import ArticlePublishingActions from '../components/ArticlePublishingActions'

export default function DashboardPage({ onNavigate, onViewDraft, schedulerStatus }) {
  const [stats, setStats] = useState(null)
  const [recentArticles, setRecentArticles] = useState([])
  const [recentDrafts, setRecentDrafts] = useState([])
  const [recentHistory, setRecentHistory] = useState([])

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const loadAllData = async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setError(null)

    try {
      const [statsRes, articlesRes, draftsRes, historyRes] = await Promise.all([
        systemApi.dashboardStats(),
        articlesApi.list({ page_size: 4 }),
        draftsApi.list({ limit: 4 }),
        publishingApi.history(3),
      ])

      setStats(statsRes.data)
      setRecentArticles(articlesRes.data.items || [])
      setRecentDrafts(Array.isArray(draftsRes.data) ? draftsRes.data : [])
      setRecentHistory(Array.isArray(historyRes.data) ? historyRes.data : [])
    } catch (ex) {
      setError(ex.response?.data?.detail || 'Failed to load dashboard data.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadAllData()
    const interval = setInterval(() => loadAllData(true), 30000)
    return () => clearInterval(interval)
  }, [])

  const fmt = (iso) => {
    return formatPoliTimestamp(iso, 'Never')
  }

  return (
    <div className="space-y-10 sm:space-y-12">
      {/* ── Dashboard Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E5E5E5]">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-bold tracking-widest uppercase px-3 py-1 rounded-full bg-[#111111] text-white">
            Overview
          </span>
          <span className="text-xs font-medium text-[#767676] flex items-center gap-1.5">
            <Clock size={13} className="text-[#999999]" />
            <span>Last sync:</span>
            <strong className="text-[#111111] font-semibold">
              {stats?.timestamp ? fmt(stats.timestamp) : 'Just now'}
            </strong>
          </span>
        </div>

        <button
          onClick={() => loadAllData(true)}
          disabled={refreshing}
          className="btn btn-secondary btn-sm text-xs font-semibold self-start sm:self-auto cursor-pointer flex items-center gap-1.5"
          title="Refresh dashboard metrics"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          <span>{refreshing ? 'Refreshing…' : 'Refresh Metrics'}</span>
        </button>
      </div>

      {error && (
        <div className="alert alert-error" role="alert">
          <AlertCircle size={16} className="shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => loadAllData()}>
            Retry
          </button>
        </div>
      )}

      {/* ── Premium Editorial Hero Section ── */}
      <section className="relative overflow-hidden rounded-3xl bg-[#F8F9FA] border border-[#E5E5E5] p-8 sm:p-12 lg:p-16">
        <div className="max-w-2xl space-y-5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-[#E5E5E5] text-[11px] font-bold tracking-wider uppercase text-[#162238] shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-[#C9A15A]" />
            <span>Political News Aggregation &amp; Studio</span>
          </div>

          <h1 className="text-2xl sm:text-3xl lg:text-4xl xl:text-5xl font-black tracking-tight uppercase leading-[1.08] text-[#111111] max-w-xl">
            STAY AHEAD OF THE HEADLINES
          </h1>

          <p className="text-xs sm:text-sm lg:text-base text-[#555555] font-normal leading-relaxed max-w-lg">
            Review collected political reporting, create high-resolution visual assets, and manage your Facebook editorial workflow from one workspace.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              onClick={() => onNavigate && onNavigate('feed')}
              className="btn btn-primary h-11 px-6 rounded-full text-xs sm:text-sm font-bold flex items-center gap-2 cursor-pointer shadow-xs hover:shadow"
            >
              <span>Explore News</span>
              <ArrowRight size={14} />
            </button>
            <button
              onClick={() => onNavigate && onNavigate('studio')}
              className="btn btn-secondary h-11 px-6 rounded-full text-xs sm:text-sm font-bold flex items-center gap-2 cursor-pointer"
            >
              <PenSquare size={14} />
              <span>Create Post</span>
            </button>
          </div>
        </div>
      </section>

      {/* ── Key Metrics Overview Grid ── */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#111111]">
            System Metrics
          </h2>
          <span className="text-xs text-[#767676]">Live tracking</span>
        </div>

        {/* Responsive Grid: Desktop 4 cols, Tablet 2 cols, Mobile 1 col */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Active Articles */}
          <div
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate?.('feed') } }}
            onClick={() => onNavigate && onNavigate('feed')}
            className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between h-[170px] sm:h-[180px] cursor-pointer hover:border-[#111111] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 transition-all duration-200 group shadow-2xs"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider uppercase text-[#767676] group-hover:text-[#111111] transition-colors">
                Active Articles
              </span>
              <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#767676] group-hover:text-[#111111] group-hover:border-[#111111] transition-all shrink-0">
                <Newspaper size={16} />
              </div>
            </div>
            <div className="text-3xl sm:text-4xl font-extrabold text-[#111111] tracking-tight my-1">
              {loading ? <div className="spinner" /> : (stats?.total_active_articles ?? 0)}
            </div>
            <p className="text-xs text-[#767676] truncate">In 30-day retention pool</p>
          </div>

          {/* Collected Today */}
          <div
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate?.('feed') } }}
            onClick={() => onNavigate && onNavigate('feed')}
            className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between h-[170px] sm:h-[180px] cursor-pointer hover:border-[#111111] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 transition-all duration-200 group shadow-2xs"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider uppercase text-[#767676] group-hover:text-[#111111] transition-colors">
                Collected Today
              </span>
              <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#767676] group-hover:text-[#111111] group-hover:border-[#111111] transition-all shrink-0">
                <TrendingUp size={16} />
              </div>
            </div>
            <div className="text-3xl sm:text-4xl font-extrabold text-[#111111] tracking-tight my-1">
              {loading ? <div className="spinner" /> : (stats?.articles_collected_today ?? 0)}
            </div>
            <p className="text-xs text-[#767676] truncate">Classified political news</p>
          </div>

          {/* Pending Drafts */}
          <div
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate?.('drafts') } }}
            onClick={() => onNavigate && onNavigate('drafts')}
            className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between h-[170px] sm:h-[180px] cursor-pointer hover:border-[#111111] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 transition-all duration-200 group shadow-2xs"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider uppercase text-[#767676] group-hover:text-[#111111] transition-colors">
                Pending Drafts
              </span>
              <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#767676] group-hover:text-[#111111] group-hover:border-[#111111] transition-all shrink-0">
                <FileText size={16} />
              </div>
            </div>
            <div className="text-3xl sm:text-4xl font-extrabold text-[#111111] tracking-tight my-1">
              {loading ? <div className="spinner" /> : (stats?.draft_posts ?? 0)}
            </div>
            <p className="text-xs text-[#767676] truncate">{stats?.approved_posts ?? 0} ready to publish</p>
          </div>

          {/* Published Posts */}
          <div
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate?.('published') } }}
            onClick={() => onNavigate && onNavigate('published')}
            className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between h-[170px] sm:h-[180px] cursor-pointer hover:border-[#111111] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 transition-all duration-200 group shadow-2xs"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider uppercase text-[#767676] group-hover:text-[#111111] transition-colors">
                Published Posts
              </span>
              <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#767676] group-hover:text-[#111111] group-hover:border-[#111111] transition-all shrink-0">
                <Send size={16} />
              </div>
            </div>
            <div className="text-3xl sm:text-4xl font-extrabold text-[#111111] tracking-tight my-1">
              {loading ? <div className="spinner" /> : (stats?.published_posts ?? 0)}
            </div>
            <p className="text-xs text-[#767676] truncate">Published to Facebook</p>
          </div>
        </div>
      </section>

      {/* ── Latest Political News Section ── */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#111111]">
              Latest Political News
            </h2>
            <p className="text-xs text-[#767676] mt-0.5">
              Collected stories ready for editorial review
            </p>
          </div>
          {onNavigate && (
            <button
              onClick={() => onNavigate('feed')}
              className="text-xs font-bold tracking-wide uppercase text-[#111111] hover:underline flex items-center gap-1 cursor-pointer"
            >
              <span>View All</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>

        {loading ? (
          <div className="p-12 text-center text-[#767676] bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
            <div className="spinner mx-auto mb-3" />
            <p className="text-xs font-semibold uppercase tracking-wider">Loading latest articles…</p>
          </div>
        ) : recentArticles.length === 0 ? (
          <div className="p-10 text-center bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
            <Newspaper size={28} className="mx-auto mb-3 text-[#767676]" />
            <h3 className="text-sm font-bold text-[#111111]">No articles collected yet</h3>
            <p className="text-xs text-[#767676] mt-1 mb-4">Add RSS sources to begin collecting political news automatically.</p>
            {onNavigate && (
              <button onClick={() => onNavigate('sources')} className="btn btn-primary btn-sm">
                Configure News Sources
              </button>
            )}
          </div>
        ) : (
          /* 2-Column Desktop Card Grid with 24px (gap-6) spacing */
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {recentArticles.map(article => (
              <div
                key={article.id}
                className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between hover:border-[#111111] transition-all duration-200 group shadow-2xs min-h-[260px]"
              >
                {/* Article Header & Excerpt */}
                <div className="flex-1 flex flex-col">
                  {/* Publisher & Category Row */}
                  <div className="flex items-center justify-between text-xs gap-2 mb-3">
                    <span className="font-bold text-[#162238] uppercase tracking-wider text-[11px] truncate flex items-center gap-1.5">
                      <Building size={12} className="text-[#C9A15A] shrink-0" />
                      <span className="truncate">{article.publisher_name || 'Publisher'}</span>
                    </span>
                    <span className="badge badge-neutral text-[10px] shrink-0">
                      {article.category || 'General'}
                    </span>
                  </div>

                  {/* Headline */}
                  <h3 className="text-base sm:text-lg font-bold text-[#111111] leading-snug line-clamp-2 mb-2 group-hover:text-[#162238] transition-colors">
                    {article.headline}
                  </h3>

                  {/* Summary Snippet */}
                  <p className="text-xs text-[#555555] line-clamp-2 leading-relaxed mb-4">
                    {article.description || 'No summary snippet provided by publisher.'}
                  </p>
                </div>

                {/* Separated Action Footer (Aligned at Bottom) */}
                <div className="pt-4 border-t border-[#E5E5E5] flex items-center justify-between mt-auto">
                  <span className="text-[11px] font-medium text-[#767676] flex items-center gap-1">
                    <Clock size={12} />
                    {fmt(article.published_at || article.collected_at)}
                  </span>

                  <div className="flex items-center gap-2">
                    <a
                      href={article.original_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 rounded-full hover:bg-[#F8F9FA] text-[#767676] hover:text-[#111111] border border-transparent hover:border-[#E5E5E5] transition-colors cursor-pointer"
                      title="View original article"
                    >
                      <ExternalLink size={14} />
                    </a>
                    <ArticlePublishingActions article={article} onNavigate={onNavigate} onViewDraft={onViewDraft} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Two-Column Bottom Grid: Drafts & System Health ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        {/* Recent Editorial Drafts Card */}
        <section className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between space-y-4 shadow-2xs">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E5]">
              <div className="flex items-center gap-2.5">
                <FileText size={18} className="text-[#111111]" />
                <h2 className="text-base font-bold text-[#111111]">
                  Recent Editorial Drafts
                </h2>
              </div>
              {onNavigate && (
                <button
                  onClick={() => onNavigate('drafts')}
                  className="text-xs font-semibold text-[#767676] hover:text-[#111111] hover:underline cursor-pointer"
                >
                  View Queue →
                </button>
              )}
            </div>

            {recentDrafts.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#767676]">
                <FileText size={28} className="mx-auto mb-2 text-[#C5C5C5]" />
                <p>No drafts in progress. Create your first graphic in Post Studio.</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recentDrafts.map(draft => (
                  <div
                    key={draft.id}
                    className="flex items-center justify-between p-3 rounded-xl bg-[#F8F9FA] border border-[#E5E5E5]"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="text-xs font-bold text-[#111111] truncate">
                        {draft.headline_override || draft.article_headline || `Draft #${draft.id}`}
                      </p>
                      <p className="text-[11px] text-[#767676] mt-0.5">
                        Template: {draft.template_id} • {fmt(draft.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`badge text-[10px] ${
                        draft.status === 'APPROVED' ? 'badge-success' : 'badge-warning'
                      }`}>
                        {draft.status}
                      </span>
                      {onNavigate && (
                        <button
                          onClick={() => onNavigate('drafts')}
                          className="btn btn-secondary btn-sm py-1 px-2.5 text-xs cursor-pointer"
                        >
                          Review
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {onNavigate && (
            <div className="pt-3 border-t border-[#E5E5E5] flex justify-end">
              <button
                onClick={() => onNavigate('studio')}
                className="btn btn-secondary btn-sm text-xs cursor-pointer"
              >
                <PenSquare size={12} />
                <span>Open Post Studio</span>
              </button>
            </div>
          )}
        </section>

        {/* System & Automation Status Card */}
        <section className="card p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between space-y-4 shadow-2xs">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E5]">
              <div className="flex items-center gap-2.5">
                <Activity size={18} className="text-[#111111]" />
                <h2 className="text-base font-bold text-[#111111]">
                  System &amp; Policy Status
                </h2>
              </div>
              <span className={`badge text-[10px] ${schedulerStatus?.running ? 'badge-success' : schedulerStatus === null ? 'badge-neutral' : 'badge-warning'}`} role="status">
                {schedulerStatus === null ? 'Unavailable' : schedulerStatus.running ? 'Running' : 'Stopped'}
              </span>
            </div>

            <div className="divide-y divide-[#E5E5E5] text-xs">
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-[#767676]">Last News Fetch</span>
                <span className="font-semibold text-[#111111]">
                  {fmt(stats?.last_successful_fetch)}
                </span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-[#767676]">News Retention Policy</span>
                <span className="font-semibold text-[#111111]">30 Days Rolling</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-[#767676]">Storage Used / Free</span>
                <span className="font-semibold text-[#111111]">
                  {stats?.storage_used_mb ?? 0} MB / {stats?.storage_free_mb ?? 0} MB
                </span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-[#767676]">Background Scheduler</span>
                <span className={`font-semibold flex items-center gap-1.5 ${schedulerStatus?.running ? 'text-[#15803D]' : 'text-[#767676]'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${schedulerStatus?.running ? 'bg-[#15803D]' : 'bg-[#767676]'}`} />
                  {schedulerStatus === null ? 'Status unavailable' : schedulerStatus.running ? 'Running' : 'Stopped'}
                </span>
              </div>
            </div>
          </div>

          {onNavigate && (
            <div className="pt-3 border-t border-[#E5E5E5] flex justify-end">
              <button
                onClick={() => onNavigate('settings')}
                className="btn btn-secondary btn-sm text-xs cursor-pointer"
              >
                <span>View Full Retention Policy</span>
                <ArrowRight size={12} />
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
