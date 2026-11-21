<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, call, type Me } from '@/api/client'
import { signedIn, useConfig } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { afterSignIn } from '@/router'
import AuthLayout from '@/components/AuthLayout.vue'
import OidcButton from '@/components/OidcButton.vue'
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
const resetting = ref(false)
const resetSent = ref(false)
const reset = useSubmit()

async function requestReset(): Promise<void> {
  const ok = await reset.run(() =>
    call(() => api.POST('/api/v1/auth/password-reset/request', { body: { email: email.value } })),
  )
  if (ok) resetSent.value = true
}

const i18n = useI18n()
const second = useSubmit({ unauthorized: 'login.invalidCode' })
// With two-step verification on, the password step returns a pending token for the code step.
const pendingToken = ref<string | null>(null)
const code = ref('')
const codeField = ref<{ focus: () => void } | null>(null)

const passwordLogin = computed(() => config.value?.password_login_enabled ?? true)
// A single sign-on that failed comes back here with ?error=<code>.
const redirectError = computed(() => {
  const value = route.query.error
  if (typeof value !== 'string') return null
  return i18n.te(`errors.${value}`) ? i18n.t(`errors.${value}`) : i18n.t('errors.unknown')
})

async function finish(me: Me): Promise<void> {
  signedIn(me)
  await router.replace(afterSignIn(route.query.next))
}

async function submit(): Promise<void> {
  const result = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/login', { body: { email: email.value, password: password.value } }),
    ),
  )
  if (!result) return
  if ('pending_token' in result) {
    pendingToken.value = result.pending_token
    await nextTick()
    codeField.value?.focus()
    return
  }
  await finish(result)
}

async function submitCode(): Promise<void> {
  const token = pendingToken.value
  if (!token) return
  const me = await second.attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/login/totp', { body: { pending_token: token, code: code.value } }),
    ),
  )
  if (me) await finish(me)
  else if (second.failure.value?.code === 'login_expired') pendingToken.value = null
}
</script>

<template>
  <AuthLayout
    :title="$t(pendingToken ? 'login.codeTitle' : resetting ? 'login.resetTitle' : 'login.title')"
  >
    <UiNotice v-if="redirectError" tone="error">{{ redirectError }}</UiNotice>
    <form
      v-if="pendingToken"
      class="flex flex-col gap-5"
      novalidate
      data-testid="totp-step"
      @submit.prevent="submitCode"
    >
      <p class="text-muted">{{ $t('login.codeHint') }}</p>
      <UiField :label="$t('login.code')" for="login-code">
        <UiInput
          id="login-code"
          ref="codeField"
          v-model="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="32"
          required
        />
      </UiField>
      <UiNotice v-if="second.error.value" tone="error">{{ second.error.value }}</UiNotice>
      <UiButton type="submit" variant="primary" :loading="second.pending.value">
        {{ $t('login.verify') }}
      </UiButton>
      <button
        type="button"
        class="cursor-pointer self-start font-medium text-accent"
        @click="((pendingToken = null), (code = ''))"
      >
        {{ $t('common.back') }}
      </button>
    </form>
    <form
      v-else-if="resetting"
      class="flex flex-col gap-5"
      novalidate
      data-testid="reset-request"
      @submit.prevent="requestReset"
    >
      <p class="text-muted">{{ $t('login.resetIntro') }}</p>
      <UiField :label="$t('account.email')" for="reset-email">
        <UiInput id="reset-email" v-model="email" type="email" autocomplete="username" required />
      </UiField>
      <UiNotice v-if="resetSent" tone="success">{{ $t('login.resetSent') }}</UiNotice>
      <UiNotice v-if="reset.error.value" tone="error">{{ reset.error.value }}</UiNotice>
      <UiButton type="submit" variant="primary" :loading="reset.pending.value">
        {{ $t('login.resetSubmit') }}
      </UiButton>
      <button
        type="button"
        class="cursor-pointer self-start font-medium text-accent"
        @click="((resetting = false), (resetSent = false))"
      >
        {{ $t('common.back') }}
      </button>
    </form>
    <form v-else-if="passwordLogin" class="flex flex-col gap-5" novalidate @submit.prevent="submit">
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
    <OidcButton
      v-if="!resetting && !pendingToken && config?.oidc_enabled"
      :next="route.query.next"
    />
    <div v-if="!resetting && !pendingToken" class="flex flex-col gap-2 text-muted">
      <p v-if="passwordLogin && !config?.email_enabled">{{ $t('login.forgot') }}</p>
      <button
        v-if="passwordLogin && config?.email_enabled"
        type="button"
        class="cursor-pointer self-start font-medium text-accent"
        data-testid="forgot-password"
        @click="resetting = true"
      >
        {{ $t('login.forgotLink') }}
      </button>
      <p v-if="config?.registration_open">
        {{ $t('login.noAccount') }}
        <RouterLink to="/register" class="font-medium text-accent">
          {{ $t('register.submit') }}
        </RouterLink>
      </p>
    </div>
  </AuthLayout>
</template>
