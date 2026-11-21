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
  type ImportResult,
  type SubscriptionCreate,
  type TagUpdate,
} from './client'
import { queryClient } from './queryClient'
import type { Scope } from '@/stores/scope'

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

export function occurrenceQuery(id: string, tz: string) {
  return queryOptions({
    queryKey: ['occurrence', id, tz],
    queryFn: () =>
      call(() =>
        api.GET('/api/v1/occurrences/{occurrence_id}', {
          params: { path: { occurrence_id: id }, query: { tz } },
        }),
      ),
  })
}

export function eventQuery(id: number, occurrence: string | null = null) {
  return queryOptions({
    queryKey: ['event', id, occurrence],
    queryFn: () =>
      call(() =>
        api.GET('/api/v1/events/{event_id}', {
          params: { path: { event_id: id }, query: occurrence ? { occurrence } : {} },
        }),
      ),
  })
}

/** Which occurrences of a series a change applies to; left out for single events. */
export interface Which {
  scope?: Scope
  occurrence?: string | null
}

function whichQuery(which: Which): { scope?: Scope; occurrence?: string } {
  return which.scope && which.occurrence ? { scope: which.scope, occurrence: which.occurrence } : {}
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
  async update(id: number, body: EventUpdate, which: Which = {}): Promise<EventDetail> {
    const updated = await call(() =>
      api.PATCH('/api/v1/events/{event_id}', {
        params: { path: { event_id: id }, query: whichQuery(which) },
        body,
      }),
    )
    await eventsChanged()
    return updated
  },
  async remove(id: number, which: Which = {}): Promise<void> {
    await call(() =>
      api.DELETE('/api/v1/events/{event_id}', {
        params: { path: { event_id: id }, query: whichQuery(which) },
      }),
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
  async subscribe(body: SubscriptionCreate): Promise<Calendar> {
    const created = await call(() => api.POST('/api/v1/calendars/subscriptions', { body }))
    await calendarsChanged()
    return created
  },
  async refresh(id: number): Promise<Calendar> {
    const refreshed = await call(() =>
      api.POST('/api/v1/calendars/{calendar_id}/refresh', {
        params: { path: { calendar_id: id } },
      }),
    )
    await calendarsChanged()
    return refreshed
  },
  async setFeed(id: number): Promise<Calendar> {
    const updated = await call(() =>
      api.PUT('/api/v1/calendars/{calendar_id}/feed', { params: { path: { calendar_id: id } } }),
    )
    await calendarsChanged()
    return updated
  },
  async removeFeed(id: number): Promise<void> {
    await call(() =>
      api.DELETE('/api/v1/calendars/{calendar_id}/feed', {
        params: { path: { calendar_id: id } },
      }),
    )
    await calendarsChanged()
  },
  async importFile(id: number, file: File): Promise<ImportResult> {
    const result = await call(() =>
      api.POST('/api/v1/calendars/{calendar_id}/import', {
        params: { path: { calendar_id: id } },
        // The generated type says string, as OpenAPI describes a binary upload; the browser sends the File.
        body: { file: file as unknown as string },
        bodySerializer: (body) => {
          const form = new FormData()
          form.append('file', body.file as unknown as Blob)
          return form
        },
      }),
    )
    await eventsChanged()
    return result
  },
  exportUrl: (id: number): string => `/api/v1/calendars/${id}/export`,
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
