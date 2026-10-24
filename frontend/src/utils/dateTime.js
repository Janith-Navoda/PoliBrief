export const DISPLAY_TIME_ZONE = 'Asia/Colombo'

const naiveApiTimestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/
const apiDate = /^\d{4}-\d{2}-\d{2}$/
const explicitZone = /(?:[zZ]|[+-]\d{2}:\d{2})$/

/**
 * SQLite strips tzinfo from our timezone=True columns. Those values are
 * UTC-naive because backend writes are UTC-aware; explicit API offsets remain
 * authoritative. This avoids interpreting SQLite's serialized value as the
 * Windows machine's local time.
 */
export function parseApiTimestamp(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value !== 'string' || !value.trim()) return null

  const input = value.trim()
  let normalized = input
  if (apiDate.test(input)) normalized = `${input}T00:00:00Z`
  else if (naiveApiTimestamp.test(input)) normalized = `${input}Z`
  else if (!explicitZone.test(input)) return null

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: DISPLAY_TIME_ZONE,
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})

export function formatPoliTimestamp(value, fallback = '—') {
  const date = parseApiTimestamp(value)
  if (!date) return fallback
  return `${dateTimeFormatter.format(date).replace(' at ', ', ')} SLST`
}
