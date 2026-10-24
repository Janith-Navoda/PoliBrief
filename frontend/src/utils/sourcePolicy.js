export function getSourcePolicyDisplay(raw) {
  if (raw == null || String(raw).trim() === '') return { labels: [], notes: [], needsReview: false }

  let policy
  try {
    policy = JSON.parse(raw)
  } catch {
    return { labels: [], notes: [], needsReview: true }
  }
  if (!policy || typeof policy !== 'object' || Array.isArray(policy)) {
    return { labels: [], notes: [], needsReview: true }
  }

  const labels = []
  const notes = []
  let needsReview = false

  if ('attribution_required' in policy) {
    if (policy.attribution_required === true) labels.push('Attribution Required')
    else if (policy.attribution_required !== false) needsReview = true
  }
  if ('commercial_use' in policy) {
    if (policy.commercial_use === false) labels.push('Commercial Use Restricted')
    else if (policy.commercial_use === true) labels.push('Commercial Use Flagged as Allowed — Verify License')
    else needsReview = true
  }
  if ('notes' in policy) {
    if (typeof policy.notes === 'string' && policy.notes.trim()) notes.push(policy.notes.trim())
    else if (policy.notes != null && typeof policy.notes !== 'string') needsReview = true
  }

  const recognized = new Set(['attribution_required', 'commercial_use', 'notes'])
  if (Object.keys(policy).some(key => !recognized.has(key))) needsReview = true
  if (!labels.length && !notes.length) needsReview = true

  return { labels, notes, needsReview }
}
