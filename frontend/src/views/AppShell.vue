<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Plus } from '@lucide/vue'
import {
  calendarsQuery,
  occurrenceQuery,
  occurrencesQuery,
  useClock,
  useOccurrences,
} from '@/api/calendar'
import { queryClient } from '@/api/queryClient'
import type { Occurrence } from '@/api/client'
import { useMe } from '@/api/session'
import { useCalendarNav } from '@/composables/useCalendarNav'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { useOnline } from '@/composables/useOnline'
import { useSwipe } from '@/composables/useSwipe'
import { parseDate, rangeTitle, visibleRange, type PlainDate } from '@/dates'
import type { CalendarView } from '@/router'
import { useUiStore } from '@/stores/ui'
import CalendarArea from '@/components/calendar/CalendarArea.vue'
import ZoneBanner from '@/components/calendar/ZoneBanner.vue'
import PhoneDrawer from '@/components/shell/PhoneDrawer.vue'
import SidebarContent from '@/components/shell/SidebarContent.vue'
import TopBar from '@/components/shell/TopBar.vue'

const route = useRoute()
const router = useRouter()
const me = useMe()
const ui = useUiStore()
const compact = useMediaQuery('(max-width: 767px)')
const now = useClock(() => me.value?.timezone)
const calendars = useQuery(calendarsQuery)
const area = ref<{ newEvent: () => void } | null>(null)
const main = ref<HTMLElement | null>(null)

/** The user's default: week on a wide screen and agenda on a phone, unless they chose one. */
const defaultView = computed<CalendarView>(() => {
  const chosen = me.value?.default_view
  if (chosen && chosen !== 'auto') return chosen
  return compact.value ? 'agenda' : 'week'
})

const nav = useCalendarNav(defaultView, now, compact)
const online = useOnline()
const readOnly = computed(() => !online.value)

/*
 * While online, a month back and three ahead are loaded quietly, so that offline there is more
 * to read than the last screen (SPEC 12). The service worker cuts any view's range out of it.
 */
const PREFETCH_EVERY_MS = 30 * 60_000
let lastPrefetch = 0
watch(
  () => [online.value, nav.today.value?.toString(), me.value?.timezone] as const,
  ([isOnline, today, tz]) => {
    if (!isOnline || !today || !tz || Date.now() - lastPrefetch < PREFETCH_EVERY_MS) return
    lastPrefetch = Date.now()
    const day = parseDate(today)
    const start = day.subtract({ months: 1 }).toString()
    const end = day.add({ months: 3 }).toString()
    void queryClient.prefetchQuery(occurrencesQuery(start, end, tz)).catch(() => undefined)
  },
  { immediate: true },
)

// /event/:occurrenceId (a search result or a notification): go to its day and open it there.
const pendingOpen = ref<Occurrence | null>(null)
const linked = useQuery(
  computed(() => ({
    ...occurrenceQuery(String(route.params.occurrenceId ?? ''), me.value?.timezone ?? 'UTC'),
    enabled: route.name === 'event' && !!me.value,
    retry: false,
  })),
)
watch(
  () => [linked.data.value, linked.error.value] as const,
  ([occurrence, error]) => {
    if (route.name !== 'event') return
    if (occurrence) {
      pendingOpen.value = occurrence
      nav.goTo(parseDate(occurrence.start), nav.view.value, true)
    } else if (error) {
      void router.replace({ name: 'calendar', params: { view: defaultView.value } })
    }
  },
)

watch(
  () => route.name,
  (name) => {
    if (name === 'home') {
      void router.replace({ name: 'calendar', params: { view: defaultView.value } })
    }
  },
  { immediate: true },
)

const range = computed(() => {
  if (!nav.anchor.value || !me.value || nav.view.value === 'agenda') return null
  const { start, end } = visibleRange(
    nav.view.value,
    nav.anchor.value,
    me.value.week_start,
    compact.value,
  )
  return { start: start.toString(), end: end.toString(), tz: me.value.timezone }
})
const occurrences = useOccurrences(range)
// The agenda loads its own pages and shows its own progress.
const rangeLoading = computed(
  () =>
    range.value !== null &&
    (occurrences.isPending.value || occurrences.isPlaceholderData.value) &&
    occurrences.isFetching.value,
)

