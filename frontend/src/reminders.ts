/**
 * Reminder offsets as the server stores them (SPEC 8): minutes before the start. For all-day events
 * they count from midnight in the user's zone: 360 is the day before at 18:00, -540 the day itself
 * at 09:00.
 */

export const TIMED_PRESETS = [0, 5, 10, 15, 30, 60, 1440] as const
export const ALL_DAY_PRESETS = [-540, 360, 1440 - 9 * 60] as const
export const MAX_MINUTES = 4 * 7 * 24 * 60

export interface AllDayReminder {
  dayBefore: boolean
  time: string // HH:MM
}

function hhmm(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

export function toAllDay(minutes: number): AllDayReminder {
  if (minutes <= 0) return { dayBefore: false, time: hhmm(Math.min(-minutes, 1439)) }
  return { dayBefore: true, time: hhmm(Math.max(1440 - minutes, 0)) }
}

export function fromAllDay(reminder: AllDayReminder): number {
  const [h, m] = reminder.time.split(':').map(Number)
  const ofDay = (h ?? 0) * 60 + (m ?? 0)
  return reminder.dayBefore ? 1440 - ofDay : -ofDay
}

export type TimedUnit = 'minutes' | 'hours' | 'days'

/** The largest unit that divides the offset evenly: 120 is 2 hours, 90 stays 90 minutes. */
export function toUnit(minutes: number): { amount: number; unit: TimedUnit } {
  if (minutes > 0 && minutes % 1440 === 0) return { amount: minutes / 1440, unit: 'days' }
  if (minutes > 0 && minutes % 60 === 0) return { amount: minutes / 60, unit: 'hours' }
  return { amount: minutes, unit: 'minutes' }
}

export function fromUnit(amount: number, unit: TimedUnit): number {
  const minutes = amount * (unit === 'days' ? 1440 : unit === 'hours' ? 60 : 1)
  return Math.min(Math.max(Math.round(minutes), 0), MAX_MINUTES)
}

export interface ReminderWords {
  t: (key: string, values?: Record<string, unknown>, plural?: number) => string
  time: (hhmm: string) => string
}

export function describeReminder(minutes: number, allDay: boolean, words: ReminderWords): string {
  if (allDay) {
    const { dayBefore, time } = toAllDay(minutes)
    return words.t(dayBefore ? 'reminders.dayBefore' : 'reminders.sameDay', {
      time: words.time(time),
    })
  }
  if (minutes === 0) return words.t('reminders.atStart')
  const { amount, unit } = toUnit(minutes)
  return words.t(`reminders.before.${unit}`, { n: amount }, amount)
}
