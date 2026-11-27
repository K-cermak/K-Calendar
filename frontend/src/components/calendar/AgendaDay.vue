<script setup lang="ts">
import type { Occurrence } from '@/api/client'
import { formatTime, parseDateTime } from '@/dates'
import { colorVar } from '@/palette'

/** One day's events as rows: colour, time in mono, title, tag markers (SPEC 11). */
const props = defineProps<{
  items: Occurrence[]
  locale: string
  timeFormat: '12' | '24'
  showTags: boolean
}>()
const emit = defineEmits<{ open: [occurrence: Occurrence, el: HTMLElement] }>()

const MAX_TAGS = 3

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
        <span class="min-w-0 flex-1 truncate">{{ item.title || $t('event.noTitle') }}</span>
        <span
          v-if="showTags && item.tags.length"
          class="mt-1.5 flex shrink-0 gap-1"
          aria-hidden="true"
        >
          <span
            v-for="tag in item.tags.slice(0, MAX_TAGS)"
            :key="tag.id"
            class="cal-tag-marker"
            :style="{ '--tag-color': colorVar(tag.color) }"
          />
          <span v-if="item.tags.length > MAX_TAGS" class="font-mono text-meta text-muted">
            +{{ item.tags.length - MAX_TAGS }}
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>
