<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { formatDate, startOfWeek, type PlainDate, type WeekStart } from '@/dates'
import { colorVar } from '@/palette'

/**
 * A month of day numbers: the sidebar's mini month, and the phone's month view with coloured dots
 * for the events of each day (SPEC 11).
 */
const props = defineProps<{
  selected: PlainDate
  today: PlainDate | null
  weekStart: WeekStart
  locale: string
  dots?: Map<string, string[]>
  large?: boolean
}>()
const emit = defineEmits<{ select: [day: PlainDate]; month: [first: PlainDate] }>()

const shown = ref(props.selected.with({ day: 1 }))
watch(
  () => props.selected.toString(),
  () => (shown.value = props.selected.with({ day: 1 })),
)

const weeks = computed(() => {
  const start = startOfWeek(shown.value, props.weekStart)
  return Array.from({ length: 6 }, (_, w) =>
    Array.from({ length: 7 }, (_, d) => start.add({ days: w * 7 + d })),
  )
})
const weekdays = computed(() =>
  weeks.value[0]!.map((day) => formatDate(day, props.locale, { weekday: 'narrow' })),
)
const title = computed(() =>
  formatDate(shown.value, props.locale, { month: 'long', year: 'numeric' }),
)

function move(step: -1 | 1): void {
  shown.value = shown.value.add({ months: step })
  emit('month', shown.value)
}

const MAX_DOTS = 3
</script>

<template>
  <div class="flex flex-col gap-2" :data-testid="large ? 'month-dots' : 'mini-month'">
    <div class="flex items-center justify-between">
      <span class="font-medium">{{ title }}</span>
      <div class="flex">
        <button
          type="button"
          class="ui-icon-button size-8!"
          :aria-label="$t('shell.previousMonth')"
          @click="move(-1)"
        >
          <ChevronLeft :size="16" />
        </button>
        <button
          type="button"
          class="ui-icon-button size-8!"
          :aria-label="$t('shell.nextMonth')"
          @click="move(1)"
        >
          <ChevronRight :size="16" />
        </button>
      </div>
    </div>
    <table class="w-full table-fixed border-collapse text-center">
      <thead>
        <tr>
          <th
            v-for="(name, i) in weekdays"
            :key="i"
            class="pb-1 text-meta font-normal text-faint"
            scope="col"
          >
            {{ name }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(week, w) in weeks" :key="w">
          <td v-for="day in week" :key="day.toString()" class="p-0">
            <button
              type="button"
              class="mx-auto flex w-full cursor-pointer flex-col items-center gap-0.5 hover:bg-hover-tint"
              :class="large ? 'h-12 pt-1.5' : 'h-8 justify-center'"
              :aria-label="
                formatDate(day, locale, { day: 'numeric', month: 'long', year: 'numeric' })
              "
              :aria-current="today && day.equals(today) ? 'date' : undefined"
              :aria-pressed="day.equals(selected)"
              @click="emit('select', day)"
            >
              <span
                class="ui-numeric inline-grid h-6 min-w-6 place-items-center px-1 font-mono text-meta"
                :class="[
                  today && day.equals(today)
                    ? 'cal-today-mark'
                    : day.equals(selected)
                      ? 'bg-ink text-bg'
                      : day.month === shown.month
                        ? 'text-ink'
                        : 'text-faint',
                ]"
              >
                {{ day.day }}
              </span>
              <span v-if="dots" class="flex h-1.5 gap-0.5" aria-hidden="true">
                <span
                  v-for="(color, i) in (dots.get(day.toString()) ?? []).slice(0, MAX_DOTS)"
                  :key="i"
                  class="size-1.5"
                  :style="{ background: colorVar(color) }"
                />
              </span>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
