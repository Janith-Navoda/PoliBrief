import { useState, useEffect } from 'react'
import {
  Newspaper, Search, RefreshCw, ExternalLink,
  ChevronLeft, ChevronRight, Clock, Building, X, ChevronDown
} from 'lucide-react'
import toast from 'react-hot-toast'
import { articlesApi, sourcesApi } from '../services/api'
import { formatPoliTimestamp } from '../utils/dateTime'
import ArticlePublishingActions from '../components/ArticlePublishingActions'

const CATEGORIES = [
  'All Categories',
  'Government and Policy',
  'Parliament',
  'Elections',
  'International Politics',
  'Economy and Policy',
  'Political Analysis',
  'Other / Needs Review',
]

export default function NewsFeedPage({ onNavigate, onViewDraft }) {
  const [articles, setArticles] = useState([])
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [sourcesError, setSourcesError] = useState('')

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All Categories')
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [statusFilter, setStatusFilter] = useState('ACTIVE')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  // Load sources for publisher dropdown
  const fetchSources = async () => {
    setSourcesError('')
    try {
      const res = await sourcesApi.list()
      setSources(res.data)
    } catch {
      setSourcesError('Could not load publishers.')
    }
  }

  useEffect(() => { fetchSources() }, [])

  // Load articles
  const fetchArticles = async (targetPage = page) => {
    try {
      setLoading(true)
      const params = {
        page: targetPage,
        page_size: 16,
        status: statusFilter,
      }
      if (searchQuery.trim()) params.q = searchQuery.trim()
      if (selectedCategory !== 'All Categories') params.category = selectedCategory
      if (selectedSourceId) params.source_id = Number(selectedSourceId)
      if (dateFrom && statusFilter === 'ACTIVE') {
        params.date_from = new Date(`${dateFrom}T00:00:00`).toISOString()
      }
      if (dateTo && statusFilter === 'ACTIVE') {
        params.date_to = new Date(`${dateTo}T23:59:59.999`).toISOString()
      }

      setError('')
      const res = await articlesApi.list(params)
      setArticles(res.data.items)
      setTotalPages(res.data.total_pages)
      setTotalCount(res.data.total)
      setPage(res.data.page)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load articles. Check the connection and try again.')
    } finally {
      setLoading(false)
    }
  }

  // Trigger search on filter change (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchArticles(1)
    }, 250)
    return () => clearTimeout(timer)
  }, [searchQuery, selectedCategory, selectedSourceId, statusFilter, dateFrom, dateTo])

  // Manual news refresh
  const handleRefreshNews = async () => {
    try {
      setRefreshing(true)
      const res = await sourcesApi.refreshAll()
      const newArticles = res.data.result?.new_articles ?? 0
      toast.success(`News collection complete: ${newArticles} new articles ingested.`)
      fetchArticles(1)
    } catch (err) {
      toast.error('News collection failed')
    } finally {
      setRefreshing(false)
    }
  }

  // Quick category update (preserving existing feature)
  const handleCategoryChange = async (articleId, newCategory) => {
    try {
      await articlesApi.update(articleId, { category: newCategory })
      setArticles(articles.map(a => a.id === articleId ? { ...a, category: newCategory } : a))
      toast.success('Article category updated')
    } catch (err) {
      toast.error('Failed to update category')
    }
  }

  const markDateReviewed = async (article) => {
    try {
      await articlesApi.update(article.id, { status: 'ACTIVE' })
      setArticles(items => items.filter(item => item.id !== article.id))
      setTotalCount(count => Math.max(0, count - 1))
      toast.success('Review flag cleared. The original publication date remains unverified.')
    } catch {
      toast.error('Could not update the review status. Try again.')
    }
  }

  const formatTime = (isoString) => {
    return formatPoliTimestamp(isoString, '')
  }

  const hasActiveFilters = searchQuery || selectedCategory !== 'All Categories' || selectedSourceId ||
    statusFilter !== 'ACTIVE' || dateFrom || dateTo

  return (
    <div className="space-y-8 sm:space-y-10">
      {/* ── Structured Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#E5E5E5]">
        <div className="space-y-1 max-w-2xl">
          <span className="text-xs font-bold tracking-widest uppercase text-[#767676] block">
            Curated Feed
          </span>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
            Political News Feed
          </h1>
          <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mt-1">
            Political news collected from configured publishers, classified, and checked for duplicates.
          </p>
        </div>

        {/* Action Button: Aligned properly on desktop, stacks below heading on mobile */}
        <div className="shrink-0 w-full sm:w-auto self-start md:self-end">
          <button
            onClick={handleRefreshNews}
            disabled={refreshing}
            className="btn btn-primary text-xs w-full sm:w-auto h-10 px-5 flex items-center justify-center gap-2 cursor-pointer shadow-xs hover:shadow"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Collecting Feeds…' : 'Fetch Latest News'}</span>
          </button>
        </div>
      </div>

      {/* ── Restrained Pill-Shaped Category Filters ── */}
      <div className="flex items-center gap-2.5 overflow-x-auto pb-2 scrollbar-none pt-1">
        {CATEGORIES.map(category => {
          const isSelected = selectedCategory === category
          return (
              <button
              key={category}
                type="button"
                aria-pressed={isSelected}
              onClick={() => setSelectedCategory(category)}
              className={`h-9 px-4 rounded-full text-xs font-bold whitespace-nowrap transition-all duration-150 cursor-pointer border shrink-0 flex items-center justify-center ${
                isSelected
                  ? 'bg-[#111111] text-white border-[#111111] shadow-2xs'
                  : 'bg-white text-[#666666] border-[#E5E5E5] hover:border-[#111111] hover:text-[#111111] hover:bg-[#F8F9FA]'
              }`}
            >
              {category}
            </button>
          )
        })}
      </div>

      {/* ── Filter Toolbar (Search & Publisher Dropdown) ── */}
      <div className="card p-5 sm:p-6 bg-[#F8F9FA] border border-[#E5E5E5] rounded-2xl space-y-4 shadow-2xs">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-12 gap-3.5">
          {/* Keyword Search (Wide field on desktop) */}
          <div className="xl:col-span-5 relative flex items-center min-w-0">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#767676] pointer-events-none" />
            <input
              type="text"
              aria-label="Search articles"
              placeholder="Search political headlines, legislation, candidates, keywords…"
              className="w-full h-11 pl-10 pr-4 text-xs sm:text-sm bg-white border border-[#E5E5E5] rounded-xl focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none text-[#111111] placeholder:text-[#999999] transition-all"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Publisher Select (Compact on desktop, stacks vertically on mobile) */}
          <div className="xl:col-span-3 relative flex items-center min-w-0">
            <select
              aria-label="Filter by publisher"
              className="w-full h-11 px-4 pr-10 text-xs sm:text-sm bg-white border border-[#E5E5E5] rounded-xl focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none text-[#111111] cursor-pointer appearance-none transition-all"
              value={selectedSourceId}
              onChange={e => setSelectedSourceId(e.target.value)}
            >
              <option value="">All Publishers</option>
              {sources.map(s => (
                <option key={s.id} value={s.id}>{s.publisher_name}</option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#767676] pointer-events-none" />
          </div>

          <div className="xl:col-span-2">
            <label className="sr-only" htmlFor="article-status-filter">Article review status</label>
            <select
              id="article-status-filter"
              className="w-full h-11 px-4 text-xs sm:text-sm bg-white border border-[#E5E5E5] rounded-xl focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none text-[#111111]"
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
            >
              <option value="ACTIVE">Active news</option>
              <option value="DATE_REVIEW">Date review queue</option>
            </select>
          </div>

          <div className="md:col-span-2 xl:col-span-12 grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-w-2xl">
            <div>
              <label htmlFor="date-from" className="form-label">Published from</label>
              <input id="date-from" type="date" className="form-input h-11" value={dateFrom}
                max={dateTo || undefined} disabled={statusFilter === 'DATE_REVIEW'}
                onChange={e => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label htmlFor="date-to" className="form-label">Published through</label>
              <input id="date-to" type="date" className="form-input h-11" value={dateTo}
                min={dateFrom || undefined} disabled={statusFilter === 'DATE_REVIEW'}
                onChange={e => setDateTo(e.target.value)} />
            </div>
          </div>
        </div>

        {sourcesError && (
          <div className="alert alert-warning" role="alert">
            <span className="flex-1">{sourcesError}</span>
            <button type="button" className="font-semibold underline" onClick={fetchSources}>Retry</button>
          </div>
        )}

        {/* Filter Results Info & Clear Action */}
        <div className="flex items-center justify-between text-xs text-[#767676] pt-3 border-t border-[#E5E5E5]">
          <span>
            Found <strong className="text-[#111111]">{totalCount}</strong> political articles
          </span>

          {hasActiveFilters && (
            <button
              onClick={() => {
                setSearchQuery('')
                setSelectedCategory('All Categories')
                setSelectedSourceId('')
                setStatusFilter('ACTIVE')
                setDateFrom('')
                setDateTo('')
              }}
              className="text-xs font-semibold text-[#111111] hover:underline flex items-center gap-1 cursor-pointer"
            >
              <X size={12} />
              <span>Clear filters</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Articles Feed Grid ── */}
      {error && !loading && (
        <div className="alert alert-error" role="alert">
          <span className="flex-1">{error}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => fetchArticles(1)}>Retry</button>
        </div>
      )}
      {loading ? (
        <div className="py-24 text-center text-[#767676] bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
          <div className="spinner spinner-lg mx-auto mb-3" />
          <p className="text-xs font-semibold tracking-wider uppercase">Loading political articles…</p>
        </div>
      ) : articles.length === 0 ? (
        <div className="card text-center py-20 px-6 border-[#E5E5E5] bg-[#F8F9FA] rounded-2xl">
          <Newspaper size={36} className="mx-auto mb-3 text-[#767676]" />
          <h3 className="text-lg font-bold text-[#111111]">No Articles Found</h3>
          <p className="text-xs text-[#767676] max-w-md mx-auto mt-1 mb-6">
            No political news matches your current filter criteria. Try adjusting keywords or refreshing RSS feeds.
          </p>
          <button onClick={handleRefreshNews} className="btn btn-primary btn-sm mx-auto cursor-pointer">
            <RefreshCw size={13} />
            <span>Fetch News Now</span>
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Single-column article list with consistent 24px (gap-6) row spacing */}
          <div className="grid grid-cols-1 gap-6">
            {articles.map(article => (
              <article
                key={article.id}
                className="card p-6 sm:p-7 bg-white border border-[#E5E5E5] rounded-2xl hover:border-[#111111] transition-all duration-200 flex flex-col justify-between shadow-2xs group"
              >
                {/* Article Header & Main Content */}
                <div className="flex-1 flex flex-col">
                  {/* Top metadata strip: Publisher & Category Dropdown */}
                  <div className="flex items-center justify-between text-xs gap-3 mb-3.5 min-w-0">
                    <span className="font-bold text-[#162238] uppercase tracking-wider text-xs flex items-center gap-1.5 truncate min-w-0">
                      <Building size={13} className="text-[#C9A15A] shrink-0" />
                      <span className="truncate">{article.publisher_name || 'Publisher'}</span>
                    </span>

                    {/* Inline Category Select (Well-spaced chip) */}
                    <div className="shrink-0">
                      <select
                        aria-label={`Change category for ${article.headline}`}
                        value={article.category}
                        onChange={e => handleCategoryChange(article.id, e.target.value)}
                        className="text-[11px] font-semibold text-[#666666] bg-[#F8F9FA] border border-[#E5E5E5] rounded-full px-3 py-1 cursor-pointer hover:border-[#111111] hover:text-[#111111] outline-none transition-colors"
                        title="Click to adjust classification"
                      >
                        {CATEGORIES.filter(c => c !== 'All Categories').map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {article.status === 'DATE_REVIEW' && (
                    <p className="badge badge-warning text-[10px] self-start mb-2" role="status">
                      Publication date needs review
                    </p>
                  )}

                  {/* Headline */}
                  <h2 className="text-base sm:text-lg font-bold text-[#111111] leading-snug hover:text-[#162238] transition-colors line-clamp-2 mb-2.5">
                    <a href={article.original_url} target="_blank" rel="noopener noreferrer">
                      {article.headline}
                    </a>
                  </h2>

                  {/* Summary Snippet with readable spacing */}
                  <p className="text-xs sm:text-sm text-[#555555] line-clamp-2 leading-relaxed mb-6">
                    {article.description || 'No excerpt available for this article.'}
                  </p>
                </div>

                {/* Card Footer: Timestamp & Action Buttons (Aligned to bottom) */}
                <div className="pt-4 border-t border-[#E5E5E5] flex items-center justify-between text-xs mt-auto">
                      <span className="text-[#767676] flex items-center gap-1.5 text-xs font-medium">
                    <Clock size={13} className="text-[#999999]" />
                    {article.published_at ? formatTime(article.published_at) : 'Publication date unverified'}
                  </span>

                  <div className="flex items-center gap-2">
                    <a
                      href={article.original_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-[#767676] hover:text-[#111111] rounded-full hover:bg-[#F8F9FA] border border-transparent hover:border-[#E5E5E5] transition-colors cursor-pointer"
                      title="Read original source"
                    >
                      <ExternalLink size={14} />
                    </a>
                    {statusFilter !== 'DATE_REVIEW' && (
                      <ArticlePublishingActions article={article} onNavigate={onNavigate} onViewDraft={onViewDraft} />
                    )}
                    {statusFilter === 'DATE_REVIEW' && (
                      <button
                        type="button"
                        onClick={() => markDateReviewed(article)}
                        className="btn btn-secondary btn-sm text-xs py-1.5 px-3"
                        aria-label={`Clear review flag for ${article.headline}; publication date remains unverified`}
                      >
                        Clear review flag
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>

          {/* ── Pagination Controls ── */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-8 border-t border-[#E5E5E5] text-xs text-[#767676]">
              <div>
                Page <strong className="text-[#111111]">{page}</strong> of <strong className="text-[#111111]">{totalPages}</strong>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchArticles(page - 1)}
                  disabled={page <= 1}
                  className="btn btn-secondary btn-sm h-9 px-3 flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                  title="Previous Page"
                >
                  <ChevronLeft size={16} />
                  <span className="hidden sm:inline">Previous</span>
                </button>
                <button
                  onClick={() => fetchArticles(page + 1)}
                  disabled={page >= totalPages}
                  className="btn btn-secondary btn-sm h-9 px-3 flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                  title="Next Page"
                >
                  <span className="hidden sm:inline">Next</span>
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
