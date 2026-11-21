import { describe, expect, it } from 'vitest'
import { describeSpan, linkify, mapsUrl } from './text'

describe('describeSpan', () => {
  it('shows a timed event on one day with its times', () => {
    const text = describeSpan(
      { start: '2026-11-23T09:00:00', end: '2026-11-23T10:30:00', all_day: false },
      'en',
      '24',
    )
    expect(text).toBe('Mon, Nov 23 · 09:00 – 10:30')
  })

  it('shows the inclusive last day of an all-day event', () => {
    expect(
      describeSpan({ start: '2026-05-03', end: '2026-05-04', all_day: true }, 'en', '24'),
    ).toBe('Sun, May 3')
    expect(
      describeSpan({ start: '2026-05-03', end: '2026-05-06', all_day: true }, 'en', '24'),
    ).toBe('Sun, May 3 – Tue, May 5')
  })
})

describe('linkify', () => {
  it('turns URLs into link parts and leaves trailing punctuation out', () => {
    expect(linkify('Agenda: https://example.com/a?b=1. Bring <b>snacks</b>')).toEqual([
      { text: 'Agenda: ' },
      { text: 'https://example.com/a?b=1', href: 'https://example.com/a?b=1' },
      { text: '. Bring <b>snacks</b>' },
    ])
  })

  it('ignores other schemes', () => {
    expect(linkify('javascript:alert(1)')).toEqual([{ text: 'javascript:alert(1)' }])
  })
})

describe('mapsUrl', () => {
  it('uses Apple Maps on Apple devices', () => {
    expect(mapsUrl('Room 4', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)')).toBe(
      'https://maps.apple.com/?q=Room%204',
    )
    expect(mapsUrl('Room 4', 'Mozilla/5.0 (Linux; Android 15)')).toContain('google.com/maps')
  })
})
