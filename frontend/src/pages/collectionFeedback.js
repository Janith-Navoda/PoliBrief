export function getCollectionFeedback(result = {}, source = null) {
  const newCount = result.new_articles ?? 0
  const errors = result.errors || []
  const failed = source
    ? Boolean(result.error || errors.some(item => item.source_id === source.id))
    : errors.length > 0

  if (failed && source) {
    return { type: 'error', message: `${source.publisher_name} collection failed. See the source card for details.` }
  }
  if (failed) {
    return {
      type: 'error',
      message: `${newCount} articles saved; ${errors.length} source${errors.length === 1 ? '' : 's'} failed. See source cards for details.`,
    }
  }
  if (source) {
    return { type: 'success', message: `Updated ${source.publisher_name}: ${newCount} new articles saved.` }
  }
  return { type: 'success', message: `Collection complete: ${newCount} new articles saved.` }
}
