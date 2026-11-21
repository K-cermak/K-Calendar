<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { X } from '@lucide/vue'
import { tagsQuery } from '@/api/calendar'
import { colorVar } from '@/palette'

/**
 * Tag names for an event: suggests the user's tags while typing and takes any new name, which the
 * server turns into a tag with an automatic colour (SPEC 7).
 */
defineProps<{ id: string }>()
const model = defineModel<string[]>({ required: true })

const tags = useQuery(tagsQuery)
const text = ref('')
const open = ref(false)
const active = ref(0)

const fold = (value: string) => value.trim().toLocaleLowerCase()
const colorOf = (name: string) =>
  tags.data.value?.find((t) => fold(t.name) === fold(name))?.color ?? null

const suggestions = computed(() => {
  const query = fold(text.value)
  const chosen = new Set(model.value.map(fold))
  return (tags.data.value ?? [])
    .filter((t) => !chosen.has(fold(t.name)) && (!query || fold(t.name).includes(query)))
    .slice(0, 8)
})

const isNew = computed(() => {
  const query = fold(text.value)
  return !!query && !(tags.data.value ?? []).some((t) => fold(t.name) === query)
})

function add(name: string): void {
  const clean = name.trim().replace(/\s+/g, ' ')
  if (clean && !model.value.some((n) => fold(n) === fold(clean))) {
    model.value = [...model.value, clean]
  }
  text.value = ''
  active.value = 0
}

function remove(name: string): void {
  model.value = model.value.filter((n) => n !== name)
}

function onKey(event: KeyboardEvent): void {
  const count = suggestions.value.length
  if (event.key === 'ArrowDown' && count) {
    event.preventDefault()
    open.value = true
    active.value = (active.value + 1) % count
  } else if (event.key === 'ArrowUp' && count) {
    event.preventDefault()
    active.value = (active.value - 1 + count) % count
  } else if (event.key === 'Enter' || event.key === ',') {
    if (!text.value.trim() && event.key === 'Enter') return
    event.preventDefault()
    const pick = open.value ? suggestions.value[active.value] : undefined
    add(pick && !isNew.value ? pick.name : text.value)
  } else if (event.key === 'Backspace' && !text.value && model.value.length) {
    model.value = model.value.slice(0, -1)
  } else if (event.key === 'Escape' && open.value) {
    event.stopPropagation()
    open.value = false
  }
}
</script>

<template>
  <div class="relative">
    <div
      class="ui-input flex h-auto! min-h-10 flex-wrap items-center gap-1.5 py-1.5! focus-within:border-ink focus-within:shadow-[0_0_0_3px_var(--ring)]"
    >
      <span
        v-for="name in model"
        :key="name"
        class="cal-tag"
        :style="{ '--tag-color': colorVar(colorOf(name) ?? 'graphite') }"
      >
        <span class="cal-tag-marker" />
        {{ name }}
        <button
          type="button"
          class="-mr-1 grid size-5 cursor-pointer place-items-center text-muted hover:text-ink"
          :aria-label="$t('tags.remove', { name })"
          @click="remove(name)"
        >
          <X :size="12" />
        </button>
      </span>
      <input
        :id="id"
        v-model="text"
        class="min-w-24 flex-1 bg-transparent outline-none placeholder:text-faint"
        :placeholder="model.length ? '' : $t('tags.placeholder')"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open && suggestions.length > 0"
        :aria-controls="`${id}-list`"
        autocomplete="off"
        @focus="open = true"
        @blur="(add(text), (open = false))"
        @input="((open = true), (active = 0))"
        @keydown="onKey"
      />
    </div>
    <ul
      v-if="open && (suggestions.length || isNew)"
      :id="`${id}-list`"
      role="listbox"
      class="ui-panel absolute inset-x-0 top-full mt-1 max-h-60 overflow-y-auto py-1"
    >
      <li
        v-for="(tag, i) in suggestions"
        :key="tag.id"
        role="option"
        :aria-selected="i === active"
        class="ui-menu-item h-9!"
        :data-highlighted="i === active ? '' : undefined"
        @mousedown.prevent="add(tag.name)"
      >
        <span class="cal-tag-marker" :style="{ '--tag-color': colorVar(tag.color) }" />
        {{ tag.name }}
      </li>
      <li v-if="isNew" class="px-3 py-2 text-label text-muted">
        {{ $t('tags.createHint', { name: text.trim() }) }}
      </li>
    </ul>
  </div>
</template>
