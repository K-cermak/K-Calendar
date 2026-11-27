<script setup lang="ts">
import type { EventTagStyle, Occurrence } from '@/api/client'
import { formatTime, parseDateTime } from '@/dates'
import { colorVar } from '@/palette'
import EventTags from './EventTags.vue'

/** One day's events as rows: colour, time in mono, title, tag markers (SPEC 11). */
const props = defineProps<{
  items: Occurrence[]
  locale: string
  timeFormat: '12' | '24'
  tagStyle: EventTagStyle
}>()
const emit = defineEmits<{ open: [occurrence: Occurrence, el: HTMLElement] }>()

function timeLabel(o: Occurrence): string {
  const format = (v: string) => formatTime(parseDateTime(v), props.locale, props.timeFormat)
  return `${format(o.start)} – ${format(o.end)}`
}
</script>

<template>
  <ul class="flex min-w-0 flex-col gap-0.5">
    <li v-if="!items.length" class="px-2 py-1.5 text-muted">{{ $t('agenda.nothing') }}</li>
    <li v-for="item in items" :key="item.id">
      <button
        type="button"
        class="flex w-full cursor-pointer items-start gap-3 px-2 py-1.5 text-left hover:bg-hover-tint pointer-coarse:min-h-11 pointer-coarse:items-center"
        :data-testid="`agenda-${item.id}`"
        @click="emit('open', item, $event.currentTarget as HTMLElement)"
      >
        <span
          class="mt-1 h-3.5 w-0.5 shrink-0 pointer-coarse:mt-0"
          :style="{ background: colorVar(item.color) }"
          aria-hidden="true"
        />
        <span class="ui-numeric w-28 shrink-0 font-mono text-label text-muted">
          {{ item.all_day ? $t('event.allDay') : timeLabel(item) }}
        </span>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="truncate">{{ item.title || $t('event.noTitle') }}</span>
          <!-- Names go under the title: beside it they would squeeze it out on a phone. -->
          <EventTags v-if="tagStyle === 'names'" :tags="item.tags" mode="names" class="mt-0.5" />
        </span>
        <EventTags
          v-if="tagStyle === 'markers'"
          :tags="item.tags"
          mode="markers"
          class="mt-1.5 shrink-0 pointer-coarse:mt-0"
        />
      </button>
    </li>
  </ul>
</template>
