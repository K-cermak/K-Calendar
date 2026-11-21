<script setup lang="ts">
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { X } from '@lucide/vue'

/** A dialog that rises from the bottom on a phone: square corners, a hairline top (SPEC 11). */
defineProps<{ title: string; hideTitle?: boolean }>()
const open = defineModel<boolean>('open', { required: true })

// The field marked autofocus, such as an event's title, rather than the close button.
function focusFirst(event: Event): void {
  const target = (event.target as HTMLElement | null)?.querySelector<HTMLElement>('[autofocus]')
  if (!target) return
  event.preventDefault()
  target.focus()
}
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent class="cal-sheet" :aria-describedby="undefined" @open-auto-focus="focusFirst">
        <div class="flex h-12 shrink-0 items-center justify-between pr-1 pl-4">
          <DialogTitle class="font-semibold tracking-[-0.01em]" :class="hideTitle && 'sr-only'">
            {{ title }}
          </DialogTitle>
          <button
            type="button"
            class="ui-icon-button"
            :aria-label="$t('common.close')"
            @click="open = false"
          >
            <X />
          </button>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-[max(16px,env(safe-area-inset-bottom))]">
          <slot />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
