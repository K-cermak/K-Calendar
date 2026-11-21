<script setup lang="ts">
import { ref } from 'vue'
import { Share, SquarePlus } from '@lucide/vue'
import { canInstall, install, isInstalled, isIosSafariTab } from '@/pwa'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

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
