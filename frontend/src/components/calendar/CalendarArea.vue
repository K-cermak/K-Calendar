<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery } from '@tanstack/vue-query'
import { PopoverAnchor, PopoverContent, PopoverPortal, PopoverRoot } from 'reka-ui'
import { calendarsQuery, eventApi, eventQuery } from '@/api/calendar'
import type { EventDetail, Me, Occurrence, OccurrenceList } from '@/api/client'
import { queryClient } from '@/api/queryClient'
import { useSubmit } from '@/composables/useSubmit'
import type { PlainDate, PlainDateTime } from '@/dates'
import { draftFromEvent, draftFromSpan, toBody, type Draft } from '@/eventDraft'
import type { CalendarView } from '@/router'
import { useScopeStore } from '@/stores/scope'
import { useToastStore } from '@/stores/toast'
import AgendaList from './AgendaList.vue'
import CalendarGrid from './CalendarGrid.vue'
import EventDetailView from './EventDetail.vue'
import EventEditor from './EventEditor.vue'
import PhoneMonth from './PhoneMonth.vue'
import QuickCreate from './QuickCreate.vue'
import type { EditorTarget, GridChange, GridSpan } from './types'
import UiSheet from '@/components/ui/UiSheet.vue'

/** The calendar itself, with every way of creating, opening, moving and deleting events. */
const props = defineProps<{
  view: CalendarView
  anchor: PlainDate
  today: PlainDate | null
  now: PlainDateTime | null
  compact: boolean
  me: Me
  occurrences: Occurrence[]
  filter: (o: Occurrence) => boolean
  readOnly: boolean
  pendingOpen: Occurrence | null
}>()
const emit = defineEmits<{ select: [day: PlainDate]; opened: [] }>()

const { t } = useI18n()
const toast = useToastStore()
const scopes = useScopeStore()
const calendars = useQuery(calendarsQuery)
const grid = ref<{ unselect: () => void } | null>(null)
const action = useSubmit()

function defaultCalendarId(): number | null {
  const writable = (calendars.data.value ?? []).filter((c) => !c.read_only)
  return (writable.find((c) => c.is_visible) ?? writable[0])?.id ?? null
}

// Creating
const quickOpen = ref(false)
const quickDraft = ref<Draft | null>(null)
const quickAnchor = ref<DOMRect | null>(null)
const editorOpen = ref(false)
const editorTarget = ref<EditorTarget | null>(null)

function draftFor(span: GridSpan): Draft | null {
  const calendarId = defaultCalendarId()
  return calendarId === null ? null : draftFromSpan(span, calendarId, props.me.timezone)
}

function openEditor(target: EditorTarget): void {
  editorTarget.value = target
  editorOpen.value = true
}

function onSelect(span: GridSpan, element: HTMLElement | null): void {
  const draft = draftFor(span)
  if (!draft) return
  // The selection's own block is the best anchor; the element under the pointer is a whole lane.
  const mirror = document.querySelector('[data-testid="selection-mirror"]')
  quickAnchor.value = (mirror ?? element)?.getBoundingClientRect() ?? null
  quickDraft.value = draft
  quickOpen.value = true
}

function onDateClick(span: GridSpan): void {
  const draft = draftFor(span)
  if (draft) openEditor({ kind: 'create', draft })
}

/** The "new event" button: the next full hour today, or 9:00 on another day. */
function newEvent(): void {
  const day = props.anchor
  const now = props.now
  const start =
    now && props.today && day.equals(props.today) && now.hour < 23
      ? now.toPlainDate().toPlainDateTime({ hour: now.hour + 1 })
      : day.toPlainDateTime({ hour: 9 })
  const draft = draftFor({ start: start.toString(), end: '', allDay: false })
  if (draft) openEditor({ kind: 'create', draft })
}

function closedQuick(open: boolean): void {
  quickOpen.value = open
  if (!open) grid.value?.unselect()
}

