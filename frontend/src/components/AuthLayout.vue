<script setup lang="ts">
import branding from '@branding'
import { useConfig } from '@/api/session'

defineProps<{ title: string; description?: string }>()

const config = useConfig()
</script>

<template>
  <main
    class="mx-auto flex min-h-dvh w-full max-w-[400px] flex-col justify-center gap-8 px-4 py-10"
  >
    <header class="flex flex-col gap-2">
      <p class="text-label font-medium text-muted">{{ branding.name }}</p>
      <h1 class="text-xl leading-tight">{{ title }}</h1>
      <p v-if="description" class="text-muted">{{ description }}</p>
    </header>
    <slot />
    <footer v-if="config" class="ui-meta" data-testid="version">
      {{ $t('home.version', { version: config.version }) }}
    </footer>
  </main>
</template>
