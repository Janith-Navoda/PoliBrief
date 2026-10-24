import { useState, useEffect, useRef } from 'react'
import {
  PenSquare, Image as ImageIcon, Copy, Download, Check, Save,
  ExternalLink, ArrowRight, Layers, CheckCircle2, ChevronDown, Clock
} from 'lucide-react'
import toast from 'react-hot-toast'
import { articlesApi, draftsApi, sourcesApi } from '../services/api'
import PageHeader from '../components/PageHeader'
import { getSourcePolicyDisplay } from '../utils/sourcePolicy'

const TEMPLATES = [
  {
    id: 'modern',
    name: 'Modern General',
    desc: 'Deep navy background with gold framing & category chip',
    badge: 'Navy & Gold',
  },
  {
    id: 'breaking',
    name: 'Breaking News',
    desc: 'High-contrast red banner with urgent alert badge',
    badge: 'Urgent Red',
  },
  {
    id: 'minimal',
    name: 'Minimal Editorial',
    desc: 'Refined editorial serif dispatch with quotation styling',
    badge: 'Classic Serif',
  },
  {
    id: 'universal_custom',
    name: 'Universal Custom Template',
    desc: 'Use your saved square background for future news graphics',
    badge: 'Custom Background',
  },
]

function describeSourcePolicy(raw) {
  const { labels, notes, needsReview } = getSourcePolicyDisplay(raw)
  return [...labels, ...notes, ...(needsReview ? ['Policy details need review; verify before use.'] : [])].join('. ')
}

