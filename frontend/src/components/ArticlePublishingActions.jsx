import { ExternalLink, Eye, PenSquare } from 'lucide-react'
import { getArticlePublishingPresentation } from '../utils/articlePublishing'

export default function ArticlePublishingActions({ article, onNavigate, onViewDraft }) {
  const presentation = getArticlePublishingPresentation(article)
  if (!presentation || presentation.status === 'NONE') {
    return onNavigate ? (
      <button
        type="button"
        onClick={() => onNavigate('studio', article)}
        className="btn btn-primary btn-sm text-xs py-1.5 px-3.5 cursor-pointer"
      >
        <PenSquare size={13} />
        <span>Create Post</span>
      </button>
    ) : null
  }

  const viewDraft = () => onViewDraft?.(article.publishing_draft_id)
  return (
    <div className="flex items-center gap-2 flex-wrap justify-end" data-publishing-status={presentation.status}>
      <span className={`badge ${presentation.badge} text-[10px]`} role="status">
        {presentation.label}
      </span>
      {(presentation.status === 'PUBLISHED' || presentation.status === 'MANUALLY_RECORDED') && (
        article.publication_url ? (
          <a
            href={article.publication_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary btn-sm text-xs py-1.5 px-3"
          >
            <ExternalLink size={13} />
            <span>View on Facebook</span>
          </a>
        ) : (
          <button type="button" onClick={() => onNavigate?.('published')} className="btn btn-secondary btn-sm text-xs py-1.5 px-3">
            <Eye size={13} />
            <span>View Publication Record</span>
          </button>
        )
      )}
      {presentation.action && (
        <button type="button" onClick={viewDraft} className="btn btn-secondary btn-sm text-xs py-1.5 px-3">
          <Eye size={13} />
          <span>{presentation.action}</span>
        </button>
      )}
    </div>
  )
}
