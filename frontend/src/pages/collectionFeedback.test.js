import test from 'node:test'
import assert from 'node:assert/strict'
import { getCollectionFeedback } from './collectionFeedback.js'

test('refresh all reports partial collection failure and saved count', () => {
  assert.deepEqual(
    getCollectionFeedback({ new_articles: 3, errors: [{ source_id: 7 }] }),
    { type: 'error', message: '3 articles saved; 1 source failed. See source cards for details.' },
  )
})

test('single source reports failure returned by the API', () => {
  assert.deepEqual(
    getCollectionFeedback({ new_articles: 0, errors: [{ source_id: 7 }] }, { id: 7, publisher_name: 'BBC' }),
    { type: 'error', message: 'BBC collection failed. See the source card for details.' },
  )
})

test('successful zero-new refresh is reported as success', () => {
  assert.deepEqual(
    getCollectionFeedback({ new_articles: 0, errors: [] }, { id: 7, publisher_name: 'BBC' }),
    { type: 'success', message: 'Updated BBC: 0 new articles saved.' },
  )
})
