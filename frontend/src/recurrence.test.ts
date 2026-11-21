import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'
import { parseDate } from '@/dates'
import {
  buildCustom,
  matchRule,
  parseCustom,
  presetLabel,
  presetRule,
  summarize,
  type Words,
} from './recurrence'

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
const words: Words = {
  t: (key, values, plural) =>
    plural === undefined
      ? i18n.global.t(key, values ?? {})
      : i18n.global.t(key, values ?? {}, plural),
  weekday: (day) =>
    ({
      MO: 'Monday',
      TU: 'Tuesday',
      WE: 'Wednesday',
      TH: 'Thursday',
      FR: 'Friday',
      SA: 'Saturday',
      SU: 'Sunday',
    })[day],
  date: (iso) => iso,
}

const tuesday = parseDate('2026-11-24')
const lastFriday = parseDate('2026-11-27')

describe('presets', () => {
  it('derive their rule from the start date', () => {
    expect(presetRule('weekly', tuesday)).toBe('FREQ=WEEKLY;BYDAY=TU')
    expect(presetRule('monthlyDay', tuesday)).toBe('FREQ=MONTHLY;BYMONTHDAY=24')
    expect(presetRule('monthlyWeekday', tuesday)).toBe('FREQ=MONTHLY;BYDAY=4TU')
    expect(presetRule('monthlyWeekday', lastFriday)).toBe('FREQ=MONTHLY;BYDAY=4FR')
    expect(presetRule('monthlyWeekday', parseDate('2026-10-30'))).toBe('FREQ=MONTHLY;BYDAY=-1FR')
    expect(presetRule('none', tuesday)).toBeNull()
  })

  it('label themselves for the start date', () => {
    expect(presetLabel('weekly', tuesday, words)).toBe('Every week on Tuesday')
    expect(presetLabel('monthlyWeekday', parseDate('2026-10-30'), words)).toBe(
      'Every month on the last Friday',
    )
  })
})

describe('matchRule', () => {
  it('recognises presets regardless of part order', () => {
    expect(matchRule(null, tuesday)).toBe('none')
    expect(matchRule('BYDAY=TU;FREQ=WEEKLY', tuesday)).toBe('weekly')
    expect(matchRule('FREQ=WEEKLY', tuesday)).toBe('weekly')
    expect(matchRule('FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR', tuesday)).toBe('weekdays')
  })

  it('tells custom rules from ones the form cannot show', () => {
    expect(matchRule('FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=5', tuesday)).toBe('custom')
    expect(matchRule('FREQ=MONTHLY;BYDAY=MO;BYSETPOS=-1', tuesday)).toBe('unsupported')
    expect(matchRule('FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', tuesday)).toBe('unsupported')
  })
})

describe('custom rules', () => {
  it('round-trip through the form', () => {
    const rule = 'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=5'
    const custom = parseCustom(rule, tuesday)
    expect(custom).toEqual({
      freq: 'WEEKLY',
      interval: 2,
      byDay: ['MO', 'FR'],
      end: { kind: 'count', count: 5 },
    })
    expect(buildCustom(custom!, false)).toBe(rule)
  })

  it('end on a date at the end of that day, or on the date for all-day events', () => {
    const custom = {
      freq: 'DAILY' as const,
      interval: 1,
      byDay: [],
      end: { kind: 'until' as const, date: '2026-12-31' },
    }
    expect(buildCustom(custom, false)).toBe('FREQ=DAILY;UNTIL=20261231T235959')
    expect(buildCustom(custom, true)).toBe('FREQ=DAILY;UNTIL=20261231')
    expect(parseCustom('FREQ=DAILY;UNTIL=20261231T235959', tuesday)?.end).toEqual({
      kind: 'until',
      date: '2026-12-31',
    })
  })
})

describe('summarize', () => {
  it('reads like a sentence', () => {
    expect(summarize('FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=5', words)).toBe(
      'Every 2 weeks, on Monday, Friday, 5 times',
    )
    expect(summarize('FREQ=DAILY;UNTIL=20261231T235959', words)).toBe('Every day, until 2026-12-31')
    expect(summarize('FREQ=MONTHLY;BYDAY=-1FR', words)).toBe('Every month, on the last Friday')
  })

  it('names what it cannot describe instead of hiding it', () => {
    expect(summarize('FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', words)).toBe(
      'Every year, on the last Sunday, with BYMONTH',
    )
    expect(summarize('FREQ=HOURLY', words)).toBe('Custom rule: FREQ=HOURLY')
  })
})
