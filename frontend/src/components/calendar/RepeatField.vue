<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMe } from '@/api/session'
import { formatDate, parseDate } from '@/dates'
import {
  PRESETS,
  WEEKDAYS,
  buildCustom,
  defaultCustom,
  matchRule,
  parseCustom,
  presetLabel,
  presetRule,
  summarize,
  type CustomRule,
  type Freq,
  type Preset,
  type Weekday,
  type Words,
} from '@/recurrence'
import UiInput from '@/components/ui/UiInput.vue'

/** The repeat choice: presets for the start date, a custom rule, or a rule kept from elsewhere. */
const props = defineProps<{ startDate: string; allDay: boolean }>()
const rule = defineModel<string | null>({ required: true })

const i18n = useI18n()
const me = useMe()
const locale = computed(() => me.value?.locale ?? 'en')
const start = computed(() => parseDate(props.startDate))

// Monday 2024-01-01 gives every weekday its own name in the user's language.
const weekdayDate = (day: Weekday) => parseDate('2024-01-01').add({ days: WEEKDAYS.indexOf(day) })
const words = computed<Words>(() => ({
  t: (key, values, plural) =>
    plural === undefined ? i18n.t(key, values ?? {}) : i18n.t(key, values ?? {}, plural),
  weekday: (day) => formatDate(weekdayDate(day), locale.value, { weekday: 'long' }),
  date: (iso) => formatDate(parseDate(iso), locale.value, { day: 'numeric', month: 'long' }),
}))

const original = rule.value
const choice = ref<Preset | 'unsupported'>(matchRule(rule.value, start.value))
// A rule from another calendar stays available to keep, even after picking something else.
const keepable = choice.value === 'unsupported'
const custom = ref<CustomRule>(
  (rule.value && parseCustom(rule.value, start.value)) || defaultCustom(start.value),
)

// The rule follows the choice; date-based presets follow the start date ("weekly on Tuesday").
watch(
  [choice, custom, start, () => props.allDay],
  () => {
    if (choice.value === 'unsupported') rule.value = original
    else if (choice.value === 'custom') rule.value = buildCustom(custom.value, props.allDay)
    else rule.value = presetRule(choice.value, start.value)
  },
  { deep: true },
)

function toggleDay(day: Weekday): void {
  const days = custom.value.byDay.includes(day)
    ? custom.value.byDay.filter((d) => d !== day)
    : WEEKDAYS.filter((d) => d === day || custom.value.byDay.includes(d))
  if (days.length) custom.value = { ...custom.value, byDay: days }
}

function setEnd(kind: 'never' | 'until' | 'count'): void {
  const end =
    kind === 'never'
      ? { kind }
      : kind === 'count'
        ? { kind, count: 10 }
        : { kind, date: start.value.add({ months: 3 }).toString() }
  custom.value = { ...custom.value, end }
}

const units: Freq[] = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="ui-field">
      <label for="event-repeat" class="ui-label">{{ $t('repeat.label') }}</label>
      <select id="event-repeat" v-model="choice" class="ui-select" data-testid="repeat-select">
        <option v-if="original && keepable" value="unsupported">
          {{ $t('repeat.keep', { summary: summarize(original, words) }) }}
        </option>
        <option v-for="preset in PRESETS" :key="preset" :value="preset">
          {{ presetLabel(preset, start, words) }}
        </option>
      </select>
      <p v-if="choice === 'unsupported'" class="ui-hint">{{ $t('repeat.unsupported') }}</p>
      <p v-else-if="rule && choice === 'custom'" class="ui-hint" data-testid="repeat-summary">
        {{ summarize(rule, words) }}
      </p>
    </div>

    <div v-if="choice === 'custom'" class="ui-box gap-4!" data-testid="repeat-custom">
      <div class="flex flex-wrap items-center gap-2">
        <span class="ui-label">{{ $t('repeat.custom.every') }}</span>
        <input
          v-model.number="custom.interval"
          type="number"
          min="1"
          max="999"
          class="ui-input w-20! font-mono"
          :aria-label="$t('repeat.custom.every')"
        />
        <select v-model="custom.freq" class="ui-select min-w-32!" :aria-label="$t('repeat.label')">
          <option v-for="unit in units" :key="unit" :value="unit">
            {{ $t(`repeat.custom.unit.${unit}`, {}, custom.interval) }}
          </option>
        </select>
      </div>
      <div v-if="custom.freq === 'WEEKLY'" class="flex flex-col gap-2">
        <span class="ui-label">{{ $t('repeat.custom.on') }}</span>
        <div class="flex gap-1">
          <button
            v-for="day in WEEKDAYS"
            :key="day"
            type="button"
            class="grid size-9 cursor-pointer place-items-center border text-label"
            :class="
              custom.byDay.includes(day)
                ? 'border-ink bg-ink text-bg'
                : 'border-line text-muted hover:border-line-hover'
            "
            :aria-pressed="custom.byDay.includes(day)"
            :aria-label="words.weekday(day)"
            @click="toggleDay(day)"
          >
            {{ formatDate(weekdayDate(day), locale, { weekday: 'narrow' }) }}
          </button>
        </div>
      </div>
      <fieldset class="flex flex-col gap-2">
        <legend class="ui-label mb-2">{{ $t('repeat.custom.ends') }}</legend>
        <label class="flex cursor-pointer items-center gap-3">
          <input
            type="radio"
            class="ui-radio"
            :checked="custom.end.kind === 'never'"
            @change="setEnd('never')"
          />
          {{ $t('repeat.custom.never') }}
        </label>
        <div class="flex items-center gap-3">
          <input
            id="repeat-until"
            type="radio"
            class="ui-radio"
            :checked="custom.end.kind === 'until'"
            @change="setEnd('until')"
          />
          <label for="repeat-until" class="w-12 cursor-pointer">{{
            $t('repeat.custom.onDate')
          }}</label>
          <input
            v-if="custom.end.kind === 'until'"
            v-model="custom.end.date"
            type="date"
            class="ui-input w-44! font-mono"
            :min="startDate"
            :aria-label="$t('repeat.custom.onDate')"
          />
        </div>
        <div class="flex items-center gap-3">
          <input
            id="repeat-count"
            type="radio"
            class="ui-radio"
            :checked="custom.end.kind === 'count'"
            @change="setEnd('count')"
          />
          <label for="repeat-count" class="w-12 cursor-pointer">{{
            $t('repeat.custom.after')
          }}</label>
          <template v-if="custom.end.kind === 'count'">
            <UiInput
              :model-value="String(custom.end.count)"
              type="number"
              min="1"
              max="999"
              class="w-20! font-mono"
              :aria-label="$t('repeat.custom.after')"
              @update:model-value="
                custom = {
                  ...custom,
                  end: { kind: 'count', count: Math.max(1, Number($event) || 1) },
                }
              "
            />
            <span class="text-muted">{{ $t('repeat.custom.times', {}, custom.end.count) }}</span>
          </template>
        </div>
      </fieldset>
    </div>
  </div>
</template>
