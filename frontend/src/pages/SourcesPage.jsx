import { useState, useEffect } from 'react'
import {
  Radio, Plus, RefreshCw, CheckCircle, AlertCircle, Clock,
  ExternalLink, Trash2, Edit3, Check, X, Loader2, Sparkles
} from 'lucide-react'
import toast from 'react-hot-toast'
import { sourcesApi } from '../services/api'
import { getCollectionFeedback } from './collectionFeedback'
import { formatPoliTimestamp } from '../utils/dateTime'
import { getSourcePolicyDisplay } from '../utils/sourcePolicy'

export default function SourcesPage() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [refreshingAll, setRefreshingAll] = useState(false)
  const [actionSourceId, setActionSourceId] = useState(null)

  // Add / Edit Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState(null)
  const [formData, setFormData] = useState({
    publisher_name: '',
    rss_url: '',
    website_url: '',
    language: 'en',
    enabled: true,
    content_restrictions: '',
  })
  const [testingUrl, setTestingUrl] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [saving, setSaving] = useState(false)

  // Load sources
  const fetchSources = async () => {
    try {
      setLoadError('')
      setLoading(true)
      const res = await sourcesApi.list()
      setSources(res.data)
    } catch (err) {
      setLoadError('Failed to load news sources.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  // Refresh All Sources
  const handleRefreshAll = async () => {
    try {
      setRefreshingAll(true)
      const res = await sourcesApi.refreshAll()
      const result = res.data.result || {}
      const feedback = getCollectionFeedback(result)
      toast[feedback.type](feedback.message)
      await fetchSources()
    } catch (err) {
      toast.error('Failed to refresh news sources')
    } finally {
      setRefreshingAll(false)
    }
  }

  // Refresh Single Source
  const handleRefreshSingle = async (source) => {
    try {
      setActionSourceId(source.id)
      const res = await sourcesApi.refresh(source.id)
      const result = res.data.result || {}
      const feedback = getCollectionFeedback(result, source)
      toast[feedback.type](feedback.message)
      await fetchSources()
    } catch (err) {
      toast.error(`Refresh failed for ${source.publisher_name}`)
    } finally {
      setActionSourceId(null)
    }
  }

  // Test Single Existing Source
  const handleTestSource = async (source) => {
    try {
      setActionSourceId(source.id)
      const res = await sourcesApi.testSource(source.id)
      if (res.data.valid) {
        toast.success(`Feed verified! Found ${res.data.entry_count} entries.`)
      } else {
        toast.error(`Feed verification failed: ${res.data.message}`)
      }
    } catch (err) {
      toast.error('Could not test feed connectivity')
    } finally {
      setActionSourceId(null)
    }
  }

  // Toggle Source Enabled
  const handleToggleEnabled = async (source) => {
    try {
      const updated = !source.enabled
      await sourcesApi.update(source.id, { enabled: updated })
      setSources(sources.map(s => s.id === source.id ? { ...s, enabled: updated } : s))
      toast.success(`${source.publisher_name} ${updated ? 'enabled' : 'disabled'}`)
    } catch (err) {
      toast.error('Failed to update source status')
    }
  }

  // Delete Source
  const handleDeleteSource = async (source) => {
    if (!window.confirm(`Are you sure you want to delete "${source.publisher_name}"? Existing collected articles will be preserved.`)) {
      return
    }
    try {
      await sourcesApi.delete(source.id)
      setSources(sources.filter(s => s.id !== source.id))
      toast.success(`Deleted ${source.publisher_name}`)
    } catch (err) {
      toast.error('Failed to delete source')
    }
  }

  // Seed Defaults
  const handleSeedDefaults = async () => {
    try {
      const res = await sourcesApi.seedDefaults()
      if (res.data.length > 0) {
        toast.success(`Added ${res.data.length} reputable default political feeds.`)
        fetchSources()
      } else {
        toast('Default feeds are already added.', { icon: 'ℹ️' })
      }
    } catch (err) {
      toast.error('Failed to seed default sources')
    }
  }

  // Open Create Modal
  const openCreateModal = () => {
    setEditingSource(null)
    setFormData({
      publisher_name: '',
      rss_url: '',
      website_url: '',
      language: 'en',
      enabled: true,
      content_restrictions: '',
    })
    setTestResult(null)
    setModalOpen(true)
  }

  // Open Edit Modal
  const openEditModal = (source) => {
    setEditingSource(source)
    setFormData({
      publisher_name: source.publisher_name,
      rss_url: source.rss_url,
      website_url: source.website_url || '',
      language: source.language || 'en',
      enabled: source.enabled,
      content_restrictions: source.content_restrictions || '',
    })
    setTestResult(null)
    setModalOpen(true)
  }

  // Test URL in Modal
  const handleTestUrlInModal = async () => {
    if (!formData.rss_url) {
      toast.error('Please enter an RSS URL to test')
      return
    }
    try {
      setTestingUrl(true)
      const res = await sourcesApi.testUrl(formData.rss_url.trim())
      setTestResult(res.data)
      if (res.data.valid) {
        toast.success(`Verified: ${res.data.entry_count} entries found!`)
        if (!formData.publisher_name && res.data.title) {
          setFormData(prev => ({ ...prev, publisher_name: res.data.title }))
        }
      } else {
        toast.error(res.data.message || 'Feed validation failed')
      }
    } catch (err) {
      setTestResult({ valid: false, message: 'Connection error while testing URL' })
      toast.error('Failed to test feed URL')
    } finally {
      setTestingUrl(false)
    }
  }

  // Save Modal
  const handleSaveModal = async (e) => {
    e.preventDefault()
    if (!formData.publisher_name.trim() || !formData.rss_url.trim()) {
      toast.error('Publisher name and RSS URL are required')
      return
    }

    try {
      setSaving(true)
      if (editingSource) {
        await sourcesApi.update(editingSource.id, formData)
        toast.success(`Updated ${formData.publisher_name}`)
      } else {
        await sourcesApi.create(formData)
        toast.success(`Added ${formData.publisher_name}`)
      }
      setModalOpen(false)
      fetchSources()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to save news source'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const formatTimestamp = (isoString) => {
    return formatPoliTimestamp(isoString, 'Never')
  }

  // Clean, user-friendly display of error messages
  const cleanErrorMessage = (msg) => {
    if (!msg) return null
    if (msg.includes('IntegrityError') || msg.includes('duplicate_fingerprints')) {
      return 'Notice: Feed entries are already indexed or deduplicated.'
    }
    if (msg.length > 90) {
      return msg.slice(0, 90) + '…'
    }
    return msg
  }

  return (
    <div className="space-y-8 sm:space-y-10">
      {loadError && <div className="alert alert-error" role="alert"><span className="flex-1">{loadError}</span><button type="button" className="underline font-semibold" onClick={fetchSources}>Retry</button></div>}
      {/* ── Standardized Page Header ── */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 pb-6 sm:pb-8 border-b border-[#E5E5E5]">
        <div className="space-y-1 max-w-2xl">
          <span className="text-xs font-bold tracking-widest uppercase text-[#767676] block mb-1">
            Data Ingestion
          </span>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
            News Sources
          </h1>
          <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mt-1">
            Configure RSS feeds, monitor fetch health, and trigger manual collection runs.
          </p>
        </div>

        {/* Action Buttons in a clean row */}
        <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap lg:flex-nowrap shrink-0 self-start lg:self-end">
          <button
            onClick={handleSeedDefaults}
            className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 shadow-2xs hover:shadow-xs transition-colors"
            title="Pre-populate NPR, BBC, and PBS feeds"
          >
            <Sparkles size={13} className="text-[#C9A15A]" />
            <span>Seed Feeds</span>
          </button>

          <button
            onClick={handleRefreshAll}
            disabled={refreshingAll}
            className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-2 shadow-2xs hover:shadow-xs transition-colors"
          >
            <RefreshCw size={13} className={refreshingAll ? 'animate-spin' : ''} />
            <span>{refreshingAll ? 'Collecting…' : 'Refresh All'}</span>
          </button>

          <button
            onClick={openCreateModal}
            className="btn btn-primary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 shadow-xs hover:shadow transition-colors"
          >
            <Plus size={14} />
            <span>Add Source</span>
          </button>
        </div>
      </div>

      {/* ── Sources List or Centered Empty State ── */}
      {loading ? (
        <div className="py-24 text-center text-[#767676] bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
          <div className="spinner spinner-lg mx-auto mb-3" />
          <p className="text-xs font-semibold tracking-wider uppercase">Loading news sources…</p>
        </div>
      ) : sources.length === 0 ? (
        <div className="card py-12 sm:py-16 px-6 border border-[#E5E5E5] bg-[#F8F9FA] rounded-2xl flex flex-col items-center justify-center text-center shadow-2xs">
          <div className="w-full max-w-[480px] flex flex-col items-center">
            <div className="w-14 h-14 rounded-2xl bg-white border border-[#E5E5E5] flex items-center justify-center text-[#162238] mb-5 shadow-xs">
              <Radio size={24} className="text-[#162238]" />
            </div>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] mb-2 tracking-tight">
              No News Sources Configured
            </h2>
            <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mb-6">
              PoliBrief collects articles from permitted RSS feeds. You can add your own custom publisher or seed standard public political feeds.
            </p>
            <div className="flex items-center gap-3 flex-wrap justify-center">
              <button
                onClick={handleSeedDefaults}
                className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5"
              >
                <Sparkles size={13} className="text-[#C9A15A]" />
                <span>Add Default Feeds</span>
              </button>
              <button
                onClick={openCreateModal}
                className="btn btn-primary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
              >
                <Plus size={14} />
                <span>Add Custom Feed</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          {sources.map(source => {
            const isProcessing = actionSourceId === source.id
            const isError = source.status === 'ERROR'
            const isActive = source.status === 'ACTIVE'
            const userFriendlyError = cleanErrorMessage(source.error_message)
            const policyDisplay = getSourcePolicyDisplay(source.content_restrictions)

            return (
              <div
                key={source.id}
                className={`card p-5 sm:p-6 bg-white border border-[#E5E5E5] rounded-2xl transition-all duration-200 hover:border-[#111111] space-y-4 shadow-2xs ${
                  !source.enabled ? 'opacity-65 bg-[#FAFAFA]' : ''
                }`}
              >
                {/* ── Top Row: Publisher name, status badge, article count, enabled indicator ── */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#F0F0F0]">
                  <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap min-w-0">
                    <h3 className="text-base sm:text-lg font-bold text-[#111111] tracking-tight">
                      {source.publisher_name}
                    </h3>

                    {/* Status Badge */}
                    <span className={`badge text-[10px] font-bold uppercase tracking-wider ${
                      !source.enabled
                        ? 'badge-neutral'
                        : isError
                        ? 'badge-warning'
                        : isActive
                        ? 'badge-success'
                        : 'badge-warning'
                    }`}>
                      {!source.enabled ? 'Disabled' : isError ? 'Sync Notice' : isActive ? 'Active' : 'Pending'}
                    </span>

                    {/* Articles Count */}
                    <span className="text-xs font-semibold text-[#767676] bg-[#F8F9FA] px-2.5 py-0.5 rounded-full border border-[#E5E5E5]">
                      {source.article_count ?? 0} articles
                    </span>
                  </div>

                  {/* Enabled/Disabled Indicator Pill */}
                  <button
                    onClick={() => handleToggleEnabled(source)}
                    className={`text-xs font-semibold px-3 py-1 rounded-full border transition-colors inline-flex items-center gap-1.5 self-start sm:self-auto cursor-pointer ${
                      source.enabled
                        ? 'border-[#BBF7D0] bg-[#DCFCE7] text-[#15803D] hover:bg-[#BBF7D0]'
                        : 'border-[#E5E5E5] bg-[#F8F9FA] text-[#767676] hover:bg-[#EAEAEA]'
                    }`}
                    title={source.enabled ? 'Click to disable collection' : 'Click to enable collection'}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${source.enabled ? 'bg-[#15803D]' : 'bg-[#767676]'}`} />
                    <span>{source.enabled ? 'Enabled' : 'Disabled'}</span>
                  </button>
                </div>

                {/* ── Middle: RSS feed URL, Last successful fetch, Last checked timestamp ── */}
                <div className="space-y-3">
                  {/* Feed URL with website external link */}
                  <div className="flex items-center gap-2 text-xs text-[#767676] font-mono bg-[#F8F9FA] px-3.5 py-2.5 rounded-xl border border-[#E5E5E5] min-w-0">
                    <Radio size={13} className="text-[#C9A15A] shrink-0" />
                    <span className="truncate flex-1 select-all">{source.rss_url}</span>
                    {source.website_url && (
                      <a
                        href={source.website_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#162238] font-sans font-semibold hover:underline inline-flex items-center gap-1 shrink-0 text-xs pl-2.5 border-l border-[#E5E5E5]"
                        title="Visit publisher website"
                      >
                        <span>Website</span>
                        <ExternalLink size={11} />
                      </a>
                    )}
                  </div>

                  {/* Timestamps */}
                  <div className="flex items-center gap-4 sm:gap-6 flex-wrap text-xs text-[#767676]">
                    <div className="flex items-center gap-1.5">
                      <Clock size={12} className="text-[#999999]" />
                      <span>Last Success: <strong className="text-[#111111] font-semibold">{formatTimestamp(source.last_success)}</strong></span>
                    </div>
                    <span className="text-[#D4D4D4] hidden sm:inline">•</span>
                    <div className="flex items-center gap-1.5">
                      <Clock size={12} className="text-[#999999]" />
                      <span>Last Checked: <span className="font-medium">{formatTimestamp(source.last_checked)}</span></span>
                    </div>
                    {source.content_restrictions && (
                      <>
                        <span className="text-[#D4D4D4] hidden sm:inline">•</span>
                        <div className="flex items-center gap-1.5 flex-wrap" aria-label="Source policy metadata">
                          {policyDisplay.labels.map(label => (
                            <span key={label} className="badge badge-neutral text-[10px] font-medium">{label}</span>
                          ))}
                          {policyDisplay.notes.map((note, index) => (
                            <span key={`note-${index}`} className="text-xs text-[#767676]">{note}</span>
                          ))}
                          {policyDisplay.needsReview && (
                            <span className="badge badge-warning text-[10px] font-medium" title="Stored metadata is unknown or malformed; verify the source policy.">
                              Policy details need review
                            </span>
                          )}
                        </div>
                      </>
                    )}
                  </div>

                  {/* ── Warning & Error States ── */}
                  {isError && userFriendlyError && (
                    <div className="p-3.5 sm:p-4 rounded-xl text-xs bg-[#FEF3C7]/80 border border-[#FDE68A] text-[#92400E] flex items-start gap-2.5 shadow-2xs">
                      <AlertCircle size={16} className="shrink-0 mt-0.5 text-[#B45309]" />
                      <div className="space-y-0.5">
                        <span className="font-bold text-[#B45309] block">Synchronization Notice</span>
                        <span className="leading-relaxed block text-[#78350F]">{userFriendlyError}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* ── Bottom: Existing source action controls ── */}
                <div className="pt-3 border-t border-[#F0F0F0] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <span className="text-xs text-[#767676] font-medium hidden sm:inline">
                    {source.language ? `Feed Language: ${source.language.toUpperCase()}` : 'Source Controls'}
                  </span>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 flex-wrap self-end sm:self-auto w-full sm:w-auto justify-end">
                    <button
                      onClick={() => handleRefreshSingle(source)}
                      disabled={isProcessing || !source.enabled}
                      className="btn btn-secondary h-9 px-3 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                      title="Fetch news now"
                    >
                      <RefreshCw size={13} className={isProcessing ? 'animate-spin' : ''} />
                      <span>Fetch Now</span>
                    </button>

                    <button
                      onClick={() => handleTestSource(source)}
                      disabled={isProcessing}
                      className="btn btn-secondary h-9 px-3 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
                      title="Test RSS connection"
                    >
                      <CheckCircle size={13} className="text-[#15803D]" />
                      <span>Test Feed</span>
                    </button>

                    <button
                      onClick={() => openEditModal(source)}
                      className="btn btn-secondary h-9 px-3 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
                      title="Edit publisher"
                    >
                      <Edit3 size={13} />
                      <span>Edit</span>
                    </button>

                    <button
                      onClick={() => handleDeleteSource(source)}
                      className="btn btn-secondary h-9 px-3 text-xs font-semibold inline-flex items-center gap-1.5 text-[#B91C1C] hover:bg-[#FEE2E2] hover:border-[#FECACA] cursor-pointer transition-colors"
                      title="Delete publisher"
                    >
                      <Trash2 size={13} />
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Add / Edit Source Modal ── */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div role="dialog" aria-modal="true" aria-labelledby="source-dialog-title" className="card w-full max-w-lg p-6 sm:p-8 bg-white border border-[#E5E5E5] shadow-2xl rounded-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E5]">
              <h2 id="source-dialog-title" className="text-lg font-bold text-[#111111] tracking-tight">
                {editingSource ? 'Edit News Source' : 'Add News Source'}
              </h2>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-full text-[#767676] hover:text-[#111111] cursor-pointer"
                aria-label="Close news source dialog"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveModal} className="space-y-4">
              <div>
                <label htmlFor="publisher-name" className="form-label block text-xs font-bold text-[#111111] uppercase tracking-wider mb-1.5">
                  Publisher Name *
                </label>
                <input
                  id="publisher-name"
                  type="text"
                  required
                  placeholder="e.g. NPR Politics, Reuters, BBC"
                  className="form-input text-xs h-11"
                  value={formData.publisher_name}
                  onChange={e => setFormData({ ...formData, publisher_name: e.target.value })}
                />
              </div>

              <div>
                <label htmlFor="source-rss-url" className="form-label block text-xs font-bold text-[#111111] uppercase tracking-wider mb-1.5">
                  RSS / Atom Feed URL *
                </label>
                <div className="flex gap-2">
                  <input
                    id="source-rss-url"
                    type="url"
                    required
                    placeholder="https://example.com/rss.xml"
                    className="form-input text-xs font-mono h-11"
                    value={formData.rss_url}
                    onChange={e => {
                      setFormData({ ...formData, rss_url: e.target.value })
                      setTestResult(null)
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleTestUrlInModal}
                    disabled={testingUrl || !formData.rss_url}
                    className="btn btn-secondary h-11 px-3.5 text-xs font-semibold shrink-0 cursor-pointer inline-flex items-center gap-1.5"
                  >
                    {testingUrl ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                    <span>Test</span>
                  </button>
                </div>
              </div>

              {/* Feed Test Result Box */}
              {testResult && (
                <div className={`p-3.5 rounded-xl text-xs border ${
                  testResult.valid
                    ? 'bg-[#DCFCE7] border-[#BBF7D0] text-[#15803D]'
                    : 'bg-[#FEE2E2] border-[#FECACA] text-[#991B1B]'
                }`}>
                  <div className="font-bold flex items-center gap-1.5">
                    {testResult.valid ? <Check size={14} /> : <AlertCircle size={14} />}
                    <span>{testResult.message}</span>
                  </div>
                  {testResult.valid && testResult.sample_headlines?.length > 0 && (
                    <div className="mt-2 space-y-1 text-[#111111]">
                      <div className="text-[10px] uppercase font-bold tracking-wider text-[#767676]">Sample Headlines:</div>
                      <ul className="list-disc list-inside space-y-0.5 truncate text-[11px]">
                        {testResult.sample_headlines.slice(0, 3).map((h, i) => (
                          <li key={i} className="truncate">{h}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div>
                <label htmlFor="publisher-website-url" className="form-label block text-xs font-bold text-[#111111] uppercase tracking-wider mb-1.5">
                  Publisher Website URL (Optional)
                </label>
                <input
                  id="publisher-website-url"
                  type="url"
                  placeholder="https://example.com"
                  className="form-input text-xs font-mono h-11"
                  value={formData.website_url}
                  onChange={e => setFormData({ ...formData, website_url: e.target.value })}
                />
              </div>

              <div>
                <label htmlFor="content-restrictions" className="form-label block text-xs font-bold text-[#111111] uppercase tracking-wider mb-1.5">
                  Content Restrictions / License Notes (Optional)
                </label>
                <textarea
                  id="content-restrictions"
                  rows={2}
                  placeholder="e.g. Attribution required; no commercial resale."
                  className="form-input text-xs p-3"
                  value={formData.content_restrictions}
                  onChange={e => setFormData({ ...formData, content_restrictions: e.target.value })}
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="enabledCheck"
                  checked={formData.enabled}
                  onChange={e => setFormData({ ...formData, enabled: e.target.checked })}
                  className="rounded border-[#E5E5E5] text-[#111111] focus:ring-0 cursor-pointer"
                />
                <label htmlFor="enabledCheck" className="text-xs text-[#767676] select-none cursor-pointer">
                  Enable automatic collection every 30 minutes
                </label>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-[#E5E5E5]">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn btn-primary h-10 px-5 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
                >
                  {saving && <Loader2 size={13} className="animate-spin" />}
                  <span>{editingSource ? 'Save Changes' : 'Add Source'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
