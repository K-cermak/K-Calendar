import { formatDate, formatTime, inclusiveEnd, parseDate, parseDateTime } from '@/dates'

export interface Span {
  start: string
  end: string
  all_day: boolean
}

/** "Mon, 23 Nov · 09:00 – 10:00" or "23 – 25 Nov": a span of wall-clock values, as people read it. */
export function describeSpan(span: Span, locale: string, timeFormat: '12' | '24'): string {
  const day = { weekday: 'short', day: 'numeric', month: 'short' } as const
  if (span.all_day) {
    const first = parseDate(span.start)
    const last = parseDate(inclusiveEnd(span.end))
    if (first.equals(last)) return formatDate(first, locale, day)
    return `${formatDate(first, locale, day)} – ${formatDate(last, locale, day)}`
  }
  const start = parseDateTime(span.start)
  const end = parseDateTime(span.end)
  const from = formatTime(start, locale, timeFormat)
  const to = formatTime(end, locale, timeFormat)
  if (start.toPlainDate().equals(end.toPlainDate())) {
    return `${formatDate(start, locale, day)} · ${from} – ${to}`
  }
  return `${formatDate(start, locale, day)} ${from} – ${formatDate(end, locale, day)} ${to}`
}

export type TextPart = { text: string; href?: string }

const URL_PATTERN = /\bhttps?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]]/gi

/** Splits text into plain parts and links, so URLs can be rendered as links without any HTML. */
export function linkify(text: string): TextPart[] {
  const parts: TextPart[] = []
  let last = 0
  for (const match of text.matchAll(URL_PATTERN)) {
    const index = match.index
    if (index > last) parts.push({ text: text.slice(last, index) })
    parts.push({ text: match[0], href: match[0] })
    last = index + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last) })
  return parts
}

/** A link that opens the location in the device's maps app. */
export function mapsUrl(location: string, userAgent: string = navigator.userAgent): string {
  const query = encodeURIComponent(location)
  return /iPhone|iPad|Macintosh/.test(userAgent)
    ? `https://maps.apple.com/?q=${query}`
    : `https://www.google.com/maps/search/?api=1&query=${query}`
}
