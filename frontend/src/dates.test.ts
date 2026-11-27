import { describe, expect, it } from 'vitest'
import {
  exclusiveEnd,
  formatTime,
  inclusiveEnd,
  parseDate,
  parseDateTime,
  rangeTitle,
  shift,
  startOfWeek,
  visibleRange,
} from './dates'

const d = parseDate

describe('startOfWeek', () => {
  it('follows the week start preference', () => {
    expect(startOfWeek(d('2026-11-25'), 'monday').toString()).toBe('2026-11-23')
    expect(startOfWeek(d('2026-11-25'), 'sunday').toString()).toBe('2026-11-22')
    expect(startOfWeek(d('2026-11-22'), 'monday').toString()).toBe('2026-11-16')
    expect(startOfWeek(d('2026-11-22'), 'sunday').toString()).toBe('2026-11-22')
  })
})

describe('visibleRange', () => {
  it('covers six weeks for a month', () => {
    const { start, end } = visibleRange('month', d('2026-11-18'), 'monday', false)
    expect([start.toString(), end.toString()]).toEqual(['2026-10-26', '2026-12-07'])
  })

  it('shows seven days on a desktop week and three on a phone', () => {
    const desktop = visibleRange('week', d('2026-11-25'), 'monday', false)
    expect([desktop.start.toString(), desktop.end.toString()]).toEqual(['2026-11-23', '2026-11-30'])
    const phone = visibleRange('week', d('2026-11-25'), 'monday', true)
    expect([phone.start.toString(), phone.end.toString()]).toEqual(['2026-11-25', '2026-11-28'])
  })
})

describe('shift', () => {
  it('moves by the size of the view', () => {
    expect(shift('month', d('2026-01-31'), 1, false).toString()).toBe('2026-02-01')
    expect(shift('week', d('2026-11-25'), -1, false).toString()).toBe('2026-11-18')
    expect(shift('week', d('2026-11-25'), 1, true).toString()).toBe('2026-11-28')
    expect(shift('day', d('2026-12-31'), 1, false).toString()).toBe('2027-01-01')
  })
})

describe('all-day end dates', () => {
  it('converts between the exclusive API end and the inclusive end people edit', () => {
    expect(inclusiveEnd('2026-05-04')).toBe('2026-05-03')
    expect(exclusiveEnd('2026-05-03')).toBe('2026-05-04')
    expect(exclusiveEnd('2026-02-28')).toBe('2026-03-01')
    expect(inclusiveEnd('2028-03-01')).toBe('2028-02-29')
  })
})

describe('formatting', () => {
  it('prints wall-clock values unchanged, whatever the device zone', () => {
    const value = parseDateTime('2026-03-29T02:30:00')
    expect(formatTime(value, 'en', '24')).toBe('02:30')
    expect(formatTime(value, 'en', '12')).toBe('2:30 AM')
  })

  it('titles each view', () => {
    expect(rangeTitle('month', d('2026-11-18'), 'en', 'monday', false)).toBe('November 2026')
    expect(rangeTitle('week', d('2026-11-25'), 'en', 'monday', false).replace(/\s/g, ' ')).toBe(
      'Nov 23 – 29, 2026',
    )
    expect(rangeTitle('agenda', d('2026-11-27'), 'en', 'monday', true).replace(/\s/g, ' ')).toBe(
      'Nov 27 – Dec 3, 2026',
    )
  })
})
