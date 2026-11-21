import { keepPreviousData, queryOptions, useMutation, useQuery } from '@tanstack/vue-query'
import { computed, onScopeDispose, ref, type MaybeRefOrGetter, toValue } from 'vue'
import { parseDateTime, type PlainDateTime } from '@/dates'
import {
  api,
  call,
  type Calendar,
  type CalendarCreate,
  type CalendarUpdate,
  type EventCreate,
  type EventDetail,
  type EventUpdate,
  type TagUpdate,
} from './client'
import { queryClient } from './queryClient'

export const calendarsQuery = queryOptions({
  queryKey: ['calendars'],
  queryFn: () => call(() => api.GET('/api/v1/calendars')),
})

export const tagsQuery = queryOptions({
  queryKey: ['tags'],
  queryFn: () => call(() => api.GET('/api/v1/tags')),
})

export function occurrencesQuery(start: string, end: string, tz: string) {
  return queryOptions({
    queryKey: ['occurrences', tz, start, end],
    queryFn: () =>
      call(() => api.GET('/api/v1/occurrences', { params: { query: { start, end, tz } } })),
  })
}

export function useOccurrences(
  range: MaybeRefOrGetter<{ start: string; end: string; tz: string } | null>,
) {
  return useQuery(
    computed(() => {
      const value = toValue(range)
      return {
        ...occurrencesQuery(value?.start ?? '', value?.end ?? '', value?.tz ?? ''),
        enabled: value !== null,
        placeholderData: keepPreviousData,
      }
    }),
  )
}

export function eventQuery(id: number) {
  return queryOptions({
    queryKey: ['event', id],
    queryFn: () =>
      call(() => api.GET('/api/v1/events/{event_id}', { params: { path: { event_id: id } } })),
  })
}

/** Anything that changes events makes every cached range stale; the visible one refetches at once. */
function eventsChanged(): Promise<void> {
  return queryClient.invalidateQueries({
    predicate: (q) => ['occurrences', 'event', 'tags'].includes(String(q.queryKey[0])),
  })
}

function calendarsChanged(): Promise<void> {
  return queryClient.invalidateQueries({
    predicate: (q) => ['calendars', 'occurrences'].includes(String(q.queryKey[0])),
  })
}

export const eventApi = {
  async create(body: EventCreate): Promise<EventDetail> {
    const created = await call(() => api.POST('/api/v1/events', { body }))
    await eventsChanged()
    return created
  },
  async update(id: number, body: EventUpdate): Promise<EventDetail> {
    const updated = await call(() =>
      api.PATCH('/api/v1/events/{event_id}', { params: { path: { event_id: id } }, body }),
    )
    await eventsChanged()
    return updated
  },
  async remove(id: number): Promise<void> {
    await call(() =>
      api.DELETE('/api/v1/events/{event_id}', { params: { path: { event_id: id } } }),
    )
    await eventsChanged()
  },
}

export const calendarApi = {
  async create(body: CalendarCreate): Promise<Calendar> {
    const created = await call(() => api.POST('/api/v1/calendars', { body }))
    await calendarsChanged()
    return created
  },
  async update(id: number, body: CalendarUpdate): Promise<Calendar> {
    const updated = await call(() =>
      api.PATCH('/api/v1/calendars/{calendar_id}', {
        params: { path: { calendar_id: id } },
        body,
      }),
    )
    await calendarsChanged()
    return updated
  },
  async remove(id: number): Promise<void> {
    await call(() =>
      api.DELETE('/api/v1/calendars/{calendar_id}', { params: { path: { calendar_id: id } } }),
    )
    await calendarsChanged()
  },
}

export const tagApi = {
  async update(id: number, body: TagUpdate): Promise<void> {
    await call(() => api.PATCH('/api/v1/tags/{tag_id}', { params: { path: { tag_id: id } }, body }))
    await eventsChanged()
  },
  async remove(id: number): Promise<void> {
    await call(() => api.DELETE('/api/v1/tags/{tag_id}', { params: { path: { tag_id: id } } }))
    await eventsChanged()
  },
}

/** Shows or hides a calendar at once; the server keeps it for the user's other devices (SPEC 7). */
export function useCalendarVisibility() {
  return useMutation({
    mutationFn: ({ id, visible }: { id: number; visible: boolean }) =>
      calendarApi.update(id, { is_visible: visible }),
    onMutate: ({ id, visible }) => {
      const previous = queryClient.getQueryData(calendarsQuery.queryKey)
      queryClient.setQueryData(calendarsQuery.queryKey, (list) =>
        list?.map((c) => (c.id === id ? { ...c, is_visible: visible } : c)),
      )
      return { previous }
    },
    onError: (_e, _v, context) => {
      if (context?.previous) queryClient.setQueryData(calendarsQuery.queryKey, context.previous)
    },
  })
}

/**
 * The current wall-clock time in the profile's zone. The server says what time it is there; the
 * browser only adds how much time has passed since (SPEC 5).
 */
export function useClock(tz: MaybeRefOrGetter<string | undefined>) {
  const query = useQuery(
    computed(() => ({
      queryKey: ['clock', toValue(tz)],
      queryFn: async () => ({
        ...(await call(() =>
          api.GET('/api/v1/me/clock', { params: { query: { tz: toValue(tz) } } }),
        )),
        fetchedAt: Date.now(),
      }),
      enabled: !!toValue(tz),
      staleTime: 60_000,
      refetchInterval: 5 * 60_000,
    })),
  )
  const tick = ref(Date.now())
  const timer = setInterval(() => (tick.value = Date.now()), 30_000)
  onScopeDispose(() => clearInterval(timer))

  return computed<PlainDateTime | null>(() => {
    const data = query.data.value
    if (!data) return null
    return parseDateTime(data.now).add({ milliseconds: Math.max(0, tick.value - data.fetchedAt) })
  })
}
