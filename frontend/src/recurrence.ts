/**
 * Building and describing recurrence rules for the editor (SPEC 5). The rules are only written
 * and read here; expanding them into occurrences is the server's job.
 */
import type { PlainDate } from '@/dates'

export type Freq = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
export type Preset =
  'none' | 'daily' | 'weekdays' | 'weekly' | 'monthlyDay' | 'monthlyWeekday' | 'yearly' | 'custom'

export const PRESETS: Preset[] = [
  'none',
  'daily',
  'weekdays',
  'weekly',
  'monthlyDay',
  'monthlyWeekday',
  'yearly',
  'custom',
]

export const WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'] as const
export type Weekday = (typeof WEEKDAYS)[number]

export type RuleEnd =
  { kind: 'never' } | { kind: 'until'; date: string } | { kind: 'count'; count: number }

/** What the custom form edits. Anything else a rule might hold is not representable here. */
export interface CustomRule {
  freq: Freq
  interval: number
  byDay: Weekday[]
  end: RuleEnd
}

type Parts = Map<string, string>

export function parseParts(rule: string): Parts {
  const parts: Parts = new Map()
  for (const part of rule.replace(/^RRULE:/i, '').split(';')) {
    const [key, value] = part.split('=')
    if (key && value !== undefined) parts.set(key.trim().toUpperCase(), value.trim().toUpperCase())
  }
  return parts
}

function join(parts: [string, string | undefined][]): string {
  return parts
    .filter((p): p is [string, string] => p[1] !== undefined)
    .map(([k, v]) => `${k}=${v}`)
    .join(';')
}

export function weekdayOf(day: PlainDate): Weekday {
  return WEEKDAYS[day.dayOfWeek - 1]!
}

/** 1 to 4 for the first to fourth weekday of the month; a fifth one is "the last" (-1). */
export function weekdayPosition(day: PlainDate): number {
  const n = Math.ceil(day.day / 7)
  return n > 4 ? -1 : n
}

export function presetRule(preset: Preset, start: PlainDate): string | null {
  switch (preset) {
    case 'none':
    case 'custom':
      return null
    case 'daily':
      return 'FREQ=DAILY'
    case 'weekdays':
      return 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'
    case 'weekly':
      return `FREQ=WEEKLY;BYDAY=${weekdayOf(start)}`
    case 'monthlyDay':
      return `FREQ=MONTHLY;BYMONTHDAY=${start.day}`
    case 'monthlyWeekday':
      return `FREQ=MONTHLY;BYDAY=${weekdayPosition(start)}${weekdayOf(start)}`
    case 'yearly':
      return 'FREQ=YEARLY'
  }
}

const SIMPLE_KEYS = new Set(['FREQ', 'INTERVAL', 'BYDAY', 'COUNT', 'UNTIL', 'WKST'])

/** The custom form's view of a rule, or null if the form cannot show it faithfully. */
export function parseCustom(rule: string, start: PlainDate): CustomRule | null {
  const parts = parseParts(rule)
  const freq = parts.get('FREQ') as Freq | undefined
  if (!freq || !['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'].includes(freq)) return null
  for (const key of parts.keys()) if (!SIMPLE_KEYS.has(key)) return null
  const interval = Number(parts.get('INTERVAL') ?? '1')
  if (!Number.isInteger(interval) || interval < 1) return null
  const byDayText = parts.get('BYDAY')
  let byDay: Weekday[] = []
  if (byDayText) {
    if (freq !== 'WEEKLY') return null
    const days = byDayText.split(',')
    if (!days.every((d): d is Weekday => (WEEKDAYS as readonly string[]).includes(d))) return null
    byDay = WEEKDAYS.filter((d) => days.includes(d))
  } else if (freq === 'WEEKLY') {
    byDay = [weekdayOf(start)]
  }
  let end: RuleEnd = { kind: 'never' }
  const count = parts.get('COUNT')
  const until = parts.get('UNTIL')
  if (count) end = { kind: 'count', count: Number(count) }
  else if (until)
    end = { kind: 'until', date: `${until.slice(0, 4)}-${until.slice(4, 6)}-${until.slice(6, 8)}` }
  return { freq, interval, byDay, end }
}

