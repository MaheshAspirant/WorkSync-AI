export function cn(...values) {
  return values.filter(Boolean).join(' ')
}

export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(`${value}`.length === 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatShortDate(value) {
  if (!value) return '—'
  const date = new Date(`${value}`.length === 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function toISODate(date) {
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function addDays(date, days) {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

export function startOfWeek(date) {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  return addDays(d, diff)
}

export function humanize(value) {
  if (!value) return '—'
  return String(value)
    .toLowerCase()
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function initials(first, last) {
  return `${first?.[0] || ''}${last?.[0] || ''}`.toUpperCase() || '?'
}

export function percent(value, digits = 1) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function statusTone(status) {
  const key = String(status || '').toUpperCase()
  if (['APPROVED', 'COMPLETED', 'PRESENT', 'RESOLVED', 'APPLIED', 'ACTIVE', 'OK'].includes(key)) return 'green'
  if (['PENDING', 'REQUESTED', 'SCHEDULED', 'WARN', 'PARTIAL'].includes(key)) return 'amber'
  if (['REJECTED', 'CANCELLED', 'ABSENT', 'NO_SHOW', 'CRITICAL', 'FAIL', 'INFEASIBLE'].includes(key)) return 'red'
  if (['LATE', 'EARLY_DEPARTURE', 'MEDIUM', 'UNDERSTAFFED', 'HIGH'].includes(key)) return 'orange'
  if (['CONFIRMED', 'PUBLISHED', 'OPEN', 'SWAPPED_IN'].includes(key)) return 'blue'
  return 'slate'
}

export function buildQuery(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}
