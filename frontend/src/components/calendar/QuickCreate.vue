<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { PopoverAnchor, PopoverContent, PopoverPortal, PopoverRoot } from 'reka-ui'
import { calendarsQuery, eventApi } from '@/api/calendar'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { toBody, type Draft } from '@/eventDraft'
import { describeSpan } from '@/text'
import { exclusiveEnd } from '@/dates'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** The small popover after clicking or dragging on the grid: a title and Enter (SPEC 11). */
const props = defineProps<{ draft: Draft | null; anchor: DOMRect | null }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ more: [draft: Draft] }>()

const me = useMe()
const calendars = useQuery(calendarsQuery)
const writable = computed(() => (calendars.data.value ?? []).filter((c) => !c.read_only))
const { pending, error, run } = useSubmit()

const title = ref('')
const calendarId = ref<number | null>(null)

watch(
  () => [open.value, props.draft] as const,
  ([isOpen, draft]) => {
    if (!isOpen || !draft) return
    title.value = ''
    calendarId.value = draft.calendar_id
    error.value = null
  },
  { immediate: true },
)

const reference = computed(() => {
  const rect = props.anchor
  return rect ? { getBoundingClientRect: () => rect } : undefined
})

const when = computed(() => {
  const draft = props.draft
  if (!draft || !me.value) return ''
  const span = draft.all_day
    ? { start: draft.startDate, end: exclusiveEnd(draft.endDate), all_day: true }
    : {
        start: `${draft.startDate}T${draft.startTime}:00`,
        end: `${draft.endDate}T${draft.endTime}:00`,
        all_day: false,
      }
  return describeSpan(span, me.value.locale, me.value.time_format)
})

function current(): Draft | null {
  return props.draft && calendarId.value !== null
    ? { ...props.draft, title: title.value, calendar_id: calendarId.value }
    : null
}

async function save(): Promise<void> {
  const draft = current()
  if (!draft) return
  if (await run(() => eventApi.create(toBody(draft)))) open.value = false
}

function more(): void {
  const draft = current()
  if (!draft) return
  open.value = false
  emit('more', draft)
}
</script>

<template>
  <PopoverRoot v-model:open="open">
    <PopoverAnchor :reference="reference" />
    <PopoverPortal>
      <PopoverContent
        class="ui-panel w-[320px] p-4"
        side="right"
        align="start"
        :side-offset="8"
        :collision-padding="12"
        data-testid="quick-create"
      >
        <form class="flex flex-col gap-3" @submit.prevent="save">
          <input
            v-model="title"
            class="ui-input font-medium"
            :placeholder="$t('event.titlePlaceholder')"
            :aria-label="$t('event.title')"
            maxlength="500"
            autofocus
          />
          <p class="ui-meta font-mono">{{ when }}</p>
          <select
            v-model="calendarId"
            class="ui-select w-full! min-w-0!"
            :aria-label="$t('event.calendar')"
          >
            <option v-for="calendar in writable" :key="calendar.id" :value="calendar.id">
              {{ calendar.name }}
            </option>
          </select>
          <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
          <div class="flex items-center gap-2">
            <button type="button" class="text-label text-accent hover:underline" @click="more">
              {{ $t('event.moreOptions') }}
            </button>
            <span class="flex-1" />
            <UiButton size="sm" @click="open = false">{{ $t('common.cancel') }}</UiButton>
            <UiButton type="submit" variant="primary" size="sm" :loading="pending">
              {{ $t('common.save') }}
            </UiButton>
          </div>
        </form>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
