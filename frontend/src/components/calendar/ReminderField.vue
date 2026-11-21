<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'
import { useMe } from '@/api/session'
import { formatTime, parseDateTime } from '@/dates'
import {
  ALL_DAY_PRESETS,
  TIMED_PRESETS,
  describeReminder,
  fromAllDay,
  fromUnit,
  type ReminderWords,
  type TimedUnit,
} from '@/reminders'
import UiButton from '@/components/ui/UiButton.vue'

/** The reminders of an event: common offsets, or a custom one (SPEC 8). */
const props = defineProps<{ allDay: boolean }>()
const model = defineModel<number[]>({ required: true })

const i18n = useI18n()
const me = useMe()
const words = computed<ReminderWords>(() => ({
  t: (key, values, plural) =>
    plural === undefined ? i18n.t(key, values ?? {}) : i18n.t(key, values ?? {}, plural),
  time: (value) =>
    formatTime(
      parseDateTime(`2000-01-01T${value}`),
      me.value?.locale ?? 'en',
      me.value?.time_format ?? '24',
    ),
}))

const presets = computed(() =>
  (props.allDay ? ALL_DAY_PRESETS : TIMED_PRESETS).filter((m) => !model.value.includes(m)),
)
const choice = ref('')
const custom = ref(false)
const amount = ref(2)
const unit = ref<TimedUnit>('hours')
const dayBefore = ref(true)
const time = ref('18:00')

function add(minutes: number): void {
  if (!model.value.includes(minutes)) {
    model.value = [...model.value, minutes].sort((a, b) => b - a)
  }
}

function pick(): void {
  if (choice.value === 'custom') {
    custom.value = true
  } else if (choice.value !== '') {
    add(Number(choice.value))
  }
  choice.value = ''
}

function addCustom(): void {
  add(
    props.allDay
      ? fromAllDay({ dayBefore: dayBefore.value, time: time.value })
      : fromUnit(amount.value, unit.value),
  )
  custom.value = false
}

function remove(minutes: number): void {
  model.value = model.value.filter((m) => m !== minutes)
}
</script>

<template>
  <div class="ui-field" data-testid="reminders">
    <span class="ui-label">{{ $t('reminders.label') }}</span>
    <ul v-if="model.length" class="flex flex-col border border-line">
      <li
        v-for="minutes in model"
        :key="minutes"
        class="flex h-10 items-center justify-between gap-2 pl-3 not-first:border-t not-first:border-line"
      >
        <span>{{ describeReminder(minutes, allDay, words) }}</span>
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('reminders.remove')"
          @click="remove(minutes)"
        >
          <X :size="16" />
        </button>
      </li>
    </ul>
    <select
      v-if="model.length < 10 && !custom"
      v-model="choice"
      class="ui-select"
      :aria-label="$t('reminders.add')"
      data-testid="reminder-add"
      @change="pick"
    >
      <option value="" disabled>{{ $t('reminders.add') }}</option>
      <option v-for="minutes in presets" :key="minutes" :value="String(minutes)">
        {{ describeReminder(minutes, allDay, words) }}
      </option>
      <option value="custom">{{ $t('reminders.custom') }}</option>
    </select>
    <div v-if="custom" class="flex flex-wrap items-center gap-2">
      <template v-if="allDay">
        <select v-model="dayBefore" class="ui-select min-w-40!" :aria-label="$t('reminders.label')">
          <option :value="false">{{ $t('reminders.onTheDay') }}</option>
          <option :value="true">{{ $t('reminders.theDayBefore') }}</option>
        </select>
        <span class="text-muted">{{ $t('reminders.at') }}</span>
        <input
          v-model="time"
          type="time"
          class="ui-input w-32! font-mono"
          :aria-label="$t('reminders.at')"
        />
      </template>
      <template v-else>
        <input
          v-model.number="amount"
          type="number"
          min="0"
          max="999"
          class="ui-input w-20! font-mono"
          :aria-label="$t('reminders.label')"
        />
        <select v-model="unit" class="ui-select min-w-28!" :aria-label="$t('reminders.label')">
          <option v-for="u in ['minutes', 'hours', 'days'] as const" :key="u" :value="u">
            {{ $t(`reminders.unit.${u}`) }}
          </option>
        </select>
        <span class="text-muted">{{ $t('reminders.beforeWord') }}</span>
      </template>
      <UiButton size="sm" @click="addCustom">{{ $t('common.add') }}</UiButton>
      <UiButton size="sm" variant="ghost" @click="custom = false">{{
        $t('common.cancel')
      }}</UiButton>
    </div>
  </div>
</template>
