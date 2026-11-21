import type { Occurrence } from '@/api/client'
import { parseDate, type PlainDate } from '@/dates'

export interface DayGroup {
  day: string
  items: Occurrence[]
}

/**
 * Occurrences per day in [from, to): all-day events on every day they cover, timed ones on the
 * day they start, each day in time order with all-day events first.
 */
export function groupByDay(items: Occurrence[], from: PlainDate, to: PlainDate): DayGroup[] {
  const days = new Map<string, Occurrence[]>()
  const add = (day: string, item: Occurrence) => {
    const list = days.get(day)
    if (list) list.push(item)
    else days.set(day, [item])
  }
  for (const item of items) {
    if (!item.all_day) {
      const day = item.start.slice(0, 10)
      if (day >= from.toString() && day < to.toString()) add(day, item)
      continue
    }
    let day = parseDate(item.start)
    const end = parseDate(item.end)
    if (PlainDateLess(day, from)) day = from
    while (PlainDateLess(day, end) && PlainDateLess(day, to)) {
      add(day.toString(), item)
      day = day.add({ days: 1 })
    }
  }
  return [...days.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([day, list]) => ({
      day,
      items: list.sort((a, b) =>
        a.all_day !== b.all_day
          ? a.all_day
            ? -1
            : 1
          : a.start < b.start
            ? -1
            : a.start > b.start
              ? 1
              : 0,
      ),
    }))
}

function PlainDateLess(a: PlainDate, b: PlainDate): boolean {
  return a.toString() < b.toString()
}
