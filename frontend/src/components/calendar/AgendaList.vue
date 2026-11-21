<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useInfiniteQuery } from '@tanstack/vue-query'
import { api, call, type Occurrence } from '@/api/client'
import { formatDate, parseDate, type PlainDate } from '@/dates'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import AgendaDay from './AgendaDay.vue'
import { groupByDay } from './groupByDay'

/** Agenda: days with events from the anchor on, loading further as the list scrolls (SPEC 11). */
const props = defineProps<{
  anchor: PlainDate
  today: PlainDate | null
  tz: string
  locale: string
  timeFormat: '12' | '24'
  filter: (o: Occurrence) => boolean
}>()
const emit = defineEmits<{ open: [occurrence: Occurrence, el: HTMLElement] }>()

const PAGE_DAYS = 30

const pages = useInfiniteQuery({
  queryKey: computed(() => ['occurrences', props.tz, 'agenda', props.anchor.toString()]),
  initialPageParam: 0,
  queryFn: async ({ pageParam }) => {
    const from = props.anchor.add({ days: pageParam * PAGE_DAYS })
    const to = from.add({ days: PAGE_DAYS })
    const result = await call(() =>
      api.GET('/api/v1/occurrences', {
        params: { query: { start: from.toString(), end: to.toString(), tz: props.tz } },
      }),
    )
    return { from, to, items: result.items }
  },
  getNextPageParam: (_last, all) => (all.length < 12 ? all.length : undefined),
})

const groups = computed(() =>
  (pages.data.value?.pages ?? []).flatMap((page) =>
    groupByDay(page.items.filter(props.filter), page.from, page.to),
  ),
)

const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    if (
      entries.some((e) => e.isIntersecting) &&
      pages.hasNextPage.value &&
      !pages.isFetching.value
    ) {
      void pages.fetchNextPage()
    }
  })
  if (sentinel.value) observer.observe(sentinel.value)
})
onUnmounted(() => observer?.disconnect())

// An observer reports only changes. After a page with few or no events the end of the list is
// still in view, so observing it afresh asks for the next page, until the list fills the screen
// or the year has been searched.
watch(
  () => pages.data.value?.pages.length,
  () => {
    if (!observer || !sentinel.value) return
    observer.unobserve(sentinel.value)
    observer.observe(sentinel.value)
  },
  { flush: 'post' },
)

function dayLabel(day: string): string {
  return formatDate(parseDate(day), props.locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}
</script>

<template>
  <div class="h-full overflow-y-auto" data-testid="agenda">
    <p
      v-if="pages.isSuccess.value && !groups.length && !pages.hasNextPage.value"
      class="p-8 text-center text-muted"
    >
      {{ $t('agenda.empty') }}
    </p>
    <section
      v-for="group in groups"
      :key="group.day"
      class="flex border-b border-line px-4 py-3 sm:px-6"
    >
      <h2
        class="ui-numeric w-24 shrink-0 pt-1 font-mono text-label text-muted sm:w-32"
        :class="today && group.day === today.toString() && 'text-accent!'"
      >
        {{ dayLabel(group.day) }}
      </h2>
      <AgendaDay
        :items="group.items"
        :locale="locale"
        :time-format="timeFormat"
        class="flex-1"
        @open="(o, el) => emit('open', o, el)"
      />
    </section>
    <!-- Tall enough that the last day scrolls clear of the round button on a phone. -->
    <div ref="sentinel" class="flex h-24 justify-center pt-6 text-muted">
      <UiSpinner v-if="pages.isFetching.value" />
      <span v-if="pages.isFetching.value" class="sr-only">{{ $t('common.loading') }}</span>
    </div>
  </div>
</template>
