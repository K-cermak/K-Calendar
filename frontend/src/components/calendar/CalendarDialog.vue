<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  DialogClose,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogDescription,
  DialogTitle,
} from 'reka-ui'
import { calendarApi } from '@/api/calendar'
import type { Calendar, PaletteColor } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import ColorPicker from './ColorPicker.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** Create a calendar, or rename and recolour one. */
const props = defineProps<{ calendar: Calendar | null }>()
const open = defineModel<boolean>('open', { required: true })

const name = ref('')
const color = ref<PaletteColor | null>('blue')
const { pending, error, run } = useSubmit()

watch(open, (isOpen) => {
  if (!isOpen) return
  name.value = props.calendar?.name ?? ''
  color.value = props.calendar?.color ?? 'blue'
  error.value = null
})

async function save(): Promise<void> {
  const body = { name: name.value, color: color.value ?? 'blue' }
  const ok = await run(() =>
    props.calendar ? calendarApi.update(props.calendar.id, body) : calendarApi.create(body),
  )
  if (ok) open.value = false
}
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent class="ui-dialog" data-testid="calendar-dialog">
        <DialogTitle class="ui-dialog__title">
          {{ $t(calendar ? 'calendars.editTitle' : 'calendars.newTitle') }}
        </DialogTitle>
        <DialogDescription class="sr-only">{{ $t('calendars.description') }}</DialogDescription>
        <form class="flex flex-col gap-4" @submit.prevent="save">
          <UiField :label="$t('calendars.name')" for="calendar-name">
            <UiInput id="calendar-name" v-model="name" maxlength="100" required autofocus />
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
            <UiButton type="submit" variant="primary" :loading="pending">
              {{ $t('common.save') }}
            </UiButton>
          </div>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
