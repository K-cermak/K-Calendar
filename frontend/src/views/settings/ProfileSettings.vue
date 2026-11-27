<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProfileUpdate } from '@/api/client'
import { useUpdateProfile } from '@/api/profile'
import { useConfig, useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { LOCALES } from '@/i18n'
import { VIEWS } from '@/router'
import { useToastStore } from '@/stores/toast'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import TimezoneSelect from '@/components/TimezoneSelect.vue'
import WorkingHoursSettings from './WorkingHoursSettings.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const { t } = useI18n()
const me = useMe()
const config = useConfig()
const toast = useToastStore()
const mutation = useUpdateProfile()
const { error, run } = useSubmit()

const name = ref(me.value?.display_name ?? '')
watch(
  () => me.value?.display_name,
  (value) => (name.value = value ?? ''),
)

const weekStarts = computed(() =>
  (['monday', 'sunday'] as const).map((value) => ({
    value,
    label: t(`settings.profile.${value}`),
  })),
)
const timeFormats = computed(() =>
  (['24', '12'] as const).map((value) => ({
    value,
    label: t(`settings.profile.hours${value}`),
  })),
)
const defaultViews = computed(() => [
  { value: 'auto' as const, label: t('settings.profile.auto') },
  ...VIEWS.map((value) => ({ value, label: t(`views.${value}`) })),
])

async function update(patch: ProfileUpdate): Promise<void> {
  if (await run(() => mutation.mutateAsync(patch))) toast.show(t('common.saved'))
}

async function saveName(): Promise<void> {
  const trimmed = name.value.trim()
  if (trimmed) await update({ display_name: trimmed })
}

function selected(event: Event): string {
  return (event.target as HTMLSelectElement).value
}
</script>

<template>
  <section v-if="me" class="flex flex-col gap-5">
    <h2 class="ui-section-title">{{ $t('settings.profile.title') }}</h2>
    <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
    <form @submit.prevent="saveName">
      <UiField :label="$t('account.displayName')" for="profile-name">
        <div class="ui-input-row">
          <UiInput id="profile-name" v-model="name" maxlength="100" autocomplete="name" />
          <UiButton type="submit" :disabled="!name.trim() || name.trim() === me.display_name">
            {{ $t('common.save') }}
          </UiButton>
        </div>
      </UiField>
    </form>
    <UiField :label="$t('account.email')" for="profile-email">
      <UiInput id="profile-email" :model-value="me.email" disabled />
    </UiField>
    <UiField
      :label="$t('settings.profile.timezone')"
      for="profile-timezone"
      :hint="$t('settings.profile.timezoneHint')"
    >
      <TimezoneSelect
        id="profile-timezone"
        :model-value="me.timezone"
        @update:model-value="(zone) => zone !== me?.timezone && update({ timezone: zone })"
      />
    </UiField>
    <UiField :label="$t('settings.profile.language')" for="profile-language">
      <select
        id="profile-language"
        class="ui-select"
        :value="me.locale"
        @change="update({ locale: selected($event) })"
      >
        <option v-for="(label, code) in LOCALES" :key="code" :value="code">{{ label }}</option>
      </select>
    </UiField>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('settings.profile.weekStart') }}</span>
      <UiSegmented
        :model-value="me.week_start"
        :options="weekStarts"
        :label="$t('settings.profile.weekStart')"
        @update:model-value="(week_start) => update({ week_start })"
      />
    </div>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('settings.profile.timeFormat') }}</span>
      <UiSegmented
        :model-value="me.time_format"
        :options="timeFormats"
        :label="$t('settings.profile.timeFormat')"
        @update:model-value="(time_format) => update({ time_format })"
      />
    </div>
    <UiField
      :label="$t('settings.profile.defaultView')"
      for="profile-view"
      :hint="$t('settings.profile.defaultViewHint')"
    >
      <select
        id="profile-view"
        class="ui-select"
        :value="me.default_view"
        @change="update({ default_view: selected($event) as ProfileUpdate['default_view'] })"
      >
        <option v-for="option in defaultViews" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </UiField>
    <label class="flex cursor-pointer items-start gap-3">
      <UiCheckbox
        :model-value="me.show_event_tags"
        class="mt-0.5"
        data-testid="show-event-tags"
        @update:model-value="update({ show_event_tags: $event === true })"
      />
      <span class="flex flex-col">
        <span>{{ $t('settings.profile.showEventTags') }}</span>
        <span class="text-label text-muted">{{ $t('settings.profile.showEventTagsHint') }}</span>
      </span>
    </label>
    <label v-if="config?.email_enabled" class="flex cursor-pointer items-start gap-3">
      <UiCheckbox
        :model-value="me.email_reminders_enabled"
        class="mt-0.5"
        data-testid="email-reminders"
        @update:model-value="update({ email_reminders_enabled: $event === true })"
      />
      <span class="flex flex-col">
        <span>{{ $t('settings.profile.emailReminders') }}</span>
        <span class="text-label text-muted">{{
          $t('settings.profile.emailRemindersHint', { email: me.email })
        }}</span>
      </span>
    </label>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('theme.label') }}</span>
      <ThemeSwitch :model-value="me.theme" @update:model-value="(theme) => update({ theme })" />
    </div>
  </section>
  <WorkingHoursSettings />
</template>
