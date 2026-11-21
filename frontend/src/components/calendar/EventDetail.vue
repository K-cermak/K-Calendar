<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Lock, MapPin, Pencil, Trash2, X } from '@lucide/vue'
import { calendarsQuery } from '@/api/calendar'
import type { Occurrence } from '@/api/client'
import { useMe } from '@/api/session'
import { colorVar } from '@/palette'
import { describeSpan, linkify, mapsUrl } from '@/text'

/** What the detail popover and the phone sheet show for one occurrence (SPEC 7, 11). */
const props = defineProps<{
  occurrence: Occurrence
  description: string | null
  readOnly: boolean
}>()
const emit = defineEmits<{ edit: []; delete: []; close: [] }>()

const me = useMe()
const calendars = useQuery(calendarsQuery)
const calendar = computed(() =>
  calendars.data.value?.find((c) => c.id === props.occurrence.calendar_id),
)
const when = computed(() =>
  me.value ? describeSpan(props.occurrence, me.value.locale, me.value.time_format) : '',
)
const parts = computed(() => (props.description ? linkify(props.description) : []))
const editable = computed(() => !props.occurrence.read_only && !props.readOnly)
</script>

<template>
  <div class="flex flex-col gap-3" data-testid="event-detail">
    <div class="flex items-start gap-3">
      <span
        class="mt-1.5 size-3 shrink-0"
        :style="{ background: colorVar(occurrence.color) }"
        aria-hidden="true"
      />
      <div class="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 class="text-base font-semibold tracking-[-0.01em] break-words">
          {{ occurrence.title || $t('event.noTitle') }}
        </h2>
        <p class="ui-numeric font-mono text-label text-muted">{{ when }}</p>
      </div>
      <div class="-mt-1 -mr-1 flex">
        <button
          v-if="editable"
          type="button"
          class="ui-icon-button"
          :aria-label="$t('event.edit')"
          data-testid="detail-edit"
          @click="emit('edit')"
        >
          <Pencil :size="16" />
        </button>
        <button
          v-if="editable"
          type="button"
          class="ui-icon-button hover:text-danger!"
          :aria-label="$t('event.delete')"
          data-testid="detail-delete"
          @click="emit('delete')"
        >
          <Trash2 :size="16" />
        </button>
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('common.close')"
          @click="emit('close')"
        >
          <X :size="16" />
        </button>
      </div>
    </div>
    <p v-if="calendar" class="flex items-center gap-2 text-label text-muted">
      <span class="size-2" :style="{ background: colorVar(calendar.color) }" aria-hidden="true" />
      {{ calendar.name }}
      <span v-if="occurrence.read_only" class="ui-badge ml-1 inline-flex gap-1">
        <Lock :size="10" /> {{ $t('event.readOnly') }}
      </span>
    </p>
    <a
      v-if="occurrence.location"
      :href="mapsUrl(occurrence.location)"
      target="_blank"
      rel="noopener noreferrer"
      class="flex items-start gap-2 text-ink hover:text-accent"
    >
      <MapPin :size="16" class="mt-0.5 text-muted" />
      <span class="break-words">{{ occurrence.location }}</span>
    </a>
    <p v-if="parts.length" class="text-label break-words whitespace-pre-wrap">
      <template v-for="(part, i) in parts" :key="i">
        <a
          v-if="part.href"
          :href="part.href"
          target="_blank"
          rel="noopener noreferrer"
          class="text-accent underline underline-offset-2"
          >{{ part.text }}</a
        >
        <template v-else>{{ part.text }}</template>
      </template>
    </p>
    <div v-if="occurrence.tags.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="tag in occurrence.tags"
        :key="tag.id"
        class="cal-tag"
        :style="{ '--tag-color': colorVar(tag.color) }"
      >
        <span class="cal-tag-marker" />{{ tag.name }}
      </span>
    </div>
  </div>
</template>
