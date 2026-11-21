<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery } from '@tanstack/vue-query'
import { calendarsQuery, eventApi } from '@/api/calendar'
import type { EventDetail } from '@/api/client'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { draftFromEvent, moveStart, problem, toBody, toggleAllDay, type Draft } from '@/eventDraft'
import { useScopeStore } from '@/stores/scope'
import ColorPicker from './ColorPicker.vue'
import RepeatField from './RepeatField.vue'
import TagInput from './TagInput.vue'
import type { EditorTarget } from './types'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSheet from '@/components/ui/UiSheet.vue'

/** The full event editor: a dialog on a wide screen, a bottom sheet on a phone (SPEC 7, 11). */
const props = defineProps<{ target: EditorTarget | null }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ saved: [event: EventDetail]; delete: [event: EventDetail] }>()

const { t } = useI18n()
const me = useMe()
const calendars = useQuery(calendarsQuery)
const writable = computed(() => (calendars.data.value ?? []).filter((c) => !c.read_only))
const { pending, error, run } = useSubmit()

const scopes = useScopeStore()
const draft = ref<Draft | null>(null)
const moreOptions = ref(false)
const attempted = ref(false)
// A new key per opening resets the repeat field to the event being edited.
const session = ref(0)

watch(
  () => [open.value, props.target] as const,
  ([isOpen, target]) => {
    if (!isOpen || !target) return
    draft.value =
      target.kind === 'create'
        ? { ...target.draft }
        : draftFromEvent(target.event, me.value?.timezone ?? 'UTC')
    // The zone and colour live behind "more options"; open it when they hold something unusual.
    moreOptions.value =
      !!draft.value.color || (!draft.value.all_day && draft.value.timezone !== me.value?.timezone)
    attempted.value = false
    error.value = null
    session.value += 1
  },
  { immediate: true },
)

const zones = computed(() => {
  const known = Intl.supportedValuesOf('timeZone')
  const current = draft.value?.timezone
  return current && !known.includes(current) ? [current, ...known] : known
})
const invalid = computed(() => (draft.value ? problem(draft.value) : null))
const editing = computed(() => (props.target?.kind === 'edit' ? props.target.event : null))

function setStartDate(value: string): void {
  if (draft.value && value) draft.value = moveStart(draft.value, value, draft.value.startTime)
}
function setStartTime(value: string): void {
  if (draft.value && value) draft.value = moveStart(draft.value, draft.value.startDate, value)
}
function setAllDay(value: boolean | 'indeterminate'): void {
  if (draft.value) draft.value = toggleAllDay(draft.value, value === true)
}

async function save(): Promise<void> {
  attempted.value = true
  const current = draft.value
  if (!current || invalid.value) return
  const event = editing.value
  const body = toBody(current)
  let save: () => Promise<EventDetail> = () => eventApi.create(body)
  if (event?.recurring && event.occurrence) {
    // One occurrence keeps the series' rule and calendar, so "this event" is only offered without
    // changes to those.
    const seriesOnly = current.rrule !== event.rrule || current.calendar_id !== event.calendar_id
    const scope = await scopes.ask('edit', !seriesOnly)
    if (!scope) return
    const { rrule: _rule, calendar_id: _calendar, ...forOne } = body
    const sent = scope === 'this' ? forOne : body
    save = () => eventApi.update(event.id, sent, { scope, occurrence: event.occurrence })
  } else if (event) {
    save = () => eventApi.update(event.id, body)
  }
  let saved: EventDetail | null = null
  const ok = await run(async () => {
    saved = await save()
  })
  if (ok && saved) {
    emit('saved', saved)
    open.value = false
  }
}
</script>

