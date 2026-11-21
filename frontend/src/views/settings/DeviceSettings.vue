<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Bell, BellOff, Share, SquarePlus } from '@lucide/vue'
import { useConfig } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { canInstall, install, isInstalled, isIosSafariTab } from '@/pwa'
import { isSubscribed, pushSupported, subscribe, unsubscribe } from '@/push'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const config = useConfig()
const supported = pushSupported()
const subscribed = ref(false)
const denied = ref(supported && Notification.permission === 'denied')
const push = useSubmit()

onMounted(async () => {
  if (supported && !isIosSafariTab()) subscribed.value = await isSubscribed().catch(() => false)
})

async function turnOn(): Promise<void> {
  const key = config.value?.vapid_public_key
  if (!key) return
  await push.run(async () => {
    const result = await subscribe(key)
    denied.value = result === 'denied'
    subscribed.value = result === 'granted'
  })
}

async function turnOff(): Promise<void> {
  await push.run(async () => {
    await unsubscribe()
    subscribed.value = false
  })
}

/** Settings that belong to this browser: installing the app, and later notifications. */
const ios = isIosSafariTab()
const installed = ref(isInstalled())
const installable = ref(canInstall())

async function installApp(): Promise<void> {
  installed.value = await install()
  installable.value = canInstall()
}
</script>

<template>
  <section class="flex flex-col gap-4" data-testid="device-settings">
    <h2 class="ui-section-title">{{ $t('settings.device.title') }}</h2>
    <p class="text-muted">{{ $t('settings.device.intro') }}</p>
    <div class="flex flex-col gap-3" data-testid="push-settings">
      <h3 class="font-medium">{{ $t('settings.device.notifications') }}</h3>
      <p class="text-label text-muted">{{ $t('settings.device.notificationsIntro') }}</p>
      <UiNotice v-if="ios" tone="info">{{ $t('settings.device.iosPush') }}</UiNotice>
      <UiNotice v-else-if="!supported" tone="warning">{{ $t('settings.device.noPush') }}</UiNotice>
      <UiNotice v-else-if="denied" tone="warning">{{ $t('settings.device.pushDenied') }}</UiNotice>
      <template v-else>
        <UiNotice v-if="subscribed" tone="success">{{ $t('settings.device.pushOn') }}</UiNotice>
        <UiButton
          v-if="subscribed"
          class="self-start"
          :loading="push.pending.value"
          data-testid="push-off"
          @click="turnOff"
        >
          <BellOff :size="16" /> {{ $t('settings.device.pushTurnOff') }}
        </UiButton>
        <UiButton
          v-else
          variant="primary"
          class="self-start"
          :loading="push.pending.value"
          :disabled="!config?.vapid_public_key"
          data-testid="push-on"
          @click="turnOn"
        >
          <Bell :size="16" /> {{ $t('settings.device.pushTurnOn') }}
        </UiButton>
      </template>
      <UiNotice v-if="push.error.value" tone="error">{{ push.error.value }}</UiNotice>
    </div>
    <div class="flex flex-col gap-3">
      <h3 class="font-medium">{{ $t('settings.device.install') }}</h3>
      <UiNotice v-if="installed" tone="success">{{ $t('settings.device.installed') }}</UiNotice>
      <div v-else-if="ios" class="ui-box" data-testid="ios-hint">
        <p>{{ $t('settings.device.iosIntro') }}</p>
        <ol class="flex flex-col gap-2 text-label">
          <li class="flex items-center gap-2">
            <Share :size="16" aria-hidden="true" /> {{ $t('settings.device.iosShare') }}
          </li>
          <li class="flex items-center gap-2">
            <SquarePlus :size="16" aria-hidden="true" /> {{ $t('settings.device.iosAdd') }}
          </li>
        </ol>
      </div>
      <UiButton v-else-if="installable" class="self-start" @click="installApp">
        {{ $t('settings.device.installButton') }}
      </UiButton>
      <p v-else class="text-label text-muted">{{ $t('settings.device.browserMenu') }}</p>
    </div>
  </section>
</template>