export function buildCustom(custom: CustomRule, allDay: boolean): string {
  const until =
    custom.end.kind === 'until'
      ? custom.end.date.replaceAll('-', '') + (allDay ? '' : 'T235959')
      : undefined
  return join([
    ['FREQ', custom.freq],
    ['INTERVAL', custom.interval > 1 ? String(custom.interval) : undefined],
    ['BYDAY', custom.freq === 'WEEKLY' && custom.byDay.length ? custom.byDay.join(',') : undefined],
    ['COUNT', custom.end.kind === 'count' ? String(custom.end.count) : undefined],
    ['UNTIL', until],
  ])
}

function sameRule(a: string, b: string): boolean {
  const pa = parseParts(a)
  const pb = parseParts(b)
  if (pa.size !== pb.size) return false
  for (const [k, v] of pa) if (pb.get(k) !== v) return false
  return true
}

/**
 * Which editor choice shows a rule: a preset, 'custom' when the custom form can show it, or
 * 'unsupported' for a rule from elsewhere that only the summary can describe.
 */
export function matchRule(rule: string | null, start: PlainDate): Preset | 'unsupported' {
  if (!rule) return 'none'
  for (const preset of PRESETS) {
    const candidate = presetRule(preset, start)
    if (candidate && sameRule(candidate, rule)) return preset
  }
  if (sameRule(rule, 'FREQ=WEEKLY')) return 'weekly'
  return parseCustom(rule, start) ? 'custom' : 'unsupported'
}

export function defaultCustom(start: PlainDate): CustomRule {
  return { freq: 'WEEKLY', interval: 1, byDay: [weekdayOf(start)], end: { kind: 'never' } }
}

/** The texts a summary is made of, so this module stays free of the i18n setup. */
export interface Words {
  t: (key: string, values?: Record<string, unknown>, plural?: number) => string
  weekday: (day: Weekday) => string
  date: (iso: string) => string
}

const ORDINALS: Record<string, string> = {
  '1': 'first',
  '2': 'second',
  '3': 'third',
  '4': 'fourth',
  '-1': 'last',
}

/** "Every 2 weeks on Monday and Friday, 5 times": a readable sentence for any rule. */
export function summarize(rule: string, words: Words): string {
  const parts = parseParts(rule)
  const freq = parts.get('FREQ') ?? ''
  const interval = Number(parts.get('INTERVAL') ?? '1')
  const unit = { DAILY: 'day', WEEKLY: 'week', MONTHLY: 'month', YEARLY: 'year' }[freq]
  if (!unit) return words.t('repeat.summary.raw', { rule })
  const pieces = [words.t(`repeat.summary.every.${unit}`, { n: interval }, interval)]

  const byDay = parts.get('BYDAY')
  if (byDay) {
    const days = byDay.split(',').map((entry) => {
      const match = /^([+-]?\d)?([A-Z]{2})$/.exec(entry)
      const day = match?.[2] as Weekday | undefined
      if (!match || !day || !(WEEKDAYS as readonly string[]).includes(day)) return entry
      const ordinal = match[1] ? ORDINALS[String(Number(match[1]))] : undefined
      return ordinal
        ? words.t(`repeat.summary.ordinal.${ordinal}`, { day: words.weekday(day) })
        : words.weekday(day)
    })
    pieces.push(words.t('repeat.summary.onDays', { days: days.join(', ') }))
  }
  const byMonthDay = parts.get('BYMONTHDAY')
  if (byMonthDay) pieces.push(words.t('repeat.summary.onMonthDay', { days: byMonthDay }))

  const known = new Set(['FREQ', 'INTERVAL', 'BYDAY', 'BYMONTHDAY', 'COUNT', 'UNTIL', 'WKST'])
  const extra = [...parts.keys()].filter((k) => !known.has(k))
  if (extra.length) pieces.push(words.t('repeat.summary.more', { parts: extra.join(', ') }))

  const count = parts.get('COUNT')
  const until = parts.get('UNTIL')
  if (count) pieces.push(words.t('repeat.summary.count', { n: Number(count) }, Number(count)))
  if (until) {
    const date = `${until.slice(0, 4)}-${until.slice(4, 6)}-${until.slice(6, 8)}`
    pieces.push(words.t('repeat.summary.until', { date: words.date(date) }))
  }
  return pieces.join(', ')
}

/** Presets read differently depending on the start date ("weekly on Tuesday"). */
export function presetLabel(preset: Preset, start: PlainDate, words: Words): string {
  const day = words.weekday(weekdayOf(start))
  const position = ORDINALS[String(weekdayPosition(start))] ?? 'first'
  return words.t(`repeat.preset.${preset}`, {
    day,
    date: start.day,
    nth: words.t(`repeat.summary.ordinal.${position}`, { day }),
    month: words.date(start.toString()),
  })
}
