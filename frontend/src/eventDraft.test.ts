import { describe, expect, it } from 'vitest'
import type { EventDetail } from '@/api/client'
import {
  draftFromEvent,
  draftFromSpan,
  moveStart,
  problem,
  toBody,
  toggleAllDay,
} from './eventDraft'

describe('drafts from the grid', () => {
  it('turns a selected time range into a timed draft', () => {
    const draft = draftFromSpan(
      { start: '2026-11-23T09:30:00', end: '2026-11-23T11:00:00', allDay: false },
      1,
      'Europe/Prague',
    )
    expect(draft).toMatchObject({
      all_day: false,
      startDate: '2026-11-23',
      startTime: '09:30',
      endDate: '2026-11-23',
      endTime: '11:00',
      timezone: 'Europe/Prague',
    })
  })

  it('gives a tapped time an hour', () => {
    const draft = draftFromSpan({ start: '2026-11-23T23:30:00', end: '', allDay: false }, 1, 'UTC')
    expect([draft.endDate, draft.endTime]).toEqual(['2026-11-24', '00:30'])
  })

  it('shows an all-day selection with its inclusive last day', () => {
    const draft = draftFromSpan({ start: '2026-05-03', end: '2026-05-06', allDay: true }, 1, 'UTC')
    expect([draft.startDate, draft.endDate]).toEqual(['2026-05-03', '2026-05-05'])
    const single = draftFromSpan({ start: '2026-05-03', end: '', allDay: true }, 1, 'UTC')
    expect(single.endDate).toBe('2026-05-03')
  })
})

describe('toBody', () => {
  it('sends the exclusive end for all-day events', () => {
    const draft = draftFromSpan({ start: '2026-05-03', end: '2026-05-04', allDay: true }, 7, 'UTC')
    expect(toBody({ ...draft, title: 'Birthday' })).toMatchObject({
      calendar_id: 7,
      title: 'Birthday',
      all_day: true,
      start: '2026-05-03',
      end: '2026-05-04',
    })
  })

  it('sends wall-clock times with the zone for timed events', () => {
    const draft = draftFromSpan(
      { start: '2026-11-23T09:00:00', end: '2026-11-23T10:00:00', allDay: false },
      1,
      'Asia/Tokyo',
    )
    expect(toBody(draft)).toMatchObject({
      start: '2026-11-23T09:00:00',
      end: '2026-11-23T10:00:00',
      timezone: 'Asia/Tokyo',
    })
  })
})

describe('editing', () => {
  const event: EventDetail = {
    id: 1,
    calendar_id: 2,
    uid: 'u',
    title: 'Trip',
    description: '',
    location: '',
    color: null,
    all_day: true,
    start: '2026-07-10',
    end: '2026-07-13',
    timezone: null,
    rrule: null,
    recurring: false,
    occurrence: null,
    tags: [{ id: 1, name: 'travel', color: 'teal' }],
    read_only: false,
    created_at_utc: '',
    updated_at_utc: '',
  }

  it('round-trips an all-day event through the inclusive form', () => {
    const draft = draftFromEvent(event, 'Europe/Prague')
    expect([draft.startDate, draft.endDate, draft.tags]).toEqual([
      '2026-07-10',
      '2026-07-12',
      ['travel'],
    ])
    expect(toBody(draft)).toMatchObject({ start: '2026-07-10', end: '2026-07-13' })
  })

  it('keeps the duration when the start moves', () => {
    const timed = draftFromSpan(
      { start: '2026-11-23T09:00:00', end: '2026-11-23T10:30:00', allDay: false },
      1,
      'UTC',
    )
    expect(moveStart(timed, '2026-11-23', '23:00')).toMatchObject({
      endDate: '2026-11-24',
      endTime: '00:30',
    })
    const trip = draftFromEvent(event, 'UTC')
    expect(moveStart(trip, '2026-08-01', '').endDate).toBe('2026-08-03')
  })

  it('reports an end before the start', () => {
    const draft = draftFromEvent(event, 'UTC')
    expect(problem({ ...draft, endDate: '2026-07-09' })).toBe('endBeforeStart')
    expect(problem(toggleAllDay(draft, false))).toBeNull()
  })
})
