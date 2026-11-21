import type { EventCreate, EventDetail, PaletteColor } from '@/api/client'
import { exclusiveEnd, inclusiveEnd, parseDate, parseDateTime } from '@/dates'

/** What the event editor edits. All-day end dates are inclusive here, as people think of them. */
export interface Draft {
  calendar_id: number
  title: string
  description: string
  location: string
  color: PaletteColor | null
  all_day: boolean
  startDate: string
  startTime: string
  endDate: string
  endTime: string
  timezone: string
  tags: string[]
}

export interface DraftSpan {
  start: string
  end: string
  allDay: boolean
}

const DEFAULT_START = '09:00'
const DEFAULT_END = '10:00'

function split(value: string): [string, string] {
  return [value.slice(0, 10), value.slice(11, 16)]
}

export function draftFromSpan(span: DraftSpan, calendarId: number, timezone: string): Draft {
  const base = {
    calendar_id: calendarId,
    title: '',
    description: '',
    location: '',
    color: null,
    tags: [],
    timezone,
  }
  if (span.allDay) {
    const end = span.end || exclusiveEnd(span.start)
    return {
      ...base,
      all_day: true,
      startDate: span.start.slice(0, 10),
      endDate: inclusiveEnd(end.slice(0, 10)),
      startTime: DEFAULT_START,
      endTime: DEFAULT_END,
    }
  }
  const start = parseDateTime(span.start)
  const end = span.end ? parseDateTime(span.end) : start.add({ hours: 1 })
  const [startDate, startTime] = split(start.toString())
  const [endDate, endTime] = split(end.toString())
  return { ...base, all_day: false, startDate, startTime, endDate, endTime }
}

export function draftFromEvent(event: EventDetail, fallbackZone: string): Draft {
  const base = {
    calendar_id: event.calendar_id,
    title: event.title,
    description: event.description,
    location: event.location,
    color: event.color,
    tags: event.tags.map((t) => t.name),
    timezone: event.timezone ?? fallbackZone,
  }
  if (event.all_day) {
    return {
      ...base,
      all_day: true,
      startDate: event.start,
      endDate: inclusiveEnd(event.end),
      startTime: DEFAULT_START,
      endTime: DEFAULT_END,
    }
  }
  const [startDate, startTime] = split(event.start)
  const [endDate, endTime] = split(event.end)
  return { ...base, all_day: false, startDate, startTime, endDate, endTime }
}

/** Switching all-day on or off keeps the days; the times stay as they were last set. */
export function toggleAllDay(draft: Draft, allDay: boolean): Draft {
  return { ...draft, all_day: allDay }
}

/** Moving the start keeps the duration, as calendars usually do. */
export function moveStart(draft: Draft, startDate: string, startTime: string): Draft {
  if (draft.all_day) {
    const days = parseDate(draft.endDate).since(parseDate(draft.startDate)).days
    return { ...draft, startDate, endDate: parseDate(startDate).add({ days }).toString() }
  }
  const oldStart = parseDateTime(`${draft.startDate}T${draft.startTime}`)
  const oldEnd = parseDateTime(`${draft.endDate}T${draft.endTime}`)
  const newStart = parseDateTime(`${startDate}T${startTime}`)
  const newEnd = newStart.add(oldEnd.since(oldStart))
  const [endDate, endTime] = split(newEnd.toString())
  return { ...draft, startDate, startTime, endDate, endTime }
}

export type DraftProblem = 'endBeforeStart' | null

export function problem(draft: Draft): DraftProblem {
  if (draft.all_day) return draft.endDate < draft.startDate ? 'endBeforeStart' : null
  return `${draft.endDate}T${draft.endTime}` < `${draft.startDate}T${draft.startTime}`
    ? 'endBeforeStart'
    : null
}

export function toBody(draft: Draft): EventCreate {
  const body = {
    calendar_id: draft.calendar_id,
    title: draft.title,
    description: draft.description,
    location: draft.location,
    color: draft.color,
    all_day: draft.all_day,
    tags: draft.tags,
  }
  if (draft.all_day) {
    return { ...body, start: draft.startDate, end: exclusiveEnd(draft.endDate) }
  }
  return {
    ...body,
    start: `${draft.startDate}T${draft.startTime}:00`,
    end: `${draft.endDate}T${draft.endTime}:00`,
    timezone: draft.timezone,
  }
}
