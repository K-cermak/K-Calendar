<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight, Plus, Search, Trash2 } from '@lucide/vue'
import { applyTheme, parseTheme, type Theme } from '@/theme'
import { PALETTE, colorVar } from '@/palette'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ?theme=dark makes side-by-side screenshots against the reference form easy.
const theme = ref<Theme>(parseTheme(route.query.theme) ?? 'system')
watch(
  theme,
  (value) => {
    applyTheme(value)
    void router.replace({ query: value === 'system' ? {} : { theme: value } })
  },
  { immediate: true },
)
onBeforeUnmount(() => applyTheme('system'))

const title = ref('')
const password = ref('short')
const location = ref('Room 4')
const description = ref('')
const allDay = ref(true)
const work = ref(false)

const view = ref<'month' | 'week' | 'day' | 'agenda'>('week')
const viewOptions = computed(() =>
  (['month', 'week', 'day', 'agenda'] as const).map((value) => ({
    value,
    label: t(`views.${value}`),
  })),
)

const tokens = [
  'bg',
  'ink',
  'muted',
  'faint',
  'line',
  'line-hover',
  'accent',
  'accent-hover',
  'danger',
  'warning',
  'success',
]
const tags = [
  { name: 'tagTravel', color: 'teal' },
  { name: 'tagKids', color: 'amber' },
  { name: 'tagDeadline', color: 'red' },
] as const
</script>

<template>
  <main class="mx-auto flex max-w-[560px] flex-col gap-10 px-4 py-6 sm:px-0 sm:py-10">
    <header class="flex items-start justify-between gap-4">
      <div class="flex flex-col gap-1">
        <h1 class="text-xl leading-tight">{{ $t('showcase.title') }}</h1>
        <p class="text-muted">{{ $t('showcase.intro') }}</p>
      </div>
      <ThemeSwitch v-model="theme" />
    </header>

    <section class="flex flex-col gap-4">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.typography') }}
      </h2>
      <div class="flex flex-col gap-1 border border-line p-4">
        <p class="text-base font-semibold tracking-[-0.02em]">{{ $t('showcase.headingSample') }}</p>
        <p>{{ $t('showcase.bodySample') }}</p>
        <p class="ui-meta font-mono">{{ $t('showcase.metaSample') }}</p>
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.buttons') }}
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="primary">{{ $t('showcase.primary') }}</UiButton>
        <UiButton>{{ $t('showcase.secondary') }}</UiButton>
        <UiButton variant="ghost">{{ $t('showcase.ghost') }}</UiButton>
        <UiButton variant="danger">
          <Trash2 :size="16" />
          {{ $t('showcase.danger') }}
        </UiButton>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="primary" disabled>{{ $t('showcase.disabled') }}</UiButton>
        <UiButton variant="primary" loading>{{ $t('showcase.loading') }}</UiButton>
        <UiButton size="sm">{{ $t('showcase.today') }}</UiButton>
        <UiButton variant="ghost" icon-only size="sm" :aria-label="$t('showcase.previous')">
          <ChevronLeft :size="16" />
        </UiButton>
        <UiButton variant="ghost" icon-only size="sm" :aria-label="$t('showcase.next')">
          <ChevronRight :size="16" />
        </UiButton>
        <button type="button" class="ui-icon-button" :aria-label="$t('showcase.ghost')">
          <Search :size="18" />
        </button>
        <UiButton variant="primary" icon-only :aria-label="$t('showcase.primary')">
          <Plus :size="20" />
        </UiButton>
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.segmented') }}
      </h2>
      <UiSegmented v-model="view" :options="viewOptions" :label="$t('views.label')" />
    </section>

    <section class="flex flex-col gap-5">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.inputs') }}
      </h2>
      <UiField :label="$t('showcase.eventTitle')" for="sc-title">
        <UiInput
          id="sc-title"
          v-model="title"
          :placeholder="$t('showcase.eventTitlePlaceholder')"
        />
      </UiField>
      <UiField
        :label="$t('showcase.password')"
        for="sc-password"
        :error="password.length < 10 ? $t('showcase.passwordError') : undefined"
      >
        <UiInput
          id="sc-password"
          v-model="password"
          type="password"
          :invalid="password.length < 10"
          aria-describedby="sc-password-error"
        />
      </UiField>
      <UiField :label="$t('showcase.location')" for="sc-location">
        <UiInput id="sc-location" v-model="location" />
      </UiField>
      <UiField :label="$t('showcase.disabledInput')" for="sc-disabled">
        <UiInput id="sc-disabled" model-value="Europe/Prague" disabled />
      </UiField>
      <UiField :label="$t('showcase.description')" for="sc-description">
        <UiInput
          id="sc-description"
          v-model="description"
          multiline
          :placeholder="$t('showcase.descriptionPlaceholder')"
        />
      </UiField>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.checkboxes') }}
      </h2>
      <label class="flex cursor-pointer items-center gap-3">
        <UiCheckbox v-model="allDay" />
        {{ $t('showcase.allDay') }}
      </label>
      <label class="flex cursor-pointer items-center gap-3">
        <UiCheckbox v-model="work" />
        {{ $t('showcase.workCalendar') }}
      </label>
      <label class="flex items-center gap-3 text-faint">
        <UiCheckbox disabled />
        {{ $t('showcase.checkboxDisabled') }}
      </label>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.notices') }}
      </h2>
      <UiNotice>{{ $t('showcase.noticeNeutral') }}</UiNotice>
      <UiNotice tone="info">{{ $t('showcase.noticeInfo') }}</UiNotice>
      <UiNotice tone="warning">{{ $t('showcase.noticeWarning') }}</UiNotice>
      <UiNotice tone="error">{{ $t('showcase.noticeError') }}</UiNotice>
      <UiNotice tone="success">{{ $t('showcase.noticeSuccess') }}</UiNotice>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">{{ $t('showcase.tokens') }}</h2>
      <ul class="grid grid-cols-2 border-t border-l border-line sm:grid-cols-3">
        <li
          v-for="token in tokens"
          :key="token"
          class="flex items-center gap-2 border-r border-b border-line p-2"
        >
          <span
            class="size-5 shrink-0 border border-line"
            :style="{ background: `var(--${token})` }"
          />
          <span class="ui-code text-muted">{{ token }}</span>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.palette') }}
      </h2>
      <ul class="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <li
          v-for="color in PALETTE"
          :key="color"
          class="cal-event"
          :style="{ '--event-color': colorVar(color) }"
        >
          <span class="cal-event__title">{{ $t('showcase.eventTitleSample') }}</span>
          <span class="cal-event__time">09:00 – 10:00</span>
          <span class="ui-meta">{{ $t(`palette.${color}`) }}</span>
        </li>
        <li class="cal-event cal-event--past" :style="{ '--event-color': colorVar('blue') }">
          <span class="cal-event__title">{{ $t('showcase.eventPast') }}</span>
          <span class="cal-event__time">07:00 – 08:00</span>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">{{ $t('showcase.tags') }}</h2>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="tag in tags"
          :key="tag.name"
          class="cal-tag"
          :style="{ '--tag-color': colorVar(tag.color) }"
        >
          <span class="cal-tag-marker" />
          {{ $t(`showcase.${tag.name}`) }}
        </span>
      </div>
      <div class="flex gap-2">
        <span
          v-for="color in PALETTE"
          :key="color"
          class="cal-swatch"
          :style="{ '--swatch-color': colorVar(color) }"
          :title="$t(`palette.${color}`)"
        />
      </div>
    </section>
  </main>
</template>
