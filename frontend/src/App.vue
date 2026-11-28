<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView } from 'vue-router'
import { setLucideProps } from '@lucide/vue'
import { useMe } from '@/api/session'
import { applyLocale } from '@/i18n'
import { registerServiceWorker, rememberUser } from '@/pwa'
import { useToastStore } from '@/stores/toast'
import { applyTheme, rememberTheme } from '@/theme'
import OfflineBanner from '@/components/OfflineBanner.vue'
import AppToast from '@/components/AppToast.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ScopeDialog from '@/components/ScopeDialog.vue'

setLucideProps({ strokeWidth: 1.6, size: 18 })

const me = useMe()
const toast = useToastStore()
const { t } = useI18n()

onMounted(() =>
  registerServiceWorker((reload) =>
    toast.pin(t('pwa.updateReady'), { label: t('pwa.reload'), run: reload }),
  ),
)

watch(
  () => me.value?.id,
  (id) => {
    if (id !== undefined) void rememberUser(id)
  },
)

// The theme follows the profile and is remembered for the next start (SPEC 11).
watch(
  () => me.value?.theme ?? 'system',
  (theme) => {
    applyTheme(theme)
    rememberTheme(theme)
  },
  { immediate: true },
)

watch(() => me.value?.locale, applyLocale, { immediate: true })
</script>

<template>
  <!-- Sticky with an opaque background, although the page never scrolls: iOS 26 Safari fills the
       area under the status bar with a solid colour only next to a fixed or sticky element at the
       top edge, and otherwise lays a soft blur over the top of the page that smears its first
       line of text. -->
  <div class="sticky top-0 flex h-dvh flex-col bg-bg">
    <OfflineBanner />
    <div class="min-h-0 flex-1 overflow-y-auto">
      <RouterView />
    </div>
  </div>
  <ConfirmDialog />
  <ScopeDialog />
  <AppToast />
</template>
