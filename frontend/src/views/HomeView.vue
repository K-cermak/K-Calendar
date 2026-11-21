<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { api, call } from '@/api/client'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import branding from '@branding'

const health = useQuery({
  queryKey: ['health'],
  queryFn: () => call(() => api.GET('/api/v1/health')),
})
</script>

<template>
  <main class="mx-auto flex max-w-[560px] flex-col gap-6 px-4 py-10">
    <h1 class="text-xl leading-tight">{{ branding.name }}</h1>
    <div v-if="health.isPending.value" class="flex items-center gap-2 text-muted">
      <UiSpinner />
      {{ $t('home.checking') }}
    </div>
    <UiNotice v-else-if="health.isError.value" tone="error">{{ $t('home.unreachable') }}</UiNotice>
    <UiNotice v-else tone="success">
      {{ $t('home.healthy') }}
      <span class="ui-meta ml-1 font-mono">{{
        $t('home.version', { version: health.data.value?.version })
      }}</span>
    </UiNotice>
    <RouterLink to="/showcase" class="self-start text-accent underline-offset-4 hover:underline">
      {{ $t('home.showcase') }}
    </RouterLink>
  </main>
</template>