export default function PostStudioPage({ article: navArticle, onNavigate }) {
  const [articles, setArticles] = useState([])
  const [selectedArticle, setSelectedArticle] = useState(navArticle || null)
  const [articlesLoading, setArticlesLoading] = useState(true)
  const [articlesError, setArticlesError] = useState('')
  const [templateId, setTemplateId] = useState('modern')
  const [headlineColor, setHeadlineColor] = useState('#FFFFFF')
  const [hashtagColor, setHashtagColor] = useState('#FFFFFF')
  const [universalTemplate, setUniversalTemplate] = useState({ loading: true, exists: false, image_url: null, error: '' })
  const [templateBusy, setTemplateBusy] = useState(false)
  const templateFileRef = useRef(null)
  const [headlineOverride, setHeadlineOverride] = useState('')
  const [caption, setCaption] = useState('')

  const [previewUrl, setPreviewUrl] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [copiedCaption, setCopiedCaption] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const captionEditedRef = useRef(false)
  const [previewAttempt, setPreviewAttempt] = useState(0)
  const [relatedStories, setRelatedStories] = useState([])
  const [sourcePolicy, setSourcePolicy] = useState('')
  const [sourcePolicyError, setSourcePolicyError] = useState('')

  const loadArticles = async () => {
    setArticlesError('')
    setArticlesLoading(true)
    try {
      const res = await articlesApi.list({ page_size: 30 })
      setArticles(res.data.items)
      setSelectedArticle(current => current || navArticle || res.data.items[0] || null)
    } catch {
      setArticlesError('Articles could not be loaded. Check the connection and retry.')
    } finally {
      setArticlesLoading(false)
    }
  }

  useEffect(() => { loadArticles() }, [])
  useEffect(() => { if (navArticle) setSelectedArticle(navArticle) }, [navArticle?.id])

  const loadUniversalTemplate = async () => {
    try {
      const res = await draftsApi.universalTemplate()
      setUniversalTemplate({ loading: false, ...res.data, error: '' })
    } catch (err) {
      setUniversalTemplate({ loading: false, exists: false, image_url: null, error: err.response?.data?.detail || 'Custom background status could not be loaded.' })
    }
  }

  useEffect(() => { loadUniversalTemplate() }, [])

  const handleBackgroundUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (universalTemplate.exists && !window.confirm('Replace the saved background? Existing drafts and published graphics will remain unchanged.')) {
      event.target.value = ''
      return
    }
    try {
      setTemplateBusy(true)
      const res = await draftsApi.uploadUniversalTemplate(file)
      setUniversalTemplate({ loading: false, ...res.data.template, error: '' })
      toast.success('Universal custom background saved for future graphics.')
      setPreviewAttempt(value => value + 1)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Background upload failed. Use a square PNG or JPG under 10 MB.')
    } finally {
      setTemplateBusy(false)
      event.target.value = ''
    }
  }

  const handleRemoveBackground = async () => {
    if (!universalTemplate.exists) return
    if (!window.confirm('Remove the active custom background? Existing generated and published graphics will remain unchanged.')) return
    try {
      setTemplateBusy(true)
      await draftsApi.removeUniversalTemplate()
      setUniversalTemplate({ loading: false, exists: false, image_url: null, error: '' })
      if (templateId === 'universal_custom') setTemplateId('modern')
      setPreviewAttempt(value => value + 1)
      toast.success('Custom background removed. Built-in templates remain available.')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not remove the custom background.')
    } finally {
      setTemplateBusy(false)
    }
  }

  useEffect(() => {
    let active = true
    setSourcePolicy('')
    setSourcePolicyError('')
    sourcesApi.list()
      .then(res => {
        if (!active) return
        const source = res.data.find(item => item.id === selectedArticle?.source_id)
        setSourcePolicy(describeSourcePolicy(source?.content_restrictions))
        setSourcePolicyError('')
      })
      .catch(() => { if (active) setSourcePolicyError('Publisher usage notes are unavailable. The server still enforces required attribution.') })
    return () => { active = false }
  }, [selectedArticle?.source_id])

  // Sync state when selectedArticle changes
  useEffect(() => {
    if (!selectedArticle) return
    setHeadlineOverride(selectedArticle.headline)
    setCaption('')
    captionEditedRef.current = false
    setPreviewUrl('')
  }, [selectedArticle])

  useEffect(() => {
    if (!selectedArticle) { setRelatedStories([]); return }
    let active = true
    articlesApi.related(selectedArticle.id)
      .then(res => { if (active) setRelatedStories(res.data || []) })
      .catch(() => { if (active) setRelatedStories([]) })
    return () => { active = false }
  }, [selectedArticle?.id])

  // Generate live preview on changes (debounced)
  useEffect(() => {
    if (!selectedArticle) return

    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        setPreviewLoading(true)
        setPreviewError('')
        const res = await draftsApi.preview({
          article_id: selectedArticle.id,
          headline_override: headlineOverride.trim() || selectedArticle.headline,
          template_id: templateId,
          headline_color: headlineColor,
          hashtag_color: hashtagColor,
        })
        if (cancelled) return
        setPreviewUrl(res.data.image_url)
        // If caption is empty or unmodified, update with generated caption
        if (!captionEditedRef.current) {
          setCaption(res.data.caption)
        }
      } catch {
        if (!cancelled) setPreviewError('Preview could not be generated. Retry after checking the selected article.')
      } finally {
        if (!cancelled) setPreviewLoading(false)
      }
    }, 400)

    return () => { cancelled = true; clearTimeout(timer) }
  }, [selectedArticle, templateId, headlineOverride, headlineColor, hashtagColor, previewAttempt])

  // Save as Draft
  const handleSaveDraft = async (andApprove = false) => {
    if (!selectedArticle) {
      toast.error('Please select an article first')
      return
    }

    try {
      setSaving(true)
      const res = await draftsApi.create({
        article_id: selectedArticle.id,
        headline_override: headlineOverride.trim() !== selectedArticle.headline ? headlineOverride.trim() : null,
        caption: caption.trim(),
        template_id: templateId,
        headline_color: headlineColor,
        hashtag_color: hashtagColor,
      })

      const draftId = res.data.id
      if (andApprove) {
        await draftsApi.approve(draftId)
        toast.success('Post draft saved & approved!')
      } else {
        toast.success('Post draft saved to review queue!')
      }

      if (onNavigate) {
        onNavigate('drafts')
      }
    } catch (err) {
      toast.error('Failed to save post draft')
    } finally {
      setSaving(false)
    }
  }

  // Copy caption to clipboard
  const handleCopyCaption = async () => {
    if (!caption) return
    try {
      await navigator.clipboard.writeText(caption)
      setCopiedCaption(true)
      toast.success('Caption copied to clipboard!')
      setTimeout(() => setCopiedCaption(false), 2000)
    } catch {
      toast.error('Clipboard access failed. Select and copy the caption manually.')
    }
  }

  // Download preview image
  const handleDownloadPreview = () => {
    if (!previewUrl) return
    const link = document.createElement('a')
    link.href = previewUrl
    link.download = `polibrief_${templateId}_${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast.success('1080×1080 visual graphic downloaded!')
  }

  return (
    <div className="space-y-8 sm:space-y-10">
      {/* ── Standardized Page Header ── */}
      <PageHeader
        eyebrow="Content Creator"
        title="Post Studio"
        subtitle="Compose 1080×1080 editorial graphics with source-linked headlines and Facebook captions."
        actions={
          onNavigate && (
            <button
              onClick={() => onNavigate('drafts')}
              className="btn btn-secondary text-xs flex items-center gap-1.5 cursor-pointer shadow-2xs hover:shadow-xs"
            >
              <span>Review Queue</span>
              <ArrowRight size={14} />
            </button>
          )
        }
      />

      {/* ── Professional Two-Column Layout (Desktop: 42% Preview, 58% Editor, Gap: 32px) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 xl:gap-8 items-start min-w-0">
        {/* ── Left Column: Graphic Preview Panel (approx 42%) ── */}
        <div className="space-y-6 min-w-0">
          <div className="card p-6 sm:p-7 bg-white border border-[#E5E5E5] rounded-2xl space-y-6 shadow-2xs">
            {/* Section Header */}
            <div className="flex items-center justify-between pb-3.5 border-b border-[#E5E5E5]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#111111] shrink-0">
                  <ImageIcon size={16} />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-[#111111]">
                    Graphic Preview
                  </h2>
                  <p className="text-[11px] text-[#767676]">1080×1080px square post asset</p>
                </div>
              </div>

              {previewLoading && (
                <span className="text-xs font-semibold text-[#767676] flex items-center gap-1.5">
                  <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                  Rendering…
                </span>
              )}
            </div>

            {/* 1:1 Image Aspect Ratio Canvas */}
            <div className="relative aspect-square w-full rounded-xl overflow-hidden bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center shadow-inner">
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt="Post Graphic Preview"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="text-center p-6 text-[#767676]">
                  <ImageIcon size={44} className="mx-auto mb-2.5 text-[#C5C5C5]" />
                  <p className="text-xs font-semibold">Select an article to generate preview</p>
                </div>
              )}

              {previewLoading && (
                <div className="absolute inset-0 bg-white/70 backdrop-blur-xs flex items-center justify-center">
                  <div className="spinner spinner-lg" />
                </div>
              )}
            </div>

            {previewError && <div className="alert alert-error" role="alert"><span className="flex-1">{previewError}</span><button type="button" className="underline font-semibold" onClick={() => setPreviewAttempt(value => value + 1)}>Retry</button></div>}

            {/* Quick Graphic Download Action */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-[#767676]">
                Square 1:1 format • High-resolution PNG
              </span>
              <button
                type="button"
                onClick={handleDownloadPreview}
                disabled={!previewUrl || previewLoading}
                className="btn btn-secondary btn-sm text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-40"
              >
                <Download size={13} />
                <span>Download Graphic</span>
              </button>
            </div>

            {/* Template Selection Section */}
            <div className="pt-6 border-t border-[#E5E5E5] space-y-3.5">
              <div className="flex items-center gap-2">
                <Layers size={15} className="text-[#111111]" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#111111]">
                  Visual Template Style
                </h3>
              </div>

              <div className="rounded-xl border border-[#E5E5E5] bg-[#F8F9FA] p-3.5 sm:p-4 space-y-3">
                <input
                  ref={templateFileRef}
                  type="file"
                  accept="image/png,image/jpeg,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={handleBackgroundUpload}
                />
                <div className="flex items-center gap-3 min-w-0">
                  {universalTemplate.exists && universalTemplate.image_url ? (
                    <img
                      src={universalTemplate.image_url}
                      alt="Current Universal Custom Template background"
                      className="w-16 h-16 rounded-lg object-cover border border-[#E5E5E5] bg-white shrink-0"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-lg border border-dashed border-[#CFCFCF] bg-white flex items-center justify-center text-[#999999] shrink-0">
                      <ImageIcon size={22} />
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-[#111111]">Universal Custom Background</p>
                    {universalTemplate.loading ? (
                      <p className="text-[11px] text-[#767676]" role="status">Checking saved background…</p>
                    ) : universalTemplate.exists ? (
                      <p className="text-[11px] text-[#555555]">Saved square image • reused for future graphics</p>
                    ) : (
                      <p className="text-[11px] text-[#767676]">No custom background uploaded. Upload a background to enable the Universal Custom Template.</p>
                    )}
                    {universalTemplate.error && <p className="text-[11px] text-[#B91C1C] mt-1" role="alert">{universalTemplate.error}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => templateFileRef.current?.click()}
                    disabled={templateBusy || universalTemplate.loading}
                    className="btn btn-secondary btn-sm text-xs font-semibold disabled:opacity-50"
                  >
                    {templateBusy ? 'Saving…' : universalTemplate.exists ? 'Replace Background' : 'Upload Background'}
                  </button>
                  {universalTemplate.exists && (
                    <button
                      type="button"
                      onClick={handleRemoveBackground}
                      disabled={templateBusy}
                      className="btn btn-secondary btn-sm text-xs text-[#B91C1C] hover:bg-[#FEE2E2] disabled:opacity-50"
                    >
                      Remove Background / Reset
                    </button>
                  )}
                  <span className="text-[10px] text-[#767676]">Square PNG or JPG, up to 10 MB.</span>
                </div>
              </div>

              <div className="space-y-2.5">
                {TEMPLATES.map(tpl => {
                  const isSelected = templateId === tpl.id
                  const isUnavailableCustom = tpl.id === 'universal_custom' && (!universalTemplate.exists || universalTemplate.loading)
                  return (
                    <button
                      type="button"
                      key={tpl.id}
                      onClick={() => setTemplateId(tpl.id)}
                      disabled={isUnavailableCustom}
                      aria-pressed={isSelected}
                      className={`w-full text-left p-4 rounded-xl border transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#111111] ${isUnavailableCustom ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${
                        isSelected
                          ? 'border-[#111111] bg-[#F8F9FA] shadow-xs'
                          : 'border-[#E5E5E5] hover:border-[#111111] bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-[#111111]">{tpl.name}</span>
                        <span className="badge badge-neutral text-[10px]">{tpl.badge}</span>
                      </div>
                      <p className="text-[11px] text-[#555555] leading-relaxed">
                        {tpl.desc}
                      </p>
                    </button>
                  )
                })}
              </div>

              {templateId === 'universal_custom' && (
                <div className="rounded-xl border border-[#E5E5E5] bg-white px-3.5 py-3 space-y-3" aria-label="Custom template text colors">
                  <div className="flex items-center gap-3 flex-wrap">
                    <label htmlFor="custom-headline-color" className="text-xs font-semibold text-[#111111] min-w-36">
                      Headline text color
                    </label>
                    <input
                      id="custom-headline-color"
                      type="color"
                      value={headlineColor}
                      onChange={event => setHeadlineColor(event.target.value.toUpperCase())}
                      className="h-9 w-12 cursor-pointer rounded border border-[#E5E5E5] bg-white p-1"
                    />
                    <span className="text-xs font-mono text-[#767676]">{headlineColor}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <label htmlFor="custom-hashtag-color" className="text-xs font-semibold text-[#111111] min-w-36">
                      #PoliBrief color
                    </label>
                    <input
                      id="custom-hashtag-color"
                      type="color"
                      value={hashtagColor}
                      onChange={event => setHashtagColor(event.target.value.toUpperCase())}
                      className="h-9 w-12 cursor-pointer rounded border border-[#E5E5E5] bg-white p-1"
                      aria-describedby="custom-hashtag-color-help"
                    />
                    <span className="text-xs font-mono text-[#767676]">{hashtagColor}</span>
                    <span id="custom-hashtag-color-help" className="text-[11px] text-[#767676]">Preview updates automatically.</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Right Column: Content Editor Panel (approx 58%) ── */}
        <div className="space-y-6 min-w-0">
          <div className="card p-6 sm:p-8 bg-white border border-[#E5E5E5] rounded-2xl space-y-6 shadow-2xs">
            {/* Section Header */}
            <div className="flex items-center justify-between pb-3.5 border-b border-[#E5E5E5]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#111111] shrink-0">
                  <PenSquare size={16} />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-[#111111]">
                    Content Editor
                  </h2>
                  <p className="text-[11px] text-[#767676]">Configure source, headline &amp; caption</p>
                </div>
              </div>
            </div>

            {/* Form Group 1: Source Article Selector & Information */}
            <div className="space-y-2.5">
              <label
                htmlFor="source-article-select"
                className="block text-xs font-bold tracking-wide uppercase text-[#111111]"
              >
                Source Article
              </label>

              <div className="relative flex items-center">
                <select
                  id="source-article-select"
                  className="w-full h-11 sm:h-12 pl-4 pr-10 text-xs sm:text-sm bg-white border border-[#E5E5E5] rounded-xl focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none text-[#111111] cursor-pointer appearance-none transition-all"
                  value={selectedArticle?.id || ''}
                  onChange={(e) => {
                    const chosen = [...articles, ...(navArticle ? [navArticle] : [])].find(a => a.id === Number(e.target.value))
                    if (chosen) setSelectedArticle(chosen)
                  }}
                >
                  {[...articles, ...(navArticle && !articles.some(a => a.id === navArticle.id) ? [navArticle] : [])].map(a => (
                    <option key={a.id} value={a.id}>
                      [{a.publisher_name}] {a.headline}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#767676] pointer-events-none" />
              </div>
              {articlesLoading && <p className="text-xs text-[#767676]" role="status">Loading articles…</p>}
              {articlesError && <div className="alert alert-error" role="alert"><span className="flex-1">{articlesError}</span><button type="button" className="underline font-semibold" onClick={loadArticles}>Retry</button></div>}

              {selectedArticle && (
                <div className="p-3.5 rounded-xl bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-between flex-wrap gap-2 text-xs text-[#767676]">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span>Publisher: <strong className="text-[#111111] font-semibold">{selectedArticle.publisher_name}</strong></span>
                    <span>•</span>
                    <span>Category: <strong className="text-[#111111] font-semibold">{selectedArticle.category}</strong></span>
                  </div>

                  <a
                    href={selectedArticle.original_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#111111] font-semibold hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>Read Source</span>
                    <ExternalLink size={12} />
                  </a>
                </div>
              )}
              {relatedStories.length > 0 && (
                <section className="rounded-xl border border-[#E5E5E5] p-3.5" aria-label="Related coverage from other publishers">
                  <h3 className="text-[11px] font-bold uppercase tracking-wide text-[#767676] mb-2">Related coverage from other publishers</h3>
                  <ul className="space-y-2">
                    {relatedStories.slice(0, 3).map(story => (
                      <li key={story.article_id} className="text-xs text-[#111111]">
                        <span className="font-semibold">{story.publisher_name}: </span>{story.headline}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {sourcePolicyError && <p className="alert alert-warning" role="status">{sourcePolicyError}</p>}
              {sourcePolicy && (
                <aside className="alert alert-warning flex-col text-xs" aria-label="Publisher usage policy">
                  <strong className="block text-[11px] uppercase tracking-wide mb-1">Publisher usage notes</strong>
                  <span>{sourcePolicy}</span>
                  <span>Review these restrictions before publishing. Automatic checks enforce required source attribution.</span>
                </aside>
              )}
            </div>

            {/* Form Group 2: Headline Override */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="headline-input"
                  className="block text-xs font-bold tracking-wide uppercase text-[#111111]"
                >
                  Card Headline Override
                </label>
                <span className="text-[11px] font-semibold text-[#767676] px-2 py-0.5 rounded-full bg-[#F8F9FA] border border-[#E5E5E5]">
                  {headlineOverride.length} chars
                </span>
              </div>

              <textarea
                id="headline-input"
                rows={3}
                className="w-full p-4 rounded-xl border border-[#E5E5E5] text-xs sm:text-sm text-[#111111] placeholder:text-[#999999] focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none min-h-[96px] leading-relaxed resize-y transition-all"
                placeholder="Enter bold, punchy headline to render on the graphic…"
                value={headlineOverride}
                onChange={e => setHeadlineOverride(e.target.value)}
              />

              <p className="text-[11px] text-[#767676] leading-relaxed">
                Tip: Keep headlines between 60–120 characters for optimal typography and visual balance.
              </p>
            </div>

            {/* Form Group 3: Facebook Post Caption */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="caption-input"
                  className="block text-xs font-bold tracking-wide uppercase text-[#111111]"
                >
                  Facebook Post Caption
                </label>
                <button
                  type="button"
                  onClick={handleCopyCaption}
                  className="text-xs font-semibold text-[#111111] hover:underline flex items-center gap-1 cursor-pointer"
                >
                  {copiedCaption ? <Check size={12} className="text-[#15803D]" /> : <Copy size={12} />}
                  <span>{copiedCaption ? 'Copied!' : 'Copy Caption'}</span>
                </button>
              </div>

              <textarea
                id="caption-input"
                rows={6}
                className="w-full p-4 rounded-xl border border-[#E5E5E5] text-xs sm:text-sm font-mono text-[#111111] placeholder:text-[#999999] focus:border-[#111111] focus:ring-1 focus:ring-[#111111] outline-none min-h-[160px] leading-relaxed resize-y transition-all"
                placeholder="Post caption text, hashtags, attribution and link…"
                value={caption}
                onChange={e => { setCaption(e.target.value); captionEditedRef.current = true }}
              />

              <div className="flex items-center justify-between text-[11px] text-[#767676]">
                <span>Auto-generated from article summary &amp; publisher source</span>
                <span className="font-semibold">{caption.length} characters</span>
              </div>
            </div>

            {/* Form Group 4: Footer Action Hub & Editorial Status */}
            <div className="pt-6 border-t border-[#E5E5E5] flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-xs text-[#767676] flex items-center gap-2 self-start sm:self-auto">
                <span className="live-dot" />
                <span>
                  Editorial Status: <strong className="text-[#111111] font-semibold">Draft Ready</strong>
                </span>
              </div>

              {/* Action Buttons: Save as Draft & Save & Approve */}
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => handleSaveDraft(false)}
                  disabled={saving || !selectedArticle}
                  className="btn btn-secondary h-11 px-5 flex-1 sm:flex-initial text-xs font-semibold cursor-pointer"
                >
                  <Save size={14} />
                  <span>Save as Draft</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSaveDraft(true)}
                  disabled={saving || !selectedArticle}
                  className="btn btn-primary h-11 px-5 flex-1 sm:flex-initial text-xs font-semibold cursor-pointer shadow-xs hover:shadow"
                >
                  <CheckCircle2 size={14} />
                  <span>Save &amp; Approve</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
