<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Globe, X } from '@lucide/vue'
import { useUpdateProfile } from '@/api/profile'
import { useMe } from '@/api/session'
import { deviceTimeZone } from '@/device'
import { useToastStore } from '@/stores/toast'

/** When the device is in another zone than the profile (travelling), offer to switch (SPEC 5). */
const { t } = useI18n()
const me = useMe()
const toast = useToastStore()
const update = useUpdateProfile()
const device = deviceTimeZone()
const KEY = 'zone-banner-dismissed'

function dismissedFor(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

const dismissed = ref(dismissedFor() === device)
const visible = computed(
  () => !!device && !!me.value && me.value.timezone !== device && !dismissed.value,
)

function dismiss(): void {
  dismissed.value = true
  try {
    if (device) sessionStorage.setItem(KEY, device)
  } catch {
    // Without storage the banner comes back on the next visit, which is acceptable.
  }
}

function switchZone(): void {
  if (!device) return
  update.mutate({ timezone: device }, { onError: () => toast.show(t('errors.unknown')) })
}
</script>

<template>
  <div
    v-if="visible"
    class="ui-notice ui-notice--info items-center! border-x-0 border-t-0 py-2!"
    role="status"
    data-testid="zone-banner"
  >
    <Globe :size="16" class="ui-notice__icon mt-0!" aria-hidden="true" />
    <p class="min-w-0 flex-1 text-label">
      {{ $t('zone.differs', { device, profile: me?.timezone }) }}
    </p>
    <button type="button" class="shrink-0 text-label font-medium text-accent" @click="switchZone">
      {{ $t('zone.switch', { device }) }}
    </button>
    <button
      type="button"
      class="ui-icon-button size-8! shrink-0"
      :aria-label="$t('common.close')"
      @click="dismiss"
    >
      <X :size="16" />
    </button>
  </div>
</template>
