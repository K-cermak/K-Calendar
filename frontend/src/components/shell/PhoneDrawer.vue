<script setup lang="ts">
import {
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogDescription,
  DialogTitle,
} from 'reka-ui'
import { X } from '@lucide/vue'
import branding from '@branding'
import AppLogo from '@/components/AppLogo.vue'

const open = defineModel<boolean>('open', { required: true })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent
        class="cal-drawer fixed inset-y-0 left-0 z-50 flex w-[min(300px,85vw)] flex-col overflow-y-auto border-r border-line bg-bg pt-[env(safe-area-inset-top)] shadow-float outline-none"
        data-testid="drawer"
      >
        <div class="flex h-14 shrink-0 items-center justify-between border-b border-line pr-2 pl-4">
          <DialogTitle class="flex items-center gap-3 text-[17px] font-semibold tracking-[-0.02em]">
            <AppLogo />
            {{ branding.name }}
          </DialogTitle>
          <DialogDescription class="sr-only">{{ $t('shell.drawerDescription') }}</DialogDescription>
          <button
            type="button"
            class="ui-icon-button"
            :aria-label="$t('common.close')"
            @click="open = false"
          >
            <X />
          </button>
        </div>
        <slot />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
