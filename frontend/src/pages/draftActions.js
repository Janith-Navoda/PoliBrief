export function getDraftActionState(draft, metaStatus, publication) {
  const approved = draft?.status === 'APPROVED'
  const published = draft?.status === 'PUBLISHED'
  const publishing = draft?.status === 'PUBLISHING'
  const apiAvailable = Boolean(metaStatus?.configured && metaStatus?.valid && !metaStatus?.loading)

  return {
    approved,
    apiAvailable,
    publishViaApi: approved && apiAvailable,
    markPublishedManually: approved,
    delete: !published && !publishing && !publication,
    viewPublication: published,
    openFacebookPost: published && Boolean(publication?.fb_link),
  }
}

export function tryAcquirePublish(lock, draftId) {
  if (lock.has(draftId)) return false
  lock.add(draftId)
  return true
}

export function releasePublish(lock, draftId) {
  lock.delete(draftId)
}
