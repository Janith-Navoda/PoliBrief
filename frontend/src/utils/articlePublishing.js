const STATUS = {
  DRAFT: { label: 'Draft', badge: 'badge-warning', action: 'Continue Editing' },
  READY_FOR_REVIEW: { label: 'In Review', badge: 'badge-warning', action: 'View Draft' },
  APPROVED: { label: 'Approved', badge: 'badge-success', action: 'View Approved Draft' },
  PUBLISHING: { label: 'Publishing', badge: 'badge-warning', action: 'View Status' },
  FAILED: { label: 'Failed', badge: 'badge-warning', action: 'Review Failed Draft' },
  PUBLISHED: { label: 'Published', badge: 'badge-success' },
  MANUALLY_RECORDED: { label: 'Manually Recorded', badge: 'badge-neutral' },
}

export function getArticlePublishingPresentation(article) {
  const state = STATUS[article?.publishing_status] || null
  return state ? { ...state, status: article.publishing_status } : null
}
