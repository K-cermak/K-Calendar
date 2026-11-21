const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

/**
 * "3 hours ago", "in 7 days": how far an instant is from now. Relative, so no time zone is involved;
 * wall-clock times always come ready-made from the server (SPEC 5).
 */
export function relativeTime(iso: string, locale: string, now: number = Date.now()): string {
  const seconds = (Date.parse(iso) - now) / 1000
  const format = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit)
  }
  return format.format(0, 'second')
}
