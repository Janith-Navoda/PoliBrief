import test from 'node:test'
import assert from 'node:assert/strict'
import { formatPoliTimestamp, parseApiTimestamp } from './dateTime.js'

test('UTC-naive SQLite API timestamp is displayed in Asia/Colombo', () => {
  assert.equal(formatPoliTimestamp('2026-10-24T10:02:00'), 'Oct 24, 2026, 3:32 PM SLST')
})

test('missing and malformed timestamps use the supplied safe fallback', () => {
  assert.equal(parseApiTimestamp(null), null)
  assert.equal(parseApiTimestamp('not-a-date'), null)
  assert.equal(formatPoliTimestamp(undefined), '—')
  assert.equal(formatPoliTimestamp('', 'Never'), 'Never')
})

test('already timezone-aware timestamps preserve their represented instant', () => {
  assert.equal(formatPoliTimestamp('2026-10-24T10:02:00Z'), 'Oct 24, 2026, 3:32 PM SLST')
  assert.equal(formatPoliTimestamp('2026-10-24T15:32:00+05:30'), 'Oct 24, 2026, 3:32 PM SLST')
})

test('all timestamp shapes use the same readable format', () => {
  const naive = formatPoliTimestamp('2026-10-24T10:02:00')
  const aware = formatPoliTimestamp('2026-10-24T10:02:00Z')
  assert.equal(naive, aware)
  assert.match(naive, /^Oct 24, 2026, 3:32 PM SLST$/)
})
