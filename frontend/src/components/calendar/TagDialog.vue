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
import { tagApi } from '@/api/calendar'
import type { PaletteColor, Tag } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import ColorPicker from './ColorPicker.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** Rename a tag or change its colour. */
const props = defineProps<{ tag: Tag | null }>()
const open = defineModel<boolean>('open', { required: true })

const name = ref('')
const color = ref<PaletteColor | null>(null)
const { pending, error, run } = useSubmit()

watch(open, (isOpen) => {
  if (!isOpen || !props.tag) return
  name.value = props.tag.name
  color.value = props.tag.color
  error.value = null
})

async function save(): Promise<void> {
  if (!props.tag) return
  const tag = props.tag
  const ok = await run(() =>
    tagApi.update(tag.id, { name: name.value, color: color.value ?? tag.color }),
  )
  if (ok) open.value = false
}
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent class="ui-dialog" data-testid="tag-dialog">
        <DialogTitle class="ui-dialog__title">{{ $t('tags.editTitle') }}</DialogTitle>
        <DialogDescription class="sr-only">{{ $t('tags.description') }}</DialogDescription>
        <form class="flex flex-col gap-4" @submit.prevent="save">
          <UiField :label="$t('tags.name')" for="tag-name">
            <UiInput id="tag-name" v-model="name" maxlength="100" required autofocus />
          </UiField>
          <div class="flex flex-col gap-2">
            <span class="ui-label">{{ $t('tags.color') }}</span>
            <ColorPicker v-model="color" :label="$t('tags.color')" />
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
