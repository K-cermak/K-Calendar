<script setup lang="ts">
import { computed } from 'vue'
import type { EventTagStyle, Occurrence } from '@/api/client'
import { colorVar } from '@/palette'

/**
 * An event's tags in the grid and the agenda, as the user chose in the profile: colour squares,
 * or squares with the names. At most three, then "+N" (SPEC 7).
 */
const props = defineProps<{ tags: Occurrence['tags']; mode: Exclude<EventTagStyle, 'hidden'> }>()

const MAX_TAGS = 3
const shown = computed(() => props.tags.slice(0, MAX_TAGS))
const extra = computed(() => props.tags.length - shown.value.length)
</script>

<template>
  <span
    v-if="tags.length"
    class="flex min-w-0 flex-wrap items-center"
    :class="mode === 'names' ? 'gap-x-2 gap-y-0.5' : 'gap-1'"
    :aria-hidden="mode === 'markers' || undefined"
    data-testid="event-tags"
  >
    <template v-if="mode === 'names'">
      <span
        v-for="tag in shown"
        :key="tag.id"
        class="cal-tag-name"
        :style="{ '--tag-color': colorVar(tag.color) }"
      >
        <span class="cal-tag-marker" />
        <span class="truncate">{{ tag.name }}</span>
      </span>
    </template>
    <template v-else>
      <span
        v-for="tag in shown"
        :key="tag.id"
        class="cal-tag-marker"
        :style="{ '--tag-color': colorVar(tag.color) }"
        :title="tag.name"
      />
    </template>
    <span v-if="extra > 0" class="font-mono text-meta text-muted">+{{ extra }}</span>
  </span>
</template>
