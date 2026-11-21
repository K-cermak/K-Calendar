<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import { setLucideProps } from '@lucide/vue'
import { useMe } from '@/api/session'
import { applyLocale } from '@/i18n'
import { applyTheme, rememberTheme } from '@/theme'
import AppToast from '@/components/AppToast.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ScopeDialog from '@/components/ScopeDialog.vue'

setLucideProps({ strokeWidth: 1.6, size: 18 })

const me = useMe()

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
  <RouterView />
  <ConfirmDialog />
  <ScopeDialog />
  <AppToast />
</template>
