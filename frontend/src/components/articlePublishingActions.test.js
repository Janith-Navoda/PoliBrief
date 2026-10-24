import test from 'node:test'
import assert from 'node:assert/strict'
import { getArticlePublishingPresentation } from '../utils/articlePublishing.js'

test('articles without records retain the standard Create Post state', () => {
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'NONE' }), null)
})

test('draft and approved statuses resolve to the corresponding review action', () => {
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'DRAFT' }).action, 'Continue Editing')
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'READY_FOR_REVIEW' }).label, 'In Review')
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'APPROVED' }).action, 'View Approved Draft')
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'FAILED' }).action, 'Review Failed Draft')
})

test('confirmed Meta and manual records retain different visible labels', () => {
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'PUBLISHED' }).label, 'Published')
  assert.equal(getArticlePublishingPresentation({ publishing_status: 'MANUALLY_RECORDED' }).label, 'Manually Recorded')
})

test('unresolved state is represented as Publishing and has no create action', () => {
  const state = getArticlePublishingPresentation({ publishing_status: 'PUBLISHING' })
  assert.equal(state.label, 'Publishing')
  assert.equal(state.action, 'View Status')
})
