import { useState, useEffect } from 'react'
import {
  Send, ExternalLink, Clock, Copy, Check, RefreshCw
} from 'lucide-react'
import toast from 'react-hot-toast'
import { publishingApi } from '../services/api'
import { formatPoliTimestamp } from '../utils/dateTime'

function FacebookIcon({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
    </svg>
  )
}

export default function PublishedPostsPage() {
  const [posts, setPosts] = useState([])
  const [metaStatus, setMetaStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [loadError, setLoadError] = useState('')

  const loadData = async () => {
    try {
      setLoadError('')
      setLoading(true)
      const [historyRes, statusRes] = await Promise.all([
        publishingApi.history(50),
        publishingApi.status().catch(() => ({ data: { configured: false, valid: false } })),
      ])
      setPosts(historyRes.data)
      setMetaStatus(statusRes.data)
    } catch (err) {
      setLoadError('Failed to load publication history.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleRefresh = async () => {
    try {
      setRefreshing(true)
      const res = await publishingApi.history(50)
      setPosts(res.data)
      toast.success('Publication history refreshed')
    } catch (err) {
      toast.error('Failed to refresh history')
    } finally {
      setRefreshing(false)
    }
  }

  const handleCopyLink = (post) => {
    if (!post.fb_link) return
    navigator.clipboard.writeText(post.fb_link)
    setCopiedId(post.id)
    toast.success('Facebook link copied!')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const formatTimestamp = (isoString) => {
    return formatPoliTimestamp(isoString)
  }

  return (
    <div className="space-y-8 sm:space-y-10">
      {loadError && <div className="alert alert-error" role="alert"><span className="flex-1">{loadError}</span><button type="button" className="underline font-semibold" onClick={loadData}>Retry</button></div>}
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 sm:pb-8 border-b border-[#E5E5E5]">
        <div className="space-y-1 max-w-2xl">
          <span className="text-xs font-bold tracking-widest uppercase text-[#767676] block mb-1">
            Audit Trail
          </span>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
            Published Archive
          </h1>
          <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mt-1">
            Audit history of political graphics and captions published to Facebook.
          </p>
        </div>

        {/* Right Header Controls: Status indicator & Refresh button */}
        <div className="flex items-center gap-3 flex-wrap md:flex-nowrap shrink-0 self-start md:self-end">
          {metaStatus && (
            <div className={`h-10 px-3.5 rounded-full text-xs font-semibold inline-flex items-center gap-2 border ${
              metaStatus.valid
                ? 'bg-[#DCFCE7] border-[#BBF7D0] text-[#15803D]'
                : 'bg-[#F8F9FA] border-[#E5E5E5] text-[#767676]'
            }`}>
              <FacebookIcon size={13} className={metaStatus.valid ? 'text-[#15803D]' : 'text-[#767676]'} />
              <span>
                {metaStatus.configured
                  ? (metaStatus.valid ? 'Meta API Connected' : 'Token Expired')
                  : 'Manual Publishing Mode'}
              </span>
            </div>
          )}

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-2 shadow-2xs hover:shadow-xs transition-colors"
            title="Refresh publication records"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Refreshing…' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* ── Publication Records or Centered Empty State ── */}
      {loading ? (
        <div className="py-24 text-center text-[#767676] bg-[#F8F9FA] rounded-2xl border border-[#E5E5E5]">
          <div className="spinner spinner-lg mx-auto mb-3" />
          <p className="text-xs font-semibold tracking-wider uppercase">Loading publication history…</p>
        </div>
      ) : posts.length === 0 ? (
        /* ── Centered Intentional Empty State Panel ── */
        <div className="card py-12 sm:py-16 px-6 border border-[#E5E5E5] bg-[#F8F9FA] rounded-2xl flex flex-col items-center justify-center text-center shadow-2xs">
          <div className="w-full max-w-[480px] flex flex-col items-center">
            {/* Centered Send Icon */}
            <div className="w-14 h-14 rounded-2xl bg-white border border-[#E5E5E5] flex items-center justify-center text-[#162238] mb-5 shadow-xs">
              <Send size={24} className="text-[#162238]" />
            </div>

            {/* Heading */}
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] mb-2 tracking-tight">
              No Published Records Yet
            </h2>

            {/* Centered Explanatory Description */}
            <p className="text-xs sm:text-sm text-[#767676] leading-relaxed">
              When you publish posts to Facebook or mark drafts as published, the complete audit record with timestamps, post links, and generated graphics will appear here.
            </p>
          </div>
        </div>
      ) : (
        /* ── Populated Publication Records ── */
        <div className="space-y-4">
          {posts.map(post => (
            <div
              key={post.id}
              className="card p-5 sm:p-6 bg-white border border-[#E5E5E5] rounded-2xl hover:border-[#111111] transition-all duration-200 shadow-2xs group"
            >
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
                {/* Left: Graphic thumbnail and associated article info */}
                <div className="flex items-start gap-4 sm:gap-5 min-w-0 flex-1">
                  <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl bg-[#F8F9FA] border border-[#E5E5E5] shrink-0 overflow-hidden shadow-inner flex items-center justify-center relative">
                    <img
                      src={post.image_url || `/api/drafts/${post.draft_id}/image`}
                      alt="Graphic Thumbnail"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none'
                        e.currentTarget.parentElement.innerHTML = '<div class="w-full h-full flex items-center justify-center text-[10px] font-semibold text-[#767676] bg-[#F8F9FA]">No Image</div>'
                      }}
                    />
                  </div>

                  <div className="space-y-1.5 min-w-0 flex-1">
                    {/* Metadata Badges & Timestamp */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`badge ${post.platform === 'facebook_manual' ? 'badge-neutral' : 'badge-success'} text-[10px] font-bold uppercase tracking-wider`}>
                        {post.platform === 'facebook_manual' ? 'Manually Recorded' : (post.status || 'Published')}
                      </span>
                      {post.category && (
                        <span className="badge badge-neutral text-[10px]">
                          {post.category}
                        </span>
                      )}
                      {post.publisher_name && (
                        <span className="text-xs font-semibold text-[#162238]">
                          {post.publisher_name}
                        </span>
                      )}
                      <span className="text-xs font-medium text-[#767676]">
                        Draft #{post.draft_id}
                      </span>
                      <span className="text-[11px] text-[#999999]">•</span>
                      <span className="text-xs text-[#767676] flex items-center gap-1 font-medium">
                        <Clock size={12} className="text-[#999999]" />
                        {formatTimestamp(post.published_at || post.created_at)}
                      </span>
                    </div>

                    {/* Associated Article Headline */}
                    <h3 className="text-base sm:text-lg font-bold text-[#111111] leading-snug break-words">
                      {post.headline || post.title || `Publication Record #${post.id}`}
                    </h3>

                    {/* Associated Caption / Excerpt Preview */}
                    {post.caption && (
                      <p className="text-xs text-[#767676] line-clamp-2 leading-relaxed break-words">
                        {post.caption}
                      </p>
                    )}

                    {/* Platform Post Identifier / Original link */}
                    {post.platform_post_id && !post.fb_link && (
                      <p className="text-xs font-mono text-[#767676] truncate pt-0.5">
                        Platform ID: {post.platform_post_id}
                      </p>
                    )}
                  </div>
                </div>

                {/* Right: Platform Post Link & Actions */}
                <div className="flex items-center gap-2.5 shrink-0 self-start md:self-center pt-3 md:pt-0 border-t md:border-t-0 border-[#F0F0F0] w-full md:w-auto justify-end">
                  {post.fb_link ? (
                    <>
                      <button
                        onClick={() => handleCopyLink(post)}
                        className="btn btn-secondary btn-sm text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                        title="Copy Facebook Post Link"
                      >
                        {copiedId === post.id ? <Check size={13} className="text-[#15803D]" /> : <Copy size={13} />}
                        <span>{copiedId === post.id ? 'Copied' : 'Copy Link'}</span>
                      </button>

                      <a
                        href={post.fb_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-primary btn-sm text-xs flex items-center gap-1.5 cursor-pointer shadow-xs hover:shadow"
                      >
                        <FacebookIcon size={12} />
                        <span>View on Facebook</span>
                        <ExternalLink size={12} />
                      </a>
                    </>
                  ) : post.platform_post_id ? (
                    <span className="text-xs font-mono text-[#767676] px-3.5 py-1.5 bg-[#F8F9FA] rounded-full border border-[#E5E5E5]">
                      ID: {post.platform_post_id}
                    </span>
                  ) : (
                    <span className="text-xs font-semibold text-[#767676] px-3 py-1.5 bg-[#F8F9FA] rounded-full border border-[#E5E5E5]">
                      Manual Record
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
