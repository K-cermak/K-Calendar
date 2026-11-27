<script setup lang="ts">
import { computed } from 'vue'
import type { EventTagStyle, Occurrence } from '@/api/client'
import { formatTime, parseDateTime, type PlainDateTime } from '@/dates'
import { colorVar } from '@/palette'
import { useI18n } from 'vue-i18n'
import EventTags from './EventTags.vue'

/** An event in the grid: a tint of its colour with a bar on the left (SPEC 11). */
const props = defineProps<{
  occurrence: Occurrence
  view: string
  now: PlainDateTime | null
  locale: string
  timeFormat: '12' | '24'
  tagStyle: EventTagStyle
  mirror?: boolean
}>()
const { t } = useI18n()

const past = computed(
  () =>
    !!props.now &&
    props.occurrence.end <= props.now.toString().slice(0, props.occurrence.end.length),
)
const title = computed(() => props.occurrence.title || t('event.noTitle'))
// Formatted here from the wall-clock values: the grid leaves the time out of short events.
const timeText = computed(() => {
  if (props.occurrence.all_day) return ''
  const format = (v: string) => formatTime(parseDateTime(v), props.locale, props.timeFormat)
  return props.view === 'month'
    ? format(props.occurrence.start)
    : `${format(props.occurrence.start)} – ${format(props.occurrence.end)}`
})
</script>

<template>
  <div
    class="cal-event h-full"
    :class="[
      past && !mirror && 'cal-event--past',
      !occurrence.all_day && view !== 'month' && 'cal-event--block',
    ]"
    :style="{ '--event-color': colorVar(occurrence.color) }"
    :data-testid="`event-${occurrence.id}`"
  >
    <span class="cal-event__body" :class="view === 'month' && 'cal-event__body--inline'">
      <span v-if="timeText && view === 'month'" class="cal-event__time">{{ timeText }}</span>
      <span class="cal-event__title">{{ title }}</span>
      <span v-if="timeText && view !== 'month'" class="cal-event__time">{{ timeText }}</span>
    </span>
    <!-- The month view is too dense for tags (SPEC 7). -->
    <EventTags
      v-if="tagStyle !== 'hidden' && view !== 'month'"
      :tags="occurrence.tags"
      :mode="tagStyle"
      class="mt-0.5"
    />
  </div>
</template>
