import test from 'node:test'
import assert from 'node:assert/strict'
import { getSourcePolicyDisplay } from './sourcePolicy.js'

test('source policy flags render as readable labels', () => {
  assert.deepEqual(getSourcePolicyDisplay('{"attribution_required":true,"commercial_use":false}'), {
    labels: ['Attribution Required', 'Commercial Use Restricted'],
    notes: [],
    needsReview: false,
  })
})

test('commercial-use true is clearly flagged for license verification', () => {
  const result = getSourcePolicyDisplay('{"commercial_use":true}')
  assert.equal(result.labels[0], 'Commercial Use Flagged as Allowed — Verify License')
  assert.equal(result.needsReview, false)
})

test('unknown metadata is not shown raw and is flagged for review', () => {
  const result = getSourcePolicyDisplay('{"license_type":"unknown"}')
  assert.deepEqual(result.labels, [])
  assert.equal(result.needsReview, true)
})

test('malformed or non-object metadata is handled with a review flag', () => {
  for (const value of ['{malformed', '[]', '"plain text"']) {
    const result = getSourcePolicyDisplay(value)
    assert.deepEqual(result.labels, [])
    assert.deepEqual(result.notes, [])
    assert.equal(result.needsReview, true)
  }
})
