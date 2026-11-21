<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api, call } from '@/api/client'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { relativeTime } from '@/format'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const i18n = useI18n()
const me = useMe()
const queryClient = useQueryClient()

const currentPassword = ref('')
const newPassword = ref('')
const passwordChanged = ref(false)
const password = useSubmit()

async function changePassword(): Promise<void> {
  passwordChanged.value = false
  const ok = await password.run(() =>
    call(() =>
      api.POST('/api/v1/me/password', {
        body: { current_password: currentPassword.value, new_password: newPassword.value },
      }),
    ),
  )
  if (!ok) return
  currentPassword.value = newPassword.value = ''
  passwordChanged.value = true
  await queryClient.invalidateQueries({ queryKey: ['sessions'] })
}

const sessions = useQuery({
  queryKey: ['sessions'],
  queryFn: () => call(() => api.GET('/api/v1/me/sessions')),
})
const sessionAction = useSubmit()

async function revoke(id: number): Promise<void> {
  await sessionAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/me/sessions/{session_id}', { params: { path: { session_id: id } } }),
    )
    await sessions.refetch()
  })
}

async function revokeOthers(): Promise<void> {
  await sessionAction.run(async () => {
    await call(() => api.DELETE('/api/v1/me/sessions'))
    await sessions.refetch()
  })
}

function device(agent: string | null): string {
  if (!agent) return i18n.t('settings.sessions.unknown')
  const browser = /Firefox|Edg|Chrome|Safari/.exec(agent)?.[0]?.replace('Edg', 'Edge')
  const system = /Android|iPhone|iPad|Mac OS X|Windows|Linux/
    .exec(agent)?.[0]
    ?.replace('Mac OS X', 'macOS')
  return [browser, system].filter(Boolean).join(', ') || agent.slice(0, 60)
}

function when(iso: string): string {
  return relativeTime(iso, me.value?.locale ?? 'en')
}
</script>

<template>
  <section v-if="me?.has_password" class="flex flex-col gap-4">
    <h2 class="ui-section-title">{{ $t('settings.password.title') }}</h2>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="changePassword">
      <input type="email" :value="me.email" autocomplete="username" hidden readonly />
      <UiField :label="$t('settings.password.current')" for="password-current">
        <UiInput
          id="password-current"
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
        />
      </UiField>
      <UiField
        :label="$t('settings.password.new')"
        for="password-new"
        :hint="$t('account.passwordHint')"
      >
        <UiInput
          id="password-new"
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
        />
      </UiField>
      <UiNotice v-if="password.error.value" tone="error">{{ password.error.value }}</UiNotice>
      <UiNotice v-if="passwordChanged" tone="success">
        {{ $t('settings.password.changed') }}
      </UiNotice>
      <UiButton
        type="submit"
        class="self-start"
        :loading="password.pending.value"
        :disabled="!currentPassword || !newPassword"
      >
        {{ $t('settings.password.submit') }}
      </UiButton>
    </form>
  </section>

  <section class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-4">
      <h2 class="ui-section-title">{{ $t('settings.sessions.title') }}</h2>
      <UiButton v-if="(sessions.data.value?.length ?? 0) > 1" size="sm" @click="revokeOthers">
        {{ $t('settings.sessions.signOutOthers') }}
      </UiButton>
    </div>
    <ul class="border border-line" data-testid="sessions">
      <li
        v-for="item in sessions.data.value"
        :key="item.id"
        class="flex items-center gap-3 px-3 py-2.5 not-first:border-t not-first:border-line"
      >
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="truncate">
            {{ device(item.user_agent) }}
            <span v-if="item.current" class="ml-1 text-label text-success">
              {{ $t('settings.sessions.current') }}
            </span>
          </span>
          <span class="ui-meta">
            {{ $t('settings.sessions.lastUsed', { time: when(item.last_seen_at_utc) }) }}
            <template v-if="item.ip"> · {{ item.ip }}</template>
          </span>
        </div>
        <UiButton v-if="!item.current" size="sm" variant="ghost" @click="revoke(item.id)">
          {{ $t('settings.sessions.signOut') }}
        </UiButton>
      </li>
    </ul>
    <UiNotice v-if="sessionAction.error.value" tone="error">
      {{ sessionAction.error.value }}
    </UiNotice>
  </section>
</template>
