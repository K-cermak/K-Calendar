<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { calendarApi } from '@/api/calendar'
import type { PaletteColor } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import { useToastStore } from '@/stores/toast'
import { useI18n } from 'vue-i18n'
import ColorPicker from './ColorPicker.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** Adds a read-only calendar that follows an ICS address, such as public holidays (SPEC 10). */
const open = defineModel<boolean>('open', { required: true })
const { t } = useI18n()
const toast = useToastStore()

const url = ref('')
const name = ref('')
const color = ref<PaletteColor | null>('green')
const { pending, error, run } = useSubmit()

watch(open, (isOpen) => {
  if (!isOpen) return
  url.value = ''
  name.value = ''
  color.value = 'green'
  error.value = null
})

async function save(): Promise<void> {
  let failed: string | null = null
  const ok = await run(async () => {
    const created = await calendarApi.subscribe({
      url: url.value,
      name: name.value,
      color: color.value ?? 'green',
      refresh_interval_minutes: 60,
    })
    failed = created.subscription?.last_status === 'error' ? created.subscription.last_error : null
  })
  if (!ok) return
  open.value = false
  // The calendar is kept even when the first fetch fails; it is retried on its schedule.
  toast.show(failed ? t('subscription.addedWithError', { error: failed }) : t('subscription.added'))
}
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent class="ui-dialog max-w-[480px]!" data-testid="subscribe-dialog">
        <DialogTitle class="ui-dialog__title">{{ $t('subscription.newTitle') }}</DialogTitle>
        <DialogDescription class="text-label text-muted">
          {{ $t('subscription.newDescription') }}
        </DialogDescription>
        <form class="flex flex-col gap-4" @submit.prevent="save">
          <UiField :label="$t('subscription.url')" for="subscribe-url">
            <UiInput
              id="subscribe-url"
              v-model="url"
              type="url"
              inputmode="url"
              placeholder="webcal://…"
              required
              autofocus
            />
          </UiField>
          <UiField
            :label="$t('subscription.name')"
            for="subscribe-name"
            :hint="$t('subscription.nameHint')"
          >
            <UiInput id="subscribe-name" v-model="name" maxlength="100" />
          </UiField>
          <div class="flex flex-col gap-2">
            <span class="ui-label">{{ $t('calendars.color') }}</span>
            <ColorPicker v-model="color" :label="$t('calendars.color')" />
          </div>
          <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
          <div class="ui-dialog__actions">
            <DialogClose as-child>
              <UiButton>{{ $t('common.cancel') }}</UiButton>
            </DialogClose>
            <UiButton type="submit" variant="primary" :loading="pending" :disabled="!url.trim()">
              {{ $t('subscription.subscribe') }}
            </UiButton>
          </div>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
