<script setup lang="ts">
import { computed } from 'vue'
import type { Occurrence } from '@/api/client'
import { formatDate, type PlainDate, type WeekStart } from '@/dates'
import { groupByDay } from './groupByDay'
import AgendaDay from './AgendaDay.vue'
import MonthGrid from './MonthGrid.vue'

/** The phone's month: dots in the cells, and the selected day's events underneath (SPEC 11). */
const props = defineProps<{
  selected: PlainDate
  today: PlainDate | null
  occurrences: Occurrence[]
  weekStart: WeekStart
  locale: string
  timeFormat: '12' | '24'
}>()
const emit = defineEmits<{ select: [day: PlainDate]; open: [o: Occurrence, el: HTMLElement] }>()

const groups = computed(() => {
  const first = props.selected.with({ day: 1 }).subtract({ days: 7 })
  return groupByDay(props.occurrences, first, first.add({ days: 50 }))
})
const dots = computed(() => new Map(groups.value.map((g) => [g.day, g.items.map((i) => i.color)])))
const selectedItems = computed(
  () => groups.value.find((g) => g.day === props.selected.toString())?.items ?? [],
)
</script>

<template>
  <div class="flex h-full flex-col overflow-y-auto">
    <div class="border-b border-line p-3">
      <MonthGrid
        :selected="selected"
        :today="today"
        :week-start="weekStart"
        :locale="locale"
        :dots="dots"
        large
        @select="emit('select', $event)"
        @month="emit('select', $event)"
      />
    </div>
    <h2 class="px-4 pt-3 pb-1 font-mono text-label text-muted">
      {{ formatDate(selected, locale, { weekday: 'long', day: 'numeric', month: 'long' }) }}
    </h2>
    <AgendaDay
      :items="selectedItems"
      :locale="locale"
      :time-format="timeFormat"
      class="px-2 pb-24"
      @open="(o, el) => emit('open', o, el)"
    />
  </div>
</template>
