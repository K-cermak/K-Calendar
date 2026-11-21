import { describe, expect, it } from 'vitest'
import { relativeTime } from './format'

const NOW = Date.parse('2026-11-21T12:00:00Z')

describe('relativeTime', () => {
  it('picks the largest fitting unit', () => {
    expect(relativeTime('2026-11-21T09:00:00Z', 'en', NOW)).toBe('3 hours ago')
    expect(relativeTime('2026-11-28T12:00:00Z', 'en', NOW)).toBe('next week')
    expect(relativeTime('2026-11-26T12:00:00Z', 'en', NOW)).toBe('in 5 days')
  })

  it('calls anything under a minute now', () => {
    expect(relativeTime('2026-11-21T11:59:40Z', 'en', NOW)).toBe('now')
  })
})