// Opening
const detail = ref<Occurrence | null>(null)
const detailAnchor = ref<DOMRect | null>(null)
const detailOpen = ref(false)
const detailEvent = useQuery(
  computed(() => ({
    ...eventQuery(detail.value?.event_id ?? 0, detail.value?.occurrence ?? null),
    enabled: detailOpen.value && !!detail.value,
  })),
)

function openDetail(occurrence: Occurrence, element: HTMLElement): void {
  detail.value = occurrence
  detailAnchor.value = element.getBoundingClientRect()
  detailOpen.value = true
}

const detailReference = computed(() => {
  const rect = detailAnchor.value
  return rect ? { getBoundingClientRect: () => rect } : undefined
})

// Focus goes to the panel rather than its first button, so a click does not leave a focus ring
// on Edit; Tab still moves on to the buttons. The event comes from the positioning wrapper.
function focusPanel(event: Event): void {
  event.preventDefault()
  const panel = (event.target as HTMLElement).querySelector<HTMLElement>('[role="dialog"]')
  panel?.focus()
}

// The grid may have drawn the event anew while its details were open, so Reka's own return of
// focus would find the old element gone and drop focus on the page. A click elsewhere keeps its
// focus.
function returnFocus(event: Event): void {
  const active = document.activeElement
  if (active && active !== document.body && !(event.target as HTMLElement).contains(active)) return
  const block = detail.value
    ? document
        .querySelector(`[data-testid="event-${detail.value.id}"]`)
        ?.closest<HTMLElement>('[tabindex]')
    : null
  if (block) {
    event.preventDefault()
    block.focus()
  }
}

async function editFromDetail(): Promise<void> {
  if (!detail.value) return
  const event = await queryClient.fetchQuery(
    eventQuery(detail.value.event_id, detail.value.occurrence),
  )
  detailOpen.value = false
  openEditor({ kind: 'edit', event })
}

/**
 * Deleting, with undo: a single event is created again from what was saved before. Deleting from
 * a series changes its rule and exceptions, which cannot be restored that simply, so it has none.
 */
async function remove(event: EventDetail): Promise<void> {
  const scope = event.recurring && event.occurrence ? await scopes.ask('delete') : undefined
  if (scope === null) return
  const ok = await action.run(() =>
    eventApi.remove(event.id, { scope, occurrence: event.occurrence }),
  )
  if (!ok) {
    if (action.error.value) toast.show(action.error.value)
    return
  }
  if (event.recurring) {
    toast.show(t('event.deleted'))
    return
  }
  toast.show(t('event.deleted'), {
    label: t('common.undo'),
    run: () => eventApi.create(toBody(draftFromEvent(event, props.me.timezone))),
  })
}

async function deleteFromDetail(): Promise<void> {
  if (!detail.value) return
  const event = await queryClient.fetchQuery(
    eventQuery(detail.value.event_id, detail.value.occurrence),
  )
  detailOpen.value = false
  await remove(event)
}

// Moving and resizing: shown at once, put back with a message if the server refuses.
function patchCache(id: string, change: Partial<Occurrence>): void {
  queryClient.setQueriesData<OccurrenceList>({ queryKey: ['occurrences'] }, (list) =>
    list && 'items' in list
      ? { ...list, items: list.items.map((o) => (o.id === id ? { ...o, ...change } : o)) }
      : list,
  )
}

