/** Shared by the service worker and the app; free of anything the worker cannot load. */

export interface OccurrenceList {
  timezone: string
  now: string
  items: { start: string; end: string; all_day: boolean }[]
}

export const API_CACHE_NAME = 'api-v1'

/**
 * The occurrences of a list that fall into [start, end). All values are wall-clock strings in the
 * same display zone, so comparing them as text is comparing times: no zone is involved.
 */
export function occurrencesWithin<T extends OccurrenceList>(
  list: T,
  start: string,
  end: string,
): T {
  const items = list.items.filter((item) =>
    item.start === item.end
      ? item.start >= start && item.start < end
      : item.start < end && item.end > start,
  )
  return { ...list, items }
}
