<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery } from '@tanstack/vue-query'
import { Check, Copy, Download, RefreshCw, Upload } from '@lucide/vue'
import { calendarApi, calendarsQuery } from '@/api/calendar'
import type { ImportResult, PaletteColor } from '@/api/client'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { relativeTime } from '@/format'
import { useConfirmStore } from '@/stores/confirm'
import ColorPicker from './ColorPicker.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSheet from '@/components/ui/UiSheet.vue'

/**
 * Everything about one calendar: name and colour, and import, export and the secret feed for a
 * calendar of one's own, or the source and refresh state of a subscription (SPEC 7, 10).
 */
const props = defineProps<{ calendarId: number | null }>()
const open = defineModel<boolean>('open', { required: true })

const { t } = useI18n()
const me = useMe()
const confirm = useConfirmStore()
const calendars = useQuery(calendarsQuery)
const calendar = computed(
  () => calendars.data.value?.find((c) => c.id === props.calendarId) ?? null,
)

const name = ref('')
const color = ref<PaletteColor | null>('blue')
const saving = useSubmit()
const feed = useSubmit()
const refresh = useSubmit()
const importing = useSubmit()
const imported = ref<ImportResult | null>(null)
const copied = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(open, (isOpen) => {
  if (!isOpen || !calendar.value) return
  name.value = calendar.value.name
  color.value = calendar.value.color
  imported.value = null
  copied.value = false
  for (const s of [saving, feed, refresh, importing]) s.error.value = null
})

const intervals = [15, 30, 60, 180, 360, 1440]

function intervalLabel(minutes: number): string {
  if (minutes < 60) return t('subscription.minutes', { n: minutes }, minutes)
  const hours = minutes / 60
  return t('subscription.hours', { n: hours }, hours)
}

async function save(): Promise<void> {
  const current = calendar.value
  if (!current) return
  const ok = await saving.run(() =>
    calendarApi.update(current.id, { name: name.value, color: color.value ?? current.color }),
  )
  if (ok) open.value = false
}

async function setInterval(minutes: number): Promise<void> {
  const current = calendar.value
  if (current)
    await saving.run(() => calendarApi.update(current.id, { refresh_interval_minutes: minutes }))
}

async function newFeed(): Promise<void> {
  const current = calendar.value
  if (!current) return
  if (current.feed_url) {
    const sure = await confirm.ask({
      title: t('feed.replaceTitle'),
      message: t('feed.replaceMessage'),
      confirmLabel: t('feed.replace'),
    })
    if (!sure) return
  }
  copied.value = false
  await feed.run(() => calendarApi.setFeed(current.id))
}

async function removeFeed(): Promise<void> {
  const current = calendar.value
  if (current) await feed.run(() => calendarApi.removeFeed(current.id))
}

async function copyFeed(): Promise<void> {
  if (!calendar.value?.feed_url) return
  try {
    await navigator.clipboard.writeText(calendar.value.feed_url)
    copied.value = true
  } catch {
    document.querySelector<HTMLInputElement>('#feed-url')?.select()
  }
}

async function importFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const current = calendar.value
  input.value = ''
  if (!file || !current) return
  imported.value = null
  await importing.run(async () => {
    imported.value = await calendarApi.importFile(current.id, file)
  })
}

function when(iso: string): string {
  return relativeTime(iso, me.value?.locale ?? 'en')
}
</script>