// Hidden calendars are left out by the server too; filtering here as well makes a toggle instant.
const hidden = computed(
  () => new Set((calendars.data.value ?? []).filter((c) => !c.is_visible).map((c) => c.id)),
)
function shows(o: Occurrence): boolean {
  const filter = ui.tagFilter
  return (
    !hidden.value.has(o.calendar_id) &&
    (!filter.length || o.tags.some((t) => filter.includes(t.id)))
  )
}
const visibleOccurrences = computed(() => (occurrences.data.value?.items ?? []).filter(shows))

const title = computed(() =>
  nav.anchor.value && me.value
    ? rangeTitle(
        nav.view.value,
        nav.anchor.value,
        me.value.locale,
        me.value.week_start,
        compact.value,
      )
    : '',
)

function toggleMenu(): void {
  if (compact.value) ui.drawerOpen = true
  else ui.sidebarOpen = !ui.sidebarOpen
}

function selectDay(day: PlainDate): void {
  ui.drawerOpen = false
  const view = nav.view.value === 'agenda' || nav.view.value === 'month' ? nav.view.value : 'day'
  nav.goTo(day, compact.value ? view : nav.view.value === 'month' ? 'month' : nav.view.value)
}

function newEvent(): void {
  ui.drawerOpen = false
  area.value?.newEvent()
}

useSwipe(main, (direction) => {
  if (compact.value && nav.view.value !== 'agenda') nav.step(direction)
})
</script>

<template>
  <div class="flex h-full flex-col">
    <TopBar
      :view="nav.view.value"
      :compact="compact"
      :title="title"
      :loading="rangeLoading"
      @update:view="nav.setView"
      @menu="toggleMenu"
      @today="nav.goToday"
      @previous="nav.step(-1)"
      @next="nav.step(1)"
    />
    <ZoneBanner />
    <div class="flex min-h-0 flex-1">
      <aside
        v-if="!compact && ui.sidebarOpen && me"
        class="w-64 shrink-0 overflow-y-auto border-r border-line"
        data-testid="sidebar"
      >
        <SidebarContent
          :selected="nav.anchor.value"
          :today="nav.today.value"
          :week-start="me.week_start"
          :locale="me.locale"
          :read-only="readOnly"
          show-mini-month
          @select="selectDay"
          @new-event="newEvent"
        />
      </aside>
      <main
        ref="main"
        class="relative flex min-w-0 flex-1 flex-col overflow-hidden"
        data-testid="calendar-area"
        :aria-busy="rangeLoading"
      >
        <CalendarArea
          v-if="me && nav.anchor.value"
          ref="area"
          :view="nav.view.value"
          :anchor="nav.anchor.value"
          :today="nav.today.value"
          :now="now"
          :compact="compact"
          :me="me"
          :occurrences="visibleOccurrences"
          :filter="shows"
          :read-only="readOnly"
          :pending-open="pendingOpen"
          @select="(day) => nav.goTo(day)"
          @opened="pendingOpen = null"
        />
      </main>
    </div>
    <PhoneDrawer v-if="compact && me" v-model:open="ui.drawerOpen">
      <div class="flex flex-col">
        <div
          class="ui-segmented mx-4 mt-4 flex! self-stretch!"
          role="radiogroup"
          :aria-label="$t('views.label')"
        >
          <button
            v-for="view in ['agenda', 'day', 'week', 'month'] as const"
            :key="view"
            type="button"
            role="radio"
            class="ui-segmented__option flex-1"
            :aria-checked="nav.view.value === view"
            @click="((ui.drawerOpen = false), nav.setView(view))"
          >
            {{ $t(`views.${view}`) }}
          </button>
        </div>
        <SidebarContent
          :selected="nav.anchor.value"
          :today="nav.today.value"
          :week-start="me.week_start"
          :locale="me.locale"
          :read-only="readOnly"
          :show-mini-month="false"
          @select="selectDay"
          @new-event="newEvent"
        />
      </div>
    </PhoneDrawer>
    <button
      v-if="compact && !readOnly"
      type="button"
      class="ui-button ui-button--primary ui-button--icon fixed right-4 bottom-[max(16px,env(safe-area-inset-bottom))] z-20 size-14!"
      :aria-label="$t('shell.newEvent')"
      data-testid="fab"
      @click="newEvent"
    >
      <Plus :size="24" />
    </button>
  </div>
</template>