<template>
  <UiSheet v-model:open="open" :title="t(editing ? 'event.editTitle' : 'event.newTitle')">
    <form
      v-if="draft"
      class="flex flex-col gap-4 pt-1"
      novalidate
      data-testid="event-editor"
      @submit.prevent="save"
    >
      <UiInput
        id="event-title"
        v-model="draft.title"
        class="h-11! text-base! font-medium"
        maxlength="500"
        :placeholder="$t('event.titlePlaceholder')"
        :aria-label="$t('event.title')"
        autofocus
      />
      <UiField :label="$t('event.calendar')" for="event-calendar">
        <select id="event-calendar" v-model="draft.calendar_id" class="ui-select">
          <option v-for="calendar in writable" :key="calendar.id" :value="calendar.id">
            {{ calendar.name }}
          </option>
        </select>
      </UiField>

      <label class="flex cursor-pointer items-center gap-3 self-start">
        <UiCheckbox :model-value="draft.all_day" @update:model-value="setAllDay" />
        {{ $t('event.allDay') }}
      </label>

      <div class="ui-field">
        <label for="event-start-date" class="ui-label">{{ $t('event.starts') }}</label>
        <div class="ui-input-row">
          <input
            id="event-start-date"
            type="date"
            class="ui-input font-mono"
            :value="draft.startDate"
            required
            @change="setStartDate(($event.target as HTMLInputElement).value)"
          />
          <input
            v-if="!draft.all_day"
            type="time"
            class="ui-input w-32! flex-none font-mono"
            :aria-label="$t('event.startTime')"
            :value="draft.startTime"
            required
            @change="setStartTime(($event.target as HTMLInputElement).value)"
          />
        </div>
      </div>
      <div class="ui-field">
        <label for="event-end-date" class="ui-label">
          {{ $t(draft.all_day ? 'event.lastDay' : 'event.ends') }}
        </label>
        <div class="ui-input-row">
          <input
            id="event-end-date"
            v-model="draft.endDate"
            type="date"
            class="ui-input font-mono"
            :aria-invalid="(attempted && !!invalid) || undefined"
            required
          />
          <input
            v-if="!draft.all_day"
            v-model="draft.endTime"
            type="time"
            class="ui-input w-32! flex-none font-mono"
            :aria-label="$t('event.endTime')"
            :aria-invalid="(attempted && !!invalid) || undefined"
            required
          />
        </div>
      </div>
      <p v-if="attempted && invalid" class="ui-error">{{ $t('event.endBeforeStart') }}</p>

      <RepeatField
        :key="session"
        v-model="draft.rrule"
        :start-date="draft.startDate"
        :all-day="draft.all_day"
      />

      <UiField :label="$t('event.location')" for="event-location">
        <UiInput id="event-location" v-model="draft.location" maxlength="500" />
      </UiField>
      <UiField :label="$t('event.description')" for="event-description">
        <UiInput
          id="event-description"
          v-model="draft.description"
          multiline
          class="min-h-24!"
          maxlength="20000"
        />
      </UiField>
      <UiField :label="$t('event.tags')" for="event-tags">
        <TagInput id="event-tags" v-model="draft.tags" />
      </UiField>

      <button
        type="button"
        class="ui-disclosure self-start"
        :aria-expanded="moreOptions"
        @click="moreOptions = !moreOptions"
      >
        <svg class="ui-disclosure__icon" viewBox="0 0 14 14" aria-hidden="true">
          <path d="M3 5l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" />
        </svg>
        {{ $t('event.moreOptions') }}
      </button>
      <div v-if="moreOptions" class="flex flex-col gap-4">
        <UiField
          v-if="!draft.all_day"
          :label="$t('event.timezone')"
          for="event-timezone"
          :hint="$t('event.timezoneHint')"
        >
          <select id="event-timezone" v-model="draft.timezone" class="ui-select">
            <option v-for="zone in zones" :key="zone" :value="zone">{{ zone }}</option>
          </select>
        </UiField>
        <div class="flex flex-col gap-2">
          <span class="ui-label">{{ $t('event.color') }}</span>
          <ColorPicker v-model="draft.color" :label="$t('event.color')" allow-none />
        </div>
      </div>

      <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
      <div class="flex items-center gap-3 border-t border-line pt-4">
        <UiButton
          v-if="editing"
          variant="danger"
          data-testid="editor-delete"
          @click="(emit('delete', editing), (open = false))"
        >
          {{ $t('event.delete') }}
        </UiButton>
        <span class="flex-1" />
        <UiButton @click="open = false">{{ $t('common.cancel') }}</UiButton>
        <UiButton type="submit" variant="primary" :loading="pending" data-testid="editor-save">
          {{ $t('common.save') }}
        </UiButton>
      </div>
    </form>
  </UiSheet>
</template>
