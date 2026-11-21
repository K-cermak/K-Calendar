import { describe, expect, it } from 'vitest'
import type { Occurrence } from '@/api/client'
import { parseDate } from '@/dates'
import { groupByDay } from './groupByDay'

function occ(id: string, start: string, end: string, allDay = false): Occurrence {
  return {
    id,
    event_id: 1,
    calendar_id: 1,
    title: id,
    location: '',
    color: 'blue',
    all_day: allDay,
    start,
    end,
    start_utc: '',
    end_utc: '',
    tags: [],
    recurring: false,
    read_only: false,
  }
}

describe('groupByDay', () => {
  it('puts all-day events on every day they cover, first', () => {
    const groups = groupByDay(
      [
        occ('meeting', '2026-11-24T09:00:00', '2026-11-24T10:00:00'),
        occ('trip', '2026-11-23', '2026-11-26', true),
        occ('early', '2026-11-24T07:00:00', '2026-11-24T08:00:00'),
      ],
      parseDate('2026-11-24'),
      parseDate('2026-12-01'),
    )
    expect(groups.map((g) => [g.day, g.items.map((i) => i.id)])).toEqual([
      ['2026-11-24', ['trip', 'early', 'meeting']],
      ['2026-11-25', ['trip']],
    ])
  })
})
