<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import type {
  CalendarOptions,
  DateClickInfo,
  DateSelectInfo,
  EventChangeInfo,
  EventClickInfo,
  EventInput,
} from '@fullcalendar/vue3'
import '@fullcalendar/vue3/skeleton.css'
import type { Occurrence, WorkingHours } from '@/api/client'
import { PHONE_WEEK_DAYS, type PlainDateTime, type WeekStart } from '@/dates'
import { toBusinessHours } from '@/workingHours'
import EventBlock from './EventBlock.vue'
import type { GridChange, GridSpan } from './types'
import { calendarTheme } from './theme'

const props = defineProps<{
  view: 'month' | 'week' | 'day'
  anchor: string
  compact: boolean
  occurrences: Occurrence[]
  now: PlainDateTime | null
  locale: string
  weekStart: WeekStart
  timeFormat: '12' | '24'
  showTags: boolean
  workingHours: WorkingHours | null
  readOnly: boolean
}>()

const emit = defineEmits<{
  select: [span: GridSpan, anchor: HTMLElement | null]
  dateClick: [span: GridSpan]
  eventClick: [occurrence: Occurrence, anchor: HTMLElement]
  change: [change: GridChange]
}>()

const calendar = ref<InstanceType<typeof FullCalendar> | null>(null)

/*
 * The grid runs in UTC and gets wall-clock strings, so it does no time zone arithmetic of its own:
 * what it shows and what it hands back after a drag are plain wall-clock values in the display
 * zone, and the server converts them (SPEC 5).
 */
/**
 * Opens the grid an hour before `hour`. A quarter of an hour more stays above it, because each
 * hour's label sits on its line and would otherwise be cut in half at the top edge.
 */
function scrollTime(hour: number): string {
  const first = Math.max(0, hour - 1)
  return first === 0 ? '00:00:00' : `${String(first - 1).padStart(2, '0')}:45:00`
}

function wallClock(date: Date | null, allDay: boolean): string {
  const iso = (date ?? new Date(0)).toISOString()
  return allDay ? iso.slice(0, 10) : iso.slice(0, 19)
}

const fcView = computed(() => {
  if (props.view === 'month') return 'dayGridMonth'
  if (props.view === 'day') return 'timeGridDay'
  return props.compact ? 'timeGridThreeDay' : 'timeGridWeek'
})

const events = computed<EventInput[]>(() =>
  props.occurrences.map((o) => ({
    id: o.id,
    title: o.title,
    start: o.start,
    end: o.end,
    allDay: o.all_day,
    editable: !o.read_only && !props.readOnly,
    extendedProps: { occurrence: o },
  })),
)

const hourCycle = computed(() => (props.timeFormat === '12' ? 'h12' : 'h23'))

function occurrenceOf(event: { extendedProps: Record<string, unknown> }): Occurrence {
  return event.extendedProps.occurrence as Occurrence
}

const options = computed<CalendarOptions>(() => ({
  plugins: [calendarTheme, dayGridPlugin, timeGridPlugin, interactionPlugin],
  timeZone: 'UTC',
  initialView: fcView.value,
  initialDate: props.anchor,
  headerToolbar: false,
  height: '100%',
  locale: props.locale,
  firstDay: props.weekStart === 'monday' ? 1 : 0,
  now: () => (props.now ? props.now.toString() : new Date()),
  nowIndicator: true,
  // Only the time grid: the month view would shade whole days off, which reads as unavailable.
  businessHours:
    props.workingHours && props.view !== 'month' ? toBusinessHours(props.workingHours) : false,
  scrollTime: scrollTime(props.now?.hour ?? 9),
  views: { timeGridThreeDay: { type: 'timeGrid', duration: { days: PHONE_WEEK_DAYS } } },
  editable: !props.readOnly,
  selectable: !props.readOnly && !props.compact,
  selectMirror: true,
  dayMaxEvents: true,
  dayHeaderFormat: props.view === 'month' ? { weekday: 'short' } : undefined,
  eventLongPressDelay: 400,
  selectLongPressDelay: 400,
  eventTimeFormat: { hour: 'numeric', minute: '2-digit', hourCycle: hourCycle.value },
  slotHeaderFormat: { hour: 'numeric', minute: '2-digit', hourCycle: hourCycle.value },
  events: events.value,
  select: (info: DateSelectInfo) => {
    emit(
      'select',
      {
        start: wallClock(info.start, info.allDay),
        end: wallClock(info.end, info.allDay),
        allDay: info.allDay,
      },
      (info.jsEvent?.target as HTMLElement | null) ?? null,
    )
  },
  dateClick: (info: DateClickInfo) => {
    if (!props.compact || props.readOnly) return
    emit('dateClick', { start: wallClock(info.date, info.allDay), end: '', allDay: info.allDay })
  },
  eventClick: (info: EventClickInfo) => {
    info.jsEvent.preventDefault()
    emit('eventClick', occurrenceOf(info.event), info.el)
  },
  eventChange: (info: EventChangeInfo) => {
    const { event } = info
    emit('change', {
      occurrence: occurrenceOf(event),
      start: wallClock(event.start, event.allDay),
      // An event dropped from the all-day strip into the grid has no end yet: one hour then.
      end: event.end
        ? wallClock(event.end, event.allDay)
        : wallClock(
            new Date((event.start?.getTime() ?? 0) + (event.allDay ? 86_400_000 : 3_600_000)),
            event.allDay,
          ),
      allDay: event.allDay,
      revert: info.revert,
    })
  },
}))

watch(
  () => [fcView.value, props.anchor] as const,
  ([view, anchor]) => {
    const api = calendar.value?.getApi()
    if (!api) return
    if (api.view.type !== view) api.changeView(view, anchor)
    else api.gotoDate(anchor)
  },
)

function weekday(date: Date): string {
  return new Intl.DateTimeFormat(props.locale, { weekday: 'short', timeZone: 'UTC' }).format(date)
}

defineExpose({ unselect: () => calendar.value?.getApi().unselect() })
</script>

<template>
  <FullCalendar ref="calendar" :options="options" class="cal-grid">
    <template #dayHeaderContent="arg">
      <template v-if="view === 'month' || arg.inPopover">{{ arg.text }}</template>
      <template v-else>
        <span>{{ weekday(arg.date) }}</span>
        <span class="cal-fc-day-number" :class="arg.isToday && 'is-today'">{{
          arg.date.getUTCDate()
        }}</span>
      </template>
    </template>
    <template #eventContent="arg">
      <div
        v-if="!arg.event.extendedProps.occurrence"
        class="cal-event cal-event--selection h-full"
        data-testid="selection-mirror"
      >
        <span class="cal-event__time">{{ arg.timeText }}</span>
      </div>
      <EventBlock
        v-else
        :occurrence="occurrenceOf(arg.event)"
        :view="view"
        :locale="locale"
        :time-format="timeFormat"
        :show-tags="showTags"
        :now="now"
        :mirror="arg.isMirror"
      />
    </template>
  </FullCalendar>
</template>