<template>
  <UiSheet v-model:open="open" :title="$t('calendars.settingsTitle')">
    <div v-if="calendar" class="flex flex-col gap-8 pt-1 pb-2" data-testid="calendar-settings">
      <form class="flex flex-col gap-4" @submit.prevent="save">
        <UiField :label="$t('calendars.name')" for="settings-name">
          <UiInput id="settings-name" v-model="name" maxlength="100" required autofocus />
        </UiField>
        <div class="flex flex-col gap-2">
          <span class="ui-label">{{ $t('calendars.color') }}</span>
          <ColorPicker v-model="color" :label="$t('calendars.color')" />
        </div>
        <UiNotice v-if="saving.error.value" tone="error">{{ saving.error.value }}</UiNotice>
        <UiButton
          type="submit"
          variant="primary"
          class="self-start"
          :loading="saving.pending.value"
        >
          {{ $t('common.save') }}
        </UiButton>
      </form>

      <section v-if="calendar.subscription" class="flex flex-col gap-3" data-testid="subscription">
        <h3 class="ui-section-title">{{ $t('subscription.title') }}</h3>
        <p class="text-label break-all text-muted">{{ calendar.subscription.source_url }}</p>
        <UiNotice v-if="calendar.subscription.last_status === 'error'" tone="warning">
          {{ $t('subscription.failed', { error: calendar.subscription.last_error }) }}
        </UiNotice>
        <p class="ui-meta">
          {{
            calendar.subscription.last_fetched_at_utc
              ? $t('subscription.lastRefresh', {
                  when: when(calendar.subscription.last_fetched_at_utc),
                })
              : $t('subscription.never')
          }}
        </p>
        <div class="flex flex-wrap items-end gap-3">
          <UiButton
            :loading="refresh.pending.value"
            @click="refresh.run(() => calendarApi.refresh(calendar!.id))"
          >
            <RefreshCw :size="16" /> {{ $t('subscription.refresh') }}
          </UiButton>
          <UiField :label="$t('subscription.interval')" for="settings-interval">
            <select
              id="settings-interval"
              class="ui-select min-w-40!"
              :value="calendar.subscription.refresh_interval_minutes"
              @change="setInterval(Number(($event.target as HTMLSelectElement).value))"
            >
              <option v-for="minutes in intervals" :key="minutes" :value="minutes">
                {{ intervalLabel(minutes) }}
              </option>
            </select>
          </UiField>
        </div>
        <UiNotice v-if="refresh.error.value" tone="error">{{ refresh.error.value }}</UiNotice>
        <p class="ui-hint">{{ $t('subscription.readOnly') }}</p>
      </section>

      <template v-else>
        <section class="flex flex-col gap-3">
          <h3 class="ui-section-title">{{ $t('transfer.title') }}</h3>
          <p class="text-label text-muted">{{ $t('transfer.description') }}</p>
          <div class="flex flex-wrap gap-3">
            <a
              :href="calendarApi.exportUrl(calendar.id)"
              download
              class="ui-button"
              data-testid="export"
            >
              <Download :size="16" /> {{ $t('transfer.export') }}
            </a>
            <UiButton :loading="importing.pending.value" @click="fileInput?.click()">
              <Upload :size="16" /> {{ $t('transfer.import') }}
            </UiButton>
            <input
              ref="fileInput"
              type="file"
              accept=".ics,text/calendar"
              class="sr-only"
              data-testid="import-file"
              tabindex="-1"
              @change="importFile"
            />
          </div>
          <UiNotice v-if="importing.error.value" tone="error">{{ importing.error.value }}</UiNotice>
          <UiNotice v-if="imported" :tone="imported.skipped.length ? 'warning' : 'success'">
            <p data-testid="import-result">
              {{
                $t('transfer.result', {
                  created: imported.created,
                  updated: imported.updated,
                  skipped: imported.skipped.length,
                })
              }}
            </p>
            <ul
              v-if="imported.skipped.length"
              class="mt-2 flex flex-col gap-1 text-label text-muted"
            >
              <li v-for="(skip, i) in imported.skipped.slice(0, 20)" :key="i">
                <span class="text-ink">{{ skip.title || skip.uid || $t('event.noTitle') }}</span>:
                {{ skip.reason }}
              </li>
            </ul>
          </UiNotice>
        </section>

        <section class="flex flex-col gap-3" data-testid="feed">
          <h3 class="ui-section-title">{{ $t('feed.title') }}</h3>
          <p class="text-label text-muted">{{ $t('feed.description') }}</p>
          <template v-if="calendar.feed_url">
            <div class="ui-input-row">
              <UiInput
                id="feed-url"
                :model-value="calendar.feed_url"
                readonly
                class="font-mono text-label!"
              />
              <UiButton :aria-label="$t('feed.copy')" icon-only @click="copyFeed">
                <Check v-if="copied" class="text-success" />
                <Copy v-else />
              </UiButton>
            </div>
            <p class="ui-hint">{{ $t('feed.secret') }}</p>
            <div class="flex flex-wrap gap-3">
              <UiButton size="sm" @click="newFeed">{{ $t('feed.replace') }}</UiButton>
              <UiButton size="sm" variant="danger" @click="removeFeed">{{
                $t('feed.off')
              }}</UiButton>
            </div>
          </template>
          <UiButton v-else class="self-start" :loading="feed.pending.value" @click="newFeed">
            {{ $t('feed.on') }}
          </UiButton>
          <UiNotice v-if="feed.error.value" tone="error">{{ feed.error.value }}</UiNotice>
        </section>
      </template>
    </div>
  </UiSheet>
</template>
