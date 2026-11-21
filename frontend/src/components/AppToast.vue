<script setup lang="ts">
import { X } from '@lucide/vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-4 bottom-[max(16px,env(safe-area-inset-bottom))] z-50 grid items-end justify-items-start sm:right-auto sm:left-6"
    aria-live="polite"
  >
    <!-- Transitions rather than keyframes: a new message can replace one that is still arriving.
         It leaves the way it came, a little faster. While one leaves and the next arrives, both
         share the one grid cell, so the new one does not start beside the old and then jump. -->
    <Transition
      enter-from-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
      leave-to-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
      enter-active-class="transition-[opacity,translate] duration-240 ease-out"
      leave-active-class="transition-[opacity,translate] duration-150 ease-out"
    >
      <div
        v-if="toast.current"
        :key="toast.current.id"
        role="status"
        class="ui-snackbar pointer-events-auto col-start-1 row-start-1 w-full max-w-[480px] sm:w-auto sm:min-w-[320px]"
        data-testid="toast"
      >
        <span class="flex-1">{{ toast.current.text }}</span>
        <button
          v-if="toast.current.action"
          type="button"
          class="ui-snackbar__action"
          @click="toast.act()"
        >
          {{ toast.current.action.label }}
        </button>
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('common.close')"
          @click="toast.close()"
        >
          <X :size="16" />
        </button>
      </div>
    </Transition>
  </div>
</template>
