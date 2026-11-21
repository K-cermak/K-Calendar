<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, call } from '@/api/client'
import { signedIn, useConfig } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { afterSignIn } from '@/router'
import AuthLayout from '@/components/AuthLayout.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const route = useRoute()
const router = useRouter()
const config = useConfig()
const { pending, error, attempt } = useSubmit({ unauthorized: 'login.invalid' })

const email = ref('')
const password = ref('')

const passwordLogin = computed(() => config.value?.password_login_enabled ?? true)

async function submit(): Promise<void> {
  const me = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/login', { body: { email: email.value, password: password.value } }),
    ),
  )
  if (!me) return
  signedIn(me)
  await router.replace(afterSignIn(route.query.next))
}
</script>

<template>
  <AuthLayout :title="$t('login.title')">
    <form v-if="passwordLogin" class="flex flex-col gap-5" novalidate @submit.prevent="submit">
      <UiField :label="$t('account.email')" for="login-email">
        <UiInput
          id="login-email"
          v-model="email"
          type="email"
          autocomplete="username"
          required
          autofocus
        />
      </UiField>
      <UiField :label="$t('account.password')" for="login-password">
        <UiInput
          id="login-password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </UiField>
      <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
      <UiButton type="submit" variant="primary" :loading="pending">
        {{ $t('login.submit') }}
      </UiButton>
    </form>
    <div class="flex flex-col gap-2 text-muted">
      <p v-if="passwordLogin && !config?.email_enabled">{{ $t('login.forgot') }}</p>
      <p v-if="config?.registration_open">
        {{ $t('login.noAccount') }}
        <RouterLink to="/register" class="font-medium text-accent">
          {{ $t('register.submit') }}
        </RouterLink>
      </p>
    </div>
  </AuthLayout>
</template>
