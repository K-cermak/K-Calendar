<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'
import type { ProfileUpdate, WorkingHours } from '@/api/client'
import { useUpdateProfile } from '@/api/profile'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { formatDate, parseDate } from '@/dates'
import { useToastStore } from '@/stores/toast'
import {
  WORKING_DAYS,
  dayIsInvalid,
  nextInterval,
  orderedDays,
  type WorkingDay,
} from '@/workingHours'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** Working hours per day, with breaks, shaded in the week and day views (SPEC 7). */
const { t } = useI18n()
const me = useMe()
const toast = useToastStore()
const mutation = useUpdateProfile()
const { pending, error, run } = useSubmit()

const copy = (hours: WorkingHours): WorkingHours => JSON.parse(JSON.stringify(hours))
const draft = ref<WorkingHours | null>(me.value ? copy(me.value.working_hours) : null)
watch(
  () => me.value?.working_hours,
  (hours) => (draft.value = hours ? copy(hours) : null),
)

const days = computed(() => orderedDays(me.value?.week_start ?? 'monday'))
const changed = computed(
  () => JSON.stringify(draft.value) !== JSON.stringify(me.value?.working_hours),
)
const invalid = computed(() => WORKING_DAYS.filter((day) => dayIsInvalid(draft.value?.[day] ?? [])))

// Monday 2024-01-01 gives every weekday its own name in the user's language.
function dayName(day: WorkingDay): string {
  const date = parseDate('2024-01-01').add({ days: WORKING_DAYS.indexOf(day) })
  return formatDate(date, me.value?.locale ?? 'en', { weekday: 'long' })
}

function add(day: WorkingDay): void {
  const next = draft.value && nextInterval(draft.value[day])
  if (next) draft.value![day].push(next)
}

function remove(day: WorkingDay, index: number): void {
  draft.value?.[day].splice(index, 1)
}

async function update(patch: ProfileUpdate): Promise<void> {
  if (await run(() => mutation.mutateAsync(patch))) toast.show(t('common.saved'))
}

function save(): void {
  if (draft.value && !invalid.value.length) void update({ working_hours: copy(draft.value) })
}
</script>

<template>
  <section v-if="me && draft" class="flex flex-col gap-5" data-testid="working-hours">
    <h2 class="ui-section-title">{{ $t('settings.workingHours.title') }}</h2>
    <label class="flex cursor-pointer items-start gap-3">
      <UiCheckbox
        :model-value="me.working_hours_enabled"
        class="mt-0.5"
        data-testid="working-hours-enabled"
        @update:model-value="update({ working_hours_enabled: $event === true })"
      />
      <span class="flex flex-col">
        <span>{{ $t('settings.workingHours.show') }}</span>
        <span class="text-label text-muted">{{ $t('settings.workingHours.showHint') }}</span>
      </span>
    </label>

    <form
      v-if="me.working_hours_enabled"
      class="flex flex-col gap-4"
      novalidate
      @submit.prevent="save"
    >
      <div
        v-for="day in days"
        :key="day"
        class="grid gap-2 border-t border-line pt-4 sm:grid-cols-[128px_1fr]"
        :data-testid="`working-${day}`"
      >
        <span class="font-medium sm:pt-2.5">{{ dayName(day) }}</span>
        <div class="flex flex-col items-start gap-2">
          <span v-if="!draft[day].length" class="py-1 text-muted sm:pt-2.5">
            {{ $t('settings.workingHours.off') }}
          </span>
          <div v-for="(interval, index) in draft[day]" :key="index" class="flex items-center gap-2">
            <input
              v-model="interval.start"
              type="time"
              class="ui-input w-32! font-mono"
              :aria-label="$t('settings.workingHours.from', { day: dayName(day) })"
              :aria-invalid="invalid.includes(day) || undefined"
            />
            <span class="text-muted" aria-hidden="true">–</span>
            <input
              v-model="interval.end"
              type="time"
              class="ui-input w-32! font-mono"
              :aria-label="$t('settings.workingHours.to', { day: dayName(day) })"
              :aria-invalid="invalid.includes(day) || undefined"
            />
            <button
              type="button"
              class="ui-icon-button"
              :aria-label="$t('settings.workingHours.remove', { day: dayName(day) })"
              @click="remove(day, index)"
            >
              <X />
            </button>
          </div>
          <button
            v-if="nextInterval(draft[day])"
            type="button"
            class="text-label text-accent hover:underline"
            @click="add(day)"
          >
            {{ $t('settings.workingHours.add') }}
          </button>
        </div>
      </div>
      <p v-if="invalid.length" class="ui-error">{{ $t('settings.workingHours.invalid') }}</p>
      <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
      <UiButton
        type="submit"
        class="self-start"
        :disabled="!changed || invalid.length > 0"
        :loading="pending"
        data-testid="working-hours-save"
      >
        {{ $t('settings.workingHours.save') }}
      </UiButton>
    </form>
  </section>
</template>
