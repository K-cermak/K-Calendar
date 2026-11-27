/**
 * Calendar arithmetic on wall-clock values that come from the server ready-made (SPEC 5). Plain
 * dates and date-times only: nothing here knows or converts a time zone.
 */
import { Temporal } from 'temporal-polyfill'
import type { CalendarView } from '@/router'

export type WeekStart = 'monday' | 'sunday'
export type PlainDate = Temporal.PlainDate
export type PlainDateTime = Temporal.PlainDateTime

export const PHONE_WEEK_DAYS = 3

export function parseDate(value: string): PlainDate {
  return Temporal.PlainDate.from(value.slice(0, 10))
}

export function parseDateTime(value: string): PlainDateTime {
  return Temporal.PlainDateTime.from(value)
}

export function startOfWeek(day: PlainDate, weekStart: WeekStart): PlainDate {
  const first = weekStart === 'monday' ? 1 : 7
  return day.subtract({ days: (day.dayOfWeek - first + 7) % 7 })
}

/** The days a view shows, end exclusive. A month grid always shows six full weeks. */
export function visibleRange(
  view: CalendarView,
  anchor: PlainDate,
  weekStart: WeekStart,
  compact: boolean,
): { start: PlainDate; end: PlainDate } {
  switch (view) {
    case 'month': {
      const start = startOfWeek(anchor.with({ day: 1 }), weekStart)
      return { start, end: start.add({ weeks: 6 }) }
    }
    case 'week': {
      const start = compact ? anchor : startOfWeek(anchor, weekStart)
      return { start, end: start.add({ days: compact ? PHONE_WEEK_DAYS : 7 }) }
    }
    case 'day':
      return { start: anchor, end: anchor.add({ days: 1 }) }
    case 'agenda':
      return { start: anchor, end: anchor.add({ days: 30 }) }
  }
}

/** The anchor date after moving one step back (-1) or forward (+1) in a view. */
export function shift(
  view: CalendarView,
  anchor: PlainDate,
  step: -1 | 1,
  compact: boolean,
): PlainDate {
  switch (view) {
    case 'month':
      return anchor.with({ day: 1 }).add({ months: step })
    case 'week':
      return anchor.add({ days: step * (compact ? PHONE_WEEK_DAYS : 7) })
    case 'day':
      return anchor.add({ days: step })
    case 'agenda':
      return anchor.add({ weeks: step })
  }
}

// Intl formats in a zone; UTC on a date built from the plain fields just prints those fields back.
function asUtcDate(day: PlainDate | PlainDateTime): Date {
  const time = 'hour' in day ? [day.hour, day.minute] : [0, 0]
  return new Date(Date.UTC(day.year, day.month - 1, day.day, time[0], time[1]))
}

export function formatDate(
  day: PlainDate | PlainDateTime,
  locale: string,
  options: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: 'UTC' }).format(asUtcDate(day))
}

export function formatDateRange(
  start: PlainDate,
  endInclusive: PlainDate,
  locale: string,
  options: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: 'UTC' }).formatRange(
    asUtcDate(start),
    asUtcDate(endInclusive),
  )
}

export function formatTime(value: PlainDateTime, locale: string, timeFormat: '12' | '24'): string {
  return formatDate(value, locale, {
    hour: 'numeric',
    minute: '2-digit',
    hourCycle: timeFormat === '12' ? 'h12' : 'h23',
  })
}

export function rangeTitle(
  view: CalendarView,
  anchor: PlainDate,
  locale: string,
  weekStart: WeekStart,
  compact: boolean,
): string {
  if (view === 'month') return formatDate(anchor, locale, { month: 'long', year: 'numeric' })
  if (view === 'day') {
    return formatDate(anchor, locale, {
      weekday: 'short',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  }
  // The agenda list runs on past the week, but the arrows move by a week, so the title names it.
  const { start, end } =
    view === 'agenda'
      ? { start: anchor, end: shift('agenda', anchor, 1, compact) }
      : visibleRange(view, anchor, weekStart, compact)
  return formatDateRange(start, end.subtract({ days: 1 }), locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** All-day events end exclusively in the API (like iCalendar); people think of the last day. */
export function inclusiveEnd(exclusiveEnd: string): string {
  return parseDate(exclusiveEnd).subtract({ days: 1 }).toString()
}

export function exclusiveEnd(inclusiveEnd: string): string {
  return parseDate(inclusiveEnd).add({ days: 1 }).toString()
}
