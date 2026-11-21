import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'
import {
  describeReminder,
  fromAllDay,
  fromUnit,
  toAllDay,
  toUnit,
  type ReminderWords,
} from './reminders'

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
const words: ReminderWords = {
  t: (key, values, plural) =>
    plural === undefined
      ? i18n.global.t(key, values ?? {})
      : i18n.global.t(key, values ?? {}, plural),
  time: (value) => value,
}

describe('all-day reminders', () => {
  it('round-trip between offsets and day plus time', () => {
    expect(toAllDay(360)).toEqual({ dayBefore: true, time: '18:00' })
    expect(toAllDay(-540)).toEqual({ dayBefore: false, time: '09:00' })
    expect(toAllDay(0)).toEqual({ dayBefore: false, time: '00:00' })
    expect(fromAllDay({ dayBefore: true, time: '18:00' })).toBe(360)
    expect(fromAllDay({ dayBefore: false, time: '09:30' })).toBe(-570)
  })
})

describe('timed reminders', () => {
  it('use the largest even unit', () => {
    expect(toUnit(120)).toEqual({ amount: 2, unit: 'hours' })
    expect(toUnit(90)).toEqual({ amount: 90, unit: 'minutes' })
    expect(toUnit(2880)).toEqual({ amount: 2, unit: 'days' })
    expect(fromUnit(3, 'hours')).toBe(180)
    expect(fromUnit(100, 'days')).toBe(4 * 7 * 24 * 60)
  })
})

describe('describeReminder', () => {
  it('reads naturally', () => {
    expect(describeReminder(0, false, words)).toBe('At the start')
    expect(describeReminder(5, false, words)).toBe('5 minutes before')
    expect(describeReminder(60, false, words)).toBe('1 hour before')
    expect(describeReminder(1440, false, words)).toBe('1 day before')
    expect(describeReminder(360, true, words)).toBe('The day before at 18:00')
    expect(describeReminder(-540, true, words)).toBe('On the day at 09:00')
  })
})