async function onChange(change: GridChange): Promise<void> {
  const { occurrence } = change
  const before = { start: occurrence.start, end: occurrence.end, all_day: occurrence.all_day }
  const after = { start: change.start, end: change.end, all_day: change.allDay }
  const scope = occurrence.recurring ? await scopes.ask('move') : undefined
  if (scope === null) {
    change.revert()
    return
  }
  patchCache(occurrence.id, after)
  const which = { scope, occurrence: occurrence.occurrence }
  const send = (span: typeof after) =>
    eventApi.update(occurrence.event_id, { ...span, input_timezone: props.me.timezone }, which)
  const ok = await action.run(() => send(after))
  if (!ok) {
    change.revert()
    patchCache(occurrence.id, before)
    toast.show(t('event.moveFailed', { reason: action.error.value ?? '' }))
    return
  }
  // Moving one occurrence back is the same kind of change; moving a whole series is not undone.
  if (scope && scope !== 'this') {
    toast.show(t('event.moved'))
    return
  }
  toast.show(t('event.moved'), { label: t('common.undo'), run: () => send(before) })
}

// Opens a linked occurrence once its day is on screen, at its block if the grid shows one.
watch(
  () => props.pendingOpen,
  async (occurrence) => {
    if (!occurrence) return
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 150))
    const element =
      document.querySelector<HTMLElement>(`[data-testid="event-${occurrence.id}"]`) ??
      document.querySelector<HTMLElement>(`[data-testid="agenda-${occurrence.id}"]`) ??
      document.querySelector<HTMLElement>('[data-testid="calendar-area"]')
    if (element) openDetail(occurrence, element)
    emit('opened')
  },
)

defineExpose({ newEvent })
</script>

<template>
  <CalendarGrid
    v-if="view !== 'agenda' && !(compact && view === 'month')"
    ref="grid"
    :view="view"
    :anchor="anchor.toString()"
    :compact="compact"
    :occurrences="occurrences"
    :now="now"
    :locale="me.locale"
    :week-start="me.week_start"
    :time-format="me.time_format"
    :show-tags="me.show_event_tags"
    :working-hours="me.working_hours_enabled ? me.working_hours : null"
    :read-only="readOnly"
    @select="onSelect"
    @date-click="onDateClick"
    @event-click="openDetail"
    @change="onChange"
  />
  <PhoneMonth
    v-else-if="view === 'month'"
    :selected="anchor"
    :today="today"
    :occurrences="occurrences"
    :week-start="me.week_start"
    :locale="me.locale"
    :time-format="me.time_format"
    :show-tags="me.show_event_tags"
    @select="emit('select', $event)"
    @open="openDetail"
  />
  <AgendaList
    v-else
    :anchor="anchor"
    :today="today"
    :tz="me.timezone"
    :locale="me.locale"
    :time-format="me.time_format"
    :show-tags="me.show_event_tags"
    :filter="filter"
    @open="openDetail"
  />

  <QuickCreate
    :open="quickOpen"
    :draft="quickDraft"
    :anchor="quickAnchor"
    @update:open="closedQuick"
    @more="(draft) => openEditor({ kind: 'create', draft })"
  />
  <EventEditor v-model:open="editorOpen" :target="editorTarget" @delete="remove" />

  <UiSheet
    v-if="compact"
    v-model:open="detailOpen"
    :title="detail?.title || $t('event.noTitle')"
    hide-title
  >
    <EventDetailView
      v-if="detail"
      :occurrence="detail"
      :description="detailEvent.data.value?.description ?? null"
      :read-only="readOnly"
      @edit="editFromDetail"
      @delete="deleteFromDetail"
      @close="detailOpen = false"
    />
  </UiSheet>
  <PopoverRoot v-else v-model:open="detailOpen">
    <PopoverAnchor :reference="detailReference" />
    <PopoverPortal>
      <PopoverContent
        class="ui-panel w-[360px] p-4 outline-none"
        side="right"
        align="start"
        :side-offset="8"
        :collision-padding="12"
        @open-auto-focus="focusPanel"
        @close-auto-focus="returnFocus"
      >
        <EventDetailView
          v-if="detail"
          :occurrence="detail"
          :description="detailEvent.data.value?.description ?? null"
          :read-only="readOnly"
          @edit="editFromDetail"
          @delete="deleteFromDetail"
          @close="detailOpen = false"
        />
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
