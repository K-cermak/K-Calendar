import type { WorkingHours, WorkingInterval } from '@/api/client'
import type { WeekStart } from '@/dates'

export const WORKING_DAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const satisfies readonly (keyof WorkingHours)[]
export type WorkingDay = (typeof WORKING_DAYS)[number]

export const MAX_INTERVALS = 6
const LAST_MINUTE = '23:59'

/** The days in the order the user's week runs. */
export function orderedDays(weekStart: WeekStart): WorkingDay[] {
  return weekStart === 'sunday' ? ['sunday', ...WORKING_DAYS.slice(0, 6)] : [...WORKING_DAYS]
}

/** The hours as FullCalendar's business hours, which number the days from Sunday. */
export function toBusinessHours(
  hours: WorkingHours,
): { daysOfWeek: number[]; startTime: string; endTime: string }[] {
  return WORKING_DAYS.flatMap((day, index) =>
    hours[day].map((interval) => ({
      daysOfWeek: [(index + 1) % 7],
      startTime: interval.start,
      endTime: interval.end,
    })),
  )
}

/** True when a time ends before it starts or two times overlap: the server refuses both. */
export function dayIsInvalid(intervals: WorkingInterval[]): boolean {
  const sorted = [...intervals].sort((a, b) => a.start.localeCompare(b.start))
  return sorted.some((interval, i) => {
    const before = sorted[i - 1]
    return (
      !interval.start ||
      !interval.end ||
      interval.end <= interval.start ||
      (!!before && interval.start < before.end)
    )
  })
}

function plusHour(time: string): string {
  const [hours = 0, minutes = 0] = time.split(':').map(Number)
  const next = hours * 60 + minutes + 60
  if (next >= 24 * 60) return LAST_MINUTE
  return `${String(Math.floor(next / 60)).padStart(2, '0')}:${String(next % 60).padStart(2, '0')}`
}

/**
 * The time "Add" puts on a day: office hours on an empty day, else the hour after the last time,
 * which is what a split shift or an evening block usually is. Null when the day is full.
 */
export function nextInterval(intervals: WorkingInterval[]): WorkingInterval | null {
  if (!intervals.length) return { start: '09:00', end: '17:00' }
  const last = intervals.reduce((a, b) => (b.end > a.end ? b : a))
  if (intervals.length >= MAX_INTERVALS || last.end >= LAST_MINUTE) return null
  return { start: last.end, end: plusHour(last.end) }
}
