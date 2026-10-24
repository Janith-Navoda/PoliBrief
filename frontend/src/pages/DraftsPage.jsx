import { useState, useEffect, useRef } from 'react'
import {
  FileText, CheckCircle, Clock, Download, Copy, Trash2,
  Check, PenSquare, Send, X, AlertCircle, Layers, ExternalLink, Eye
} from 'lucide-react'
import toast from 'react-hot-toast'
import { draftsApi, publishingApi } from '../services/api'
import { formatPoliTimestamp } from '../utils/dateTime'
import { getDraftActionState, releasePublish, tryAcquirePublish } from './draftActions'
import { useLocation } from 'react-router-dom'

const STATUS_TABS = [
  { id: 'ALL', label: 'All Drafts' },
  { id: 'DRAFT', label: 'In Review' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'PUBLISHED', label: 'Published' },
]

export default function DraftsPage({ onNavigate }) {
  const location = useLocation()
  const focusedDraftId = Number(new URLSearchParams(location.search).get('draft_id')) || null
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [activeTab, setActiveTab] = useState('ALL')
  const [copiedId, setCopiedId] = useState(null)

  // Mark Published modal
  const [publishModalDraft, setPublishModalDraft] = useState(null)
  const [platformPostId, setPlatformPostId] = useState('')
  const [marking, setMarking] = useState(false)
  const [apiPublishDraft, setApiPublishDraft] = useState(null)
  const [publishingDraftId, setPublishingDraftId] = useState(null)
  const [uncertainDraftIds, setUncertainDraftIds] = useState([])
  const publishInFlight = useRef(new Set())
  const [metaStatus, setMetaStatus] = useState({ loading: true, configured: false, valid: false, message: '' })
  const [publicationRecords, setPublicationRecords] = useState([])

  const getApiError = (err, fallback) => err.response?.data?.detail || fallback

  const fetchDrafts = async () => {
    try {
      setLoadError('')
      setLoading(true)
      const res = await draftsApi.list({ status: activeTab })
      setDrafts(res.data)
      return res.data
    } catch (err) {
      setLoadError('Failed to load drafts.')
      return null
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDrafts()
  }, [activeTab])

  useEffect(() => {
    if (focusedDraftId && activeTab !== 'ALL') setActiveTab('ALL')
  }, [focusedDraftId, activeTab])

  useEffect(() => {
    if (!focusedDraftId || loading || !drafts.some(draft => draft.id === focusedDraftId)) return
    document.getElementById(`draft-card-${focusedDraftId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focusedDraftId, loading, drafts])

  const fetchPublicationHistory = async () => {
    try {
      const res = await publishingApi.history(200)
      setPublicationRecords(res.data)
    } catch {
      // Draft management remains available if history cannot be loaded.
    }
  }

  useEffect(() => {
    let active = true
    publishingApi.status()
      .then(res => { if (active) setMetaStatus({ loading: false, ...res.data }) })
      .catch(() => {
        if (active) setMetaStatus({
          loading: false,
          configured: false,
          valid: false,
          message: 'Could not validate the Facebook Page connection. API publishing is disabled.',
        })
      })
    fetchPublicationHistory()
    return () => { active = false }
  }, [])

  // Approve Draft
  const handleApprove = async (draft) => {
    try {
      await draftsApi.approve(draft.id)
      toast.success(`Draft #${draft.id} approved for publishing!`)
      await fetchDrafts()
    } catch (err) {
      toast.error(getApiError(err, 'Failed to approve draft'))
    }
  }

  // Delete Draft
  const handleDelete = async (draft) => {
    if (!window.confirm(`Delete draft #${draft.id}? Its generated graphic will be removed after the draft is safely deleted.`)) {
      return
    }
    try {
      await draftsApi.delete(draft.id)
      setDrafts(drafts.filter(d => d.id !== draft.id))
      toast.success('Draft removed')
    } catch (err) {
      toast.error(getApiError(err, 'Failed to delete draft'))
    }
  }

  // Copy Caption
  const handleCopyCaption = (draft) => {
    if (!draft.caption) return
    navigator.clipboard.writeText(draft.caption)
    setCopiedId(draft.id)
    toast.success('Caption copied to clipboard!')
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Download Image
  const handleDownload = (draft) => {
    const link = document.createElement('a')
    link.href = `/api/drafts/${draft.id}/image?download=true`
    link.download = `polibrief_post_${draft.id}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast.success('Downloading post graphic…')
  }

  // Mark Published Submit
  const handleConfirmPublish = async (e) => {
    e.preventDefault()
    if (!publishModalDraft) return

    try {
      setMarking(true)
      await draftsApi.markPublished(publishModalDraft.id, platformPostId.trim() || undefined)
      toast.success('Manual publication confirmation recorded. No Facebook API post was made.')
      setPublishModalDraft(null)
      setPlatformPostId('')
      await Promise.all([fetchDrafts(), fetchPublicationHistory()])
    } catch (err) {
      toast.error(getApiError(err, 'Failed to record manual publication'))
    } finally {
      setMarking(false)
    }
  }

  const canPublishThroughApi = !metaStatus.loading && metaStatus.configured && metaStatus.valid

  const handleConfirmApiPublish = async (e) => {
    e.preventDefault()
    const draft = apiPublishDraft
    if (!draft || !getDraftActionState(draft, metaStatus).publishViaApi) return
    if (!tryAcquirePublish(publishInFlight.current, draft.id)) return

    setPublishingDraftId(draft.id)
    try {
      const res = await publishingApi.publish(draft.id)
      if (res.data.status === 'PUBLISHING') {
        setUncertainDraftIds(ids => ids.includes(draft.id) ? ids : [...ids, draft.id])
        setActiveTab('ALL')
        toast.error(res.data.detail || 'The outcome is uncertain. Check the Page and reconcile before retrying.')
      } else {
        toast.success(res.data.message || 'Successfully published to Facebook.')
      }
      setApiPublishDraft(null)
      await Promise.all([fetchDrafts(), fetchPublicationHistory()])
    } catch (err) {
      const detail = err.response?.data?.detail || ''
      const uncertain = !err.response || ['ECONNABORTED', 'ETIMEDOUT'].includes(err.code) ||
        (err.response.status >= 500 && !detail.toLowerCase().includes('meta rejected'))
      if (uncertain) {
        setUncertainDraftIds(ids => ids.includes(draft.id) ? ids : [...ids, draft.id])
        setActiveTab('ALL')
        toast.error('The publish outcome could not be confirmed. Do not retry until you check the Page and reconcile this draft.')
      } else {
        toast.error(getApiError(err, 'Facebook publishing failed.'))
      }
      setApiPublishDraft(null)
      await Promise.all([fetchDrafts(), fetchPublicationHistory()])
    } finally {
      releasePublish(publishInFlight.current, draft.id)
      setPublishingDraftId(null)
    }
  }

  const formatTimestamp = (isoString) => {
    return formatPoliTimestamp(isoString)
  }

  return (
    <div className="space-y-8 sm:space-y-10">
      {loadError && <div className="alert alert-error" role="alert"><span className="flex-1">{loadError}</span><button type="button" className="underline font-semibold" onClick={fetchDrafts}>Retry</button></div>}
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#E5E5E5]">
        <div className="space-y-1 max-w-2xl">
          <span className="text-xs font-bold tracking-widest uppercase text-[#767676] block">
            Editorial Workflow
          </span>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
            Editorial Drafts
          </h1>
          <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mt-1">
            Review generated social graphics, approve posts, and track publishing audit records.
          </p>
        </div>

        {/* Action Button: Aligned to right on desktop, stacks below heading on mobile */}
        {onNavigate && (
          <div className="shrink-0 w-full sm:w-auto self-start md:self-end">
            <button
              onClick={() => onNavigate('studio')}
              className="btn btn-primary text-xs w-full sm:w-auto h-10 px-5 flex items-center justify-center gap-2 cursor-pointer shadow-xs hover:shadow"
            >
              <PenSquare size={14} />
              <span>New Post</span>
            </button>
          </div>
        )}
      </div>

      {/* ── Draft Status Filters Strip ── */}
      <div className="flex items-center gap-2.5 overflow-x-auto pb-2 scrollbar-none pt-1">
        {STATUS_TABS.map(tab => {
          const isSelected = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`h-9 px-4 rounded-full text-xs font-bold whitespace-nowrap transition-all duration-150 cursor-pointer border shrink-0 flex items-center justify-center ${
                isSelected
                  ? 'bg-[#111111] text-white border-[#111111] shadow-2xs'
                  : 'bg-white text-[#666666] border-[#E5E5E5] hover:border-[#111111] hover:text-[#111111] hover:bg-[#F8F9FA]'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* ── Drafts List or Empty State ── */}
      {loading ? (
        <div className="py-24 text-center text-[#767676] bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
          <div className="spinner spinner-lg mx-auto mb-3" />
          <p className="text-xs font-semibold tracking-wider uppercase">Loading drafts…</p>
        </div>
      ) : drafts.length === 0 ? (
        /* ── Centered Professional Empty State Panel ── */
        <div className="card py-12 sm:py-16 px-6 border border-[#E5E5E5] bg-[#F8F9FA] rounded-3xl flex flex-col items-center justify-center text-center shadow-2xs">
          <div className="w-full max-w-[480px] flex flex-col items-center">
            {/* Centered Document Icon */}
            <div className="w-14 h-14 rounded-2xl bg-white border border-[#E5E5E5] flex items-center justify-center text-[#162238] mb-4 shadow-xs">
              <FileText size={24} className="text-[#162238]" />
            </div>

            {/* Heading */}
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] mb-2 tracking-tight">
              No Drafts in This View
            </h2>

            {/* Short Explanatory Description */}
            <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mb-6">
              There are currently no drafts matching the <strong className="text-[#111111]">"{activeTab}"</strong> filter status. Generate your first editorial graphic and Facebook caption in the Post Studio.
            </p>

            {/* Create First Post Action Button */}
            {onNavigate && (
              <button
                onClick={() => onNavigate('studio')}
                className="btn btn-primary h-11 px-6 text-xs sm:text-sm font-bold flex items-center gap-2 cursor-pointer shadow-xs hover:shadow"
              >
                <PenSquare size={14} />
                <span>Create First Post</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        /* ── Populated Draft State ── */
        <div className="space-y-5">
          {drafts.map(draft => {
            const publication = publicationRecords.find(record => record.draft_id === draft.id)
            const uncertain = draft.status === 'PUBLISHING' || uncertainDraftIds.includes(draft.id)
            const actions = getDraftActionState(draft, metaStatus, publication)
            return (<div
              key={draft.id}
              id={`draft-card-${draft.id}`}
              className={`card p-6 sm:p-7 bg-white border rounded-2xl hover:border-[#111111] transition-all duration-200 shadow-2xs group ${focusedDraftId === draft.id ? 'border-[#111111] ring-2 ring-[#111111]/20' : 'border-[#E5E5E5]'}`}
            >
              <div className="flex flex-col md:flex-row items-start gap-6">
                {/* Left: Graphic Thumbnail (1:1 Ratio, fixed responsive width) */}
                <div className="w-full sm:w-44 md:w-48 shrink-0">
                  <div className="relative aspect-square w-full rounded-xl overflow-hidden bg-[#F8F9FA] border border-[#E5E5E5] shadow-inner group/thumb">
                    <img
                      src={`/api/drafts/${draft.id}/image`}
                      alt="Post Graphic"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none'
                        e.currentTarget.parentElement.innerHTML = '<div class="flex items-center justify-center w-full h-full text-xs text-[#767676]">Image Unavailable</div>'
                      }}
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <button
                        onClick={() => handleDownload(draft)}
                        className="p-2.5 rounded-full bg-white text-[#111111] hover:bg-[#F8F9FA] transition-colors cursor-pointer shadow-sm"
                        title="Download 1080×1080 Image"
                      >
                        <Download size={16} />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Right: Content, Metadata, Caption & Action Footer */}
                <div className="flex-1 flex flex-col justify-between w-full space-y-4">
                  {/* Top Metadata Strip */}
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className={`badge text-[10px] ${
                        draft.status === 'APPROVED'
                          ? 'badge-success'
                          : draft.status === 'PUBLISHED'
                          ? 'badge-info'
                          : 'badge-warning'
                      }`}>
                        {draft.status}
                      </span>
                      <span className="text-xs text-[#767676] flex items-center gap-1">
                        <Layers size={13} className="text-[#999999]" />
                        Template: <strong className="text-[#111111]">{draft.template_id}</strong>
                      </span>
                    </div>

                    <span className="text-xs text-[#767676] flex items-center gap-1.5 font-medium">
                      <Clock size={13} className="text-[#999999]" />
                      {formatTimestamp(draft.created_at)}
                    </span>
                  </div>

                  {/* Headline */}
                  <h3 className="text-base sm:text-lg font-bold text-[#111111] leading-snug">
                    {draft.headline_override || draft.article_headline}
                  </h3>

                  {/* Caption preview snippet */}
                  {draft.caption && (
                    <div className="p-3.5 rounded-xl bg-[#F8F9FA] border border-[#E5E5E5] text-xs font-mono text-[#111111] leading-relaxed max-h-24 overflow-y-auto">
                      {draft.caption}
                    </div>
                  )}

                  {/* Separated Action Footer */}
                  <div className="pt-4 border-t border-[#E5E5E5] flex items-center justify-between flex-wrap gap-3 mt-auto">
                    {/* Left Actions: Copy Caption & Download */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleCopyCaption(draft)}
                        className="btn btn-secondary btn-sm text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                        title="Copy caption to clipboard"
                      >
                        {copiedId === draft.id ? <Check size={13} className="text-[#15803D]" /> : <Copy size={13} />}
                        <span>{copiedId === draft.id ? 'Copied' : 'Copy Caption'}</span>
                      </button>

                      <button
                        onClick={() => handleDownload(draft)}
                        className="btn btn-secondary btn-sm text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                        title="Download 1080×1080 image"
                      >
                        <Download size={13} />
                        <span>Download</span>
                      </button>
                    </div>

                    {/* API publishing and manual confirmation are separate actions. */}
                    <div className="flex items-center gap-2 flex-wrap justify-end">
                      {draft.status === 'DRAFT' && (
                        <button
                          onClick={() => handleApprove(draft)}
                          className="btn btn-primary btn-sm text-xs flex items-center gap-1.5 cursor-pointer shadow-xs hover:shadow"
                          title="Approve for Facebook publication"
                        >
                          <CheckCircle size={13} />
                          <span>Approve</span>
                        </button>
                      )}

                      {actions.approved && (
                        <>
                          <button
                            type="button"
                            onClick={() => setApiPublishDraft(draft)}
                            disabled={!actions.publishViaApi || uncertain || publishingDraftId === draft.id}
                            className="btn btn-primary btn-sm text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            title={canPublishThroughApi ? `Publish to ${metaStatus.page_name || 'Facebook Page'}` : metaStatus.message || 'Valid Facebook Page connection required'}
                          >
                            <Send size={13} />
                            <span>{metaStatus.loading ? 'Checking Page…' : publishingDraftId === draft.id ? 'Publishing…' : 'Publish to Facebook'}</span>
                          </button>
                          <button
                            onClick={() => setPublishModalDraft(draft)}
                            className="btn btn-secondary btn-sm text-xs flex items-center gap-1.5 cursor-pointer"
                            title="Record your confirmation of a post published outside PoliBrief"
                          >
                            <CheckCircle size={13} />
                            <span>Mark Published Manually</span>
                          </button>
                        </>
                      )}

                      {actions.approved && !actions.apiAvailable && (
                        <span className="text-[11px] text-[#767676]" role="status">
                          {metaStatus.loading ? 'Validating Page connection…' : metaStatus.message || 'Valid Facebook Page connection required; API publishing is disabled.'}
                        </span>
                      )}

                      {actions.viewPublication && (
                        <>
                          <span className="text-[11px] text-[#767676]" role="note">
                            Retained publication history keeps this draft protected from deletion.
                          </span>
                          <button
                            type="button"
                            onClick={() => onNavigate?.('published')}
                            className="btn btn-secondary btn-sm text-xs flex items-center gap-1.5 cursor-pointer"
                          >
                            <Eye size={13} />
                            <span>View Publication Record</span>
                          </button>
                          {actions.openFacebookPost && (
                            <a
                              href={publication.fb_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn btn-secondary btn-sm text-xs flex items-center gap-1.5"
                            >
                              <ExternalLink size={13} />
                              <span>Open Facebook Post</span>
                            </a>
                          )}
                        </>
                      )}

                      {uncertain && (
                        <span className="text-xs text-[#92400E]" role="status">Outcome unresolved; verify the Page and reconcile before retrying.</span>
                      )}

                      {actions.delete && (
                        <button
                          onClick={() => handleDelete(draft)}
                          className="btn btn-secondary btn-sm text-xs flex items-center gap-1.5 text-[#B91C1C] hover:bg-[#FEE2E2] cursor-pointer"
                          title="Delete draft and remove its image after the database confirms deletion"
                        >
                          <Trash2 size={15} />
                          <span>Delete</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>)
          })}
        </div>
      )}

      {/* ── Mark Published Modal ── */}
      {publishModalDraft && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="manual-publish-dialog-title" className="bg-white rounded-2xl border border-[#E5E5E5] p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E5]">
              <h3 id="manual-publish-dialog-title" className="text-base font-bold text-[#111111]">
                Mark Draft #{publishModalDraft.id} as Published
              </h3>
              <button
                type="button"
                onClick={() => setPublishModalDraft(null)}
                className="p-1 rounded-full text-[#767676] hover:text-[#111111] cursor-pointer"
                aria-label="Close mark published dialog"
              >
                <X size={18} />
              </button>
            </div>

            <p className="text-xs text-[#767676] leading-relaxed">
              Record your explicit confirmation that this was posted manually to Facebook. This does not publish through the API. Optionally provide the Facebook post ID or link for the audit record.
            </p>

            <form onSubmit={handleConfirmPublish} className="space-y-4">
              <div>
                <label className="form-label" htmlFor="platform-id">
                  Facebook Post ID / URL (Optional)
                </label>
                <input
                  id="platform-id"
                  type="text"
                  placeholder="e.g. 123456789_987654321"
                  className="form-input text-xs"
                  value={platformPostId}
                  onChange={e => setPlatformPostId(e.target.value)}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setPublishModalDraft(null)}
                  className="btn btn-secondary btn-sm cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={marking}
                  className="btn btn-primary btn-sm cursor-pointer"
                >
                  {marking ? 'Saving…' : 'Confirm Published'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {apiPublishDraft && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="api-publish-dialog-title" className="bg-white rounded-2xl border border-[#E5E5E5] p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E5]">
              <h3 id="api-publish-dialog-title" className="text-base font-bold text-[#111111]">Publish to Facebook?</h3>
              <button
                type="button"
                onClick={() => setApiPublishDraft(null)}
                className="p-1 rounded-full text-[#767676] hover:text-[#111111] cursor-pointer"
                aria-label="Close Facebook publishing confirmation"
              >
                <X size={18} />
              </button>
            </div>
            <p className="text-sm text-[#333333]">
              This will publish the approved caption and generated image to <strong>{metaStatus.page_name || `Page ${metaStatus.page_id}`}</strong>.
            </p>
            <p className="text-xs text-[#767676]">If Meta’s response is uncertain, PoliBrief will keep the draft locked until its outcome is reconciled. It will not automatically retry.</p>
            <form onSubmit={handleConfirmApiPublish} className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setApiPublishDraft(null)}
                disabled={publishingDraftId === apiPublishDraft.id}
                className="btn btn-secondary btn-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={publishingDraftId === apiPublishDraft.id || !canPublishThroughApi}
                className="btn btn-primary btn-sm disabled:opacity-50"
              >
                {publishingDraftId === apiPublishDraft.id ? 'Publishing…' : 'Confirm and Publish'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
