<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { Search, X } from '@lucide/vue'
import { api, call } from '@/api/client'
import { useMe } from '@/api/session'
import { colorVar } from '@/palette'
import { describeSpan } from '@/text'

/**
 * Search in the top bar, with results as the user types (SPEC 9, 11). On a phone it is an icon
 * that opens the field over the bar.
 */
const props = defineProps<{ compact: boolean }>()

const router = useRouter()
const me = useMe()
const text = ref('')
const query = ref('')
const open = ref(false)
const expanded = ref(false)
const active = ref(0)
const input = ref<HTMLInputElement | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null
watch(text, (value) => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => (query.value = value.trim()), 200)
  open.value = true
  active.value = 0
})

const results = useQuery(
  computed(() => ({
    queryKey: ['search', query.value, me.value?.timezone],
    queryFn: () =>
      call(() =>
        api.GET('/api/v1/search', {
          params: { query: { q: query.value, tz: me.value?.timezone } },
        }),
      ),
    enabled: query.value.length > 0 && !!me.value,
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  })),
)
const items = computed(() => (query.value ? (results.data.value ?? []) : []))

function when(item: (typeof items.value)[number]): string {
  return me.value ? describeSpan(item, me.value.locale, me.value.time_format) : ''
}

function choose(index: number): void {
  const item = items.value[index]
  if (!item) return
  close()
  void router.push({ name: 'event', params: { occurrenceId: item.occurrence_id } })
}

function close(): void {
  open.value = false
  expanded.value = false
  text.value = ''
  query.value = ''
}

async function expand(): Promise<void> {
  expanded.value = true
  await nextTick()
  input.value?.focus()
}

function onKey(event: KeyboardEvent): void {
  const count = items.value.length
  if (event.key === 'ArrowDown' && count) {
    event.preventDefault()
    active.value = (active.value + 1) % count
  } else if (event.key === 'ArrowUp' && count) {
    event.preventDefault()
    active.value = (active.value - 1 + count) % count
  } else if (event.key === 'Enter') {
    event.preventDefault()
    choose(active.value)
  } else if (event.key === 'Escape') {
    close()
  }
}

const showField = computed(() => !props.compact || expanded.value)
</script>

<template>
  <button
    v-if="!showField"
    type="button"
    class="ui-icon-button"
    :aria-label="$t('shell.search')"
    data-testid="search-open"
    @click="expand"
  >
    <Search />
  </button>
  <div
    v-else
    class="relative"
    :class="compact ? 'absolute inset-x-2 top-[calc(env(safe-area-inset-top)+8px)] z-30' : 'w-64'"
  >
    <div class="relative">
      <Search
        :size="16"
        class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint"
        aria-hidden="true"
      />
      <input
        ref="input"
        v-model="text"
        type="text"
        enterkeyhint="search"
        autocomplete="off"
        class="ui-input h-9! pr-9! pl-9!"
        :placeholder="$t('search.placeholder')"
        :aria-label="$t('shell.search')"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="search-results"
        :aria-expanded="open && items.length > 0"
        data-testid="search-input"
        @keydown="onKey"
        @focus="open = true"
        @blur="((open = false), compact && !text && (expanded = false))"
      />
      <button
        v-if="compact || text"
        type="button"
        class="ui-icon-button absolute top-1/2 right-0.5 size-8! -translate-y-1/2"
        :aria-label="$t('common.close')"
        @mousedown.prevent="close"
      >
        <X :size="16" />
      </button>
    </div>
    <ul
      v-if="open && query"
      id="search-results"
      role="listbox"
      class="ui-panel absolute top-full right-0 mt-1 max-h-[70dvh] w-[min(420px,calc(100vw-16px))] overflow-y-auto py-1"
      data-testid="search-results"
    >
      <li v-if="results.isSuccess.value && !items.length" class="px-3 py-3 text-muted">
        {{ $t('search.none') }}
      </li>
      <li
        v-for="(item, i) in items"
        :key="item.occurrence_id"
        role="option"
        :aria-selected="i === active"
        class="flex cursor-pointer gap-3 px-3 py-2"
        :class="[i === active && 'bg-hover-tint', !item.upcoming && 'opacity-70']"
        @mousedown.prevent="choose(i)"
        @mousemove="active = i"
      >
        <span
          class="mt-1 h-4 w-0.5 shrink-0"
          :style="{ background: colorVar(item.color) }"
          aria-hidden="true"
        />
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="truncate font-medium">{{ item.title || $t('event.noTitle') }}</span>
          <span class="font-mono text-meta text-muted">{{ when(item) }}</span>
          <span v-if="item.location" class="truncate text-label text-muted">{{
            item.location
          }}</span>
          <span v-if="item.tags.length" class="mt-0.5 flex flex-wrap gap-1">
            <span
              v-for="tag in item.tags"
              :key="tag.id"
              class="cal-tag"
              :style="{ '--tag-color': colorVar(tag.color) }"
            >
              <span class="cal-tag-marker" />{{ tag.name }}
            </span>
          </span>
        </span>
      </li>
    </ul>
  </div>
</template>
