<script setup lang="ts">
import { WifiOff } from '@lucide/vue'
import { useOnline } from '@/composables/useOnline'

const online = useOnline()
</script>

<template>
  <div
    v-if="!online"
    class="ui-notice ui-notice--warning items-center! border-x-0 border-t-0 py-2! pt-[max(8px,env(safe-area-inset-top))]!"
    role="status"
    data-testid="offline-banner"
  >
    <WifiOff :size="16" class="ui-notice__icon mt-0!" aria-hidden="true" />
    <p class="text-label">{{ $t('offline.banner') }}</p>
  </div>
</template>
