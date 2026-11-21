import { describe, expect, it } from 'vitest'
import { occurrencesWithin } from './offline'

const list = {
  timezone: 'Europe/Prague',
  now: '2026-11-21T08:00:00',
  items: [
    { start: '2026-11-22T23:00:00', end: '2026-11-23T01:00:00', all_day: false },
    { start: '2026-11-23T09:00:00', end: '2026-11-23T10:00:00', all_day: false },
    { start: '2026-11-25', end: '2026-11-27', all_day: true },
    { start: '2026-11-30T00:00:00', end: '2026-11-30T01:00:00', all_day: false },
    { start: '2026-11-20', end: '2026-11-23', all_day: true },
  ],
}

describe('occurrencesWithin', () => {
  it('keeps what overlaps the range, timed and all-day alike', () => {
    const kept = occurrencesWithin(list, '2026-11-23', '2026-11-30').items.map((i) => i.start)
    expect(kept).toEqual(['2026-11-22T23:00:00', '2026-11-23T09:00:00', '2026-11-25'])
  })
})
