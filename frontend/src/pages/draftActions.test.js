import test from 'node:test'
import assert from 'node:assert/strict'
import { getDraftActionState, releasePublish, tryAcquirePublish } from './draftActions.js'

const validMeta = { configured: true, valid: true, loading: false }

test('only approved drafts expose API and manual publication actions', () => {
  const approved = getDraftActionState({ status: 'APPROVED' }, validMeta)
  assert.equal(approved.publishViaApi, true)
  assert.equal(approved.markPublishedManually, true)

  const draft = getDraftActionState({ status: 'DRAFT' }, validMeta)
  assert.equal(draft.publishViaApi, false)
  assert.equal(draft.markPublishedManually, false)
})

test('missing, invalid, or still-loading Meta status disables API publishing', () => {
  for (const status of [
    { configured: false, valid: false, loading: false },
    { configured: true, valid: false, loading: false },
    { configured: true, valid: true, loading: true },
    null,
  ]) {
    assert.equal(getDraftActionState({ status: 'APPROVED' }, status).publishViaApi, false)
  }
})

test('published drafts keep their record and link actions without destructive delete', () => {
  const actions = getDraftActionState(
    { status: 'PUBLISHED' },
    validMeta,
    { fb_link: 'https://facebook.com/test-post' },
  )
  assert.equal(actions.viewPublication, true)
  assert.equal(actions.openFacebookPost, true)
  assert.equal(actions.delete, false)
  assert.equal(actions.publishViaApi, false)
})

test('publishing drafts cannot be deleted or published again', () => {
  const actions = getDraftActionState({ status: 'PUBLISHING' }, validMeta)
  assert.equal(actions.delete, false)
  assert.equal(actions.publishViaApi, false)
})

test('publish lock allows one in-flight request per draft', () => {
  const lock = new Set()
  assert.equal(tryAcquirePublish(lock, 12), true)
  assert.equal(tryAcquirePublish(lock, 12), false)
  releasePublish(lock, 12)
  assert.equal(tryAcquirePublish(lock, 12), true)
})
