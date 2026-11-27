<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { ArrowLeft, Check, Copy, EllipsisVertical, X } from '@lucide/vue'
import { api, call, type AdminUser, type CreatedLink, type PendingInvite } from '@/api/client'
import type { components } from '@/api/schema'
import { useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { relativeTime } from '@/format'
import { useConfirmStore } from '@/stores/confirm'
import { useToastStore } from '@/stores/toast'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const i18n = useI18n()
const me = useMe()
const confirm = useConfirmStore()
const toast = useToastStore()
const queryClient = useQueryClient()

const users = useQuery({
  queryKey: ['admin', 'users'],
  queryFn: () => call(() => api.GET('/api/v1/admin/users')),
})
const invites = useQuery({
  queryKey: ['admin', 'invites'],
  queryFn: () => call(() => api.GET('/api/v1/admin/invites')),
})
const instanceSettings = useQuery({
  queryKey: ['admin', 'settings'],
  queryFn: () => call(() => api.GET('/api/v1/admin/settings')),
})
const status = useQuery({
  queryKey: ['admin', 'status'],
  queryFn: () => call(() => api.GET('/api/v1/admin/status')),
})
const loadError = computed(
  () => users.error.value ?? invites.error.value ?? instanceSettings.error.value,
)

const inviteEmail = ref('')
const link = ref<CreatedLink | null>(null)
const resetLink = ref<{ user: AdminUser; link: CreatedLink } | null>(null)
const copied = ref(false)
const create = useSubmit()
const toggle = useSubmit()
const testMail = useSubmit()
const testMailSent = ref(false)

async function sendTestMail(): Promise<void> {
  testMailSent.value = false
  testMailSent.value = await testMail.run(() => call(() => api.POST('/api/v1/admin/test-email')))
}
const userAction = useSubmit()

function when(iso: string): string {
  return relativeTime(iso, me.value?.locale ?? 'en')
}

async function createInvite(): Promise<void> {
  copied.value = false
  await create.run(async () => {
    link.value = await call(() =>
      api.POST('/api/v1/admin/invites', { body: { email: inviteEmail.value.trim() || null } }),
    )
    inviteEmail.value = ''
    await invites.refetch()
  })
}

async function copy(url: string, field: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(url)
    copied.value = true
  } catch {
    document.querySelector<HTMLInputElement>(field)?.select()
  }
}

async function revokeInvite(invite: PendingInvite): Promise<void> {
  await create.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/invites/{invite_id}', {
        params: { path: { invite_id: invite.id } },
      }),
    )
    await invites.refetch()
  })
}

type InstanceSettings = components['schemas']['InstanceSettings']
const LIMITS = {
  session_days: { min: 1, max: 3650 },
} as const
type LimitKey = keyof typeof LIMITS
const limitKeys = Object.keys(LIMITS) as LimitKey[]
const limits = ref<Record<LimitKey, string>>({ session_days: '' })
const limitErrors = ref<Partial<Record<LimitKey, string>>>({})
const limitsSave = useSubmit()

function showLimits(s: InstanceSettings): void {
  limits.value = { session_days: String(s.session_days) }
}
watch(
  () => instanceSettings.data.value,
  (s) => {
    if (s) showLimits(s)
  },
  { immediate: true },
)

async function saveLimits(): Promise<void> {
  const body = {} as Record<LimitKey, number>
  limitErrors.value = {}
  for (const key of limitKeys) {
    const value = Number(limits.value[key].trim())
    const { min, max } = LIMITS[key]
    if (!limits.value[key].trim() || !Number.isInteger(value) || value < min || value > max)
      limitErrors.value[key] = i18n.t('admin.limits.range', { min, max })
    body[key] = value
  }
  if (Object.keys(limitErrors.value).length) return
  const ok = await limitsSave.run(async () => {
    const saved = await call(() => api.PATCH('/api/v1/admin/settings', { body }))
    queryClient.setQueryData(['admin', 'settings'], saved)
  })
  if (ok) toast.show(i18n.t('common.saved'))
}

async function setRegistration(value: boolean): Promise<void> {
  const ok = await toggle.run(async () => {
    await call(() => api.PATCH('/api/v1/admin/settings', { body: { registration_enabled: value } }))
    await instanceSettings.refetch()
    await queryClient.invalidateQueries({ queryKey: ['config'] })
  })
  if (ok) toast.show(i18n.t('common.saved'))
}

// The server enforces both guards (SPEC 6); the menu only reflects them.
const activeAdmins = computed(
  () => (users.data.value ?? []).filter((u) => u.is_admin && u.is_active).length,
)
function isSelf(user: AdminUser): boolean {
  return user.id === me.value?.id
}
function lastAdmin(user: AdminUser): boolean {
  return user.is_admin && user.is_active && activeAdmins.value <= 1
}

async function updateUser(
  user: AdminUser,
  body: components['schemas']['AdminUserUpdate'],
): Promise<void> {
  const ok = await userAction.run(async () => {
    await call(() =>
      api.PATCH('/api/v1/admin/users/{user_id}', { params: { path: { user_id: user.id } }, body }),
    )
    await users.refetch()
  })
  if (ok) toast.show(i18n.t('common.saved'))
}

async function createResetLink(user: AdminUser): Promise<void> {
  copied.value = false
  await userAction.run(async () => {
    const created = await call(() =>
      api.POST('/api/v1/admin/users/{user_id}/reset-link', {
        params: { path: { user_id: user.id } },
      }),
    )
    resetLink.value = { user, link: created }
  })
}

async function resetTotp(user: AdminUser): Promise<void> {
  const sure = await confirm.ask({
    title: i18n.t('admin.users.resetTotpTitle', { name: user.display_name }),
    message: i18n.t('admin.users.resetTotpMessage'),
    confirmLabel: i18n.t('admin.users.resetTotp'),
  })
  if (!sure) return
  await userAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/users/{user_id}/totp', { params: { path: { user_id: user.id } } }),
    )
    await users.refetch()
  })
}

async function deleteUser(user: AdminUser): Promise<void> {
  const sure = await confirm.ask({
    title: i18n.t('admin.users.deleteTitle', { name: user.display_name }),
    message: i18n.t('admin.users.deleteMessage'),
    confirmLabel: i18n.t('admin.users.delete'),
    danger: true,
  })
  if (!sure) return
  await userAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/users/{user_id}', { params: { path: { user_id: user.id } } }),
    )
    await users.refetch()
  })
}
</script>

<template>
  <main class="mx-auto flex w-full max-w-[600px] flex-col gap-10 px-4 py-6 sm:py-10">
    <header class="flex items-center gap-3">
      <RouterLink to="/" class="ui-icon-button" :aria-label="$t('common.back')">
        <ArrowLeft />
      </RouterLink>
      <h1 class="text-xl leading-tight">{{ $t('admin.title') }}</h1>
    </header>

    <UiNotice v-if="loadError" tone="error">{{ $t('errors.unknown') }}</UiNotice>

    <section class="flex flex-col gap-4">
      <h2 class="ui-section-title">{{ $t('admin.invite.title') }}</h2>
      <p class="text-muted">{{ $t('admin.invite.description') }}</p>
      <form @submit.prevent="createInvite">
        <UiField :label="$t('admin.invite.email')" for="invite-email">
          <div class="ui-input-row">
            <UiInput id="invite-email" v-model="inviteEmail" type="email" autocomplete="off" />
            <UiButton type="submit" variant="primary" :loading="create.pending.value">
              {{ $t('admin.invite.create') }}
            </UiButton>
          </div>
        </UiField>
      </form>
      <UiNotice v-if="create.error.value" tone="error">{{ create.error.value }}</UiNotice>
      <div v-if="link" class="flex flex-col gap-2">
        <div class="ui-input-row">
          <UiInput id="invite-link" :model-value="link.url" readonly data-testid="invite-link" />
          <UiButton
            :aria-label="$t('admin.invite.copy')"
            icon-only
            @click="copy(link.url, '#invite-link')"
          >
            <Check v-if="copied" class="text-success" />
            <Copy v-else />
          </UiButton>
        </div>
        <p class="ui-meta">{{ $t('admin.invite.once', { when: when(link.expires_at_utc) }) }}</p>
        <p v-if="link.emailed" class="text-label text-success">{{ $t('admin.invite.emailed') }}</p>
      </div>
      <ul v-if="invites.data.value?.length" class="border border-line">
        <li
          v-for="invite in invites.data.value"
          :key="invite.id"
          class="flex items-center gap-3 px-3 py-2 not-first:border-t not-first:border-line"
        >
          <span class="min-w-0 flex-1 truncate">
            {{ invite.email ?? $t('admin.invite.anyone') }}
          </span>
          <span class="ui-meta">
            {{ $t('admin.invite.expires', { when: when(invite.expires_at_utc) }) }}
          </span>
          <UiButton
            variant="ghost"
            size="sm"
            icon-only
            :aria-label="$t('admin.invite.revoke')"
            @click="revokeInvite(invite)"
          >
            <X :size="16" />
          </UiButton>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="ui-section-title">{{ $t('admin.users.title') }}</h2>
      <ul class="border border-line" data-testid="users">
        <li
          v-for="user in users.data.value"
          :key="user.id"
          class="flex items-center gap-3 px-3 py-2.5 not-first:border-t not-first:border-line"
        >
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="truncate font-medium">{{ user.display_name }}</span>
            <span class="truncate text-label text-muted">{{ user.email }}</span>
            <span v-if="user.last_seen_at_utc" class="ui-meta">
              {{ $t('admin.users.lastSeen', { when: when(user.last_seen_at_utc) }) }}
            </span>
          </div>
          <span v-if="user.is_admin" class="ui-badge">{{ $t('admin.users.admin') }}</span>
          <span v-if="user.totp_enabled" class="ui-badge">{{ $t('admin.users.twoStep') }}</span>
          <span v-if="!user.is_active" class="ui-badge ui-badge--error">
            {{ $t('admin.users.inactive') }}
          </span>
          <DropdownMenuRoot :modal="false">
            <DropdownMenuTrigger
              :class="iconButton"
              :aria-label="$t('admin.users.actions', { name: user.display_name })"
              data-testid="user-actions"
            >
              <EllipsisVertical :size="18" />
            </DropdownMenuTrigger>
            <DropdownMenuPortal>
              <DropdownMenuContent :class="menuPanel" align="end" :side-offset="4">
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="!user.is_active"
                  @select="createResetLink(user)"
                >
                  {{ $t('admin.users.resetLink') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  v-if="user.totp_enabled"
                  :class="menuItem"
                  @select="resetTotp(user)"
                >
                  {{ $t('admin.users.resetTotp') }}
                </DropdownMenuItem>
                <DropdownMenuSeparator class="ui-menu-separator" />
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="user.is_admin && (isSelf(user) || lastAdmin(user))"
                  @select="updateUser(user, { is_admin: !user.is_admin })"
                >
                  {{ $t(user.is_admin ? 'admin.users.revokeAdmin' : 'admin.users.makeAdmin') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="user.is_active && (isSelf(user) || lastAdmin(user))"
                  @select="updateUser(user, { is_active: !user.is_active })"
                >
                  {{ $t(user.is_active ? 'admin.users.deactivate' : 'admin.users.reactivate') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  :class="[menuItem, 'text-danger']"
                  :disabled="isSelf(user) || lastAdmin(user)"
                  @select="deleteUser(user)"
                >
                  {{ $t('admin.users.delete') }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenuPortal>
          </DropdownMenuRoot>
        </li>
      </ul>
      <UiNotice v-if="userAction.error.value" tone="error">{{ userAction.error.value }}</UiNotice>
      <div v-if="resetLink" class="flex flex-col gap-2" data-testid="reset-link">
        <p class="text-muted">
          {{ $t('admin.users.resetLinkFor', { name: resetLink.user.display_name }) }}
        </p>
        <div class="ui-input-row">
          <UiInput id="reset-link" :model-value="resetLink.link.url" readonly />
          <UiButton
            :aria-label="$t('admin.invite.copy')"
            icon-only
            @click="copy(resetLink.link.url, '#reset-link')"
          >
            <Check v-if="copied" class="text-success" />
            <Copy v-else />
          </UiButton>
        </div>
        <p class="ui-meta">
          {{ $t('admin.users.resetOnce', { when: when(resetLink.link.expires_at_utc) }) }}
        </p>
      </div>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="ui-section-title">{{ $t('admin.registration.title') }}</h2>
      <label class="flex cursor-pointer items-start gap-3">
        <UiCheckbox
          :model-value="instanceSettings.data.value?.registration_enabled ?? false"
          :disabled="toggle.pending.value || !instanceSettings.data.value"
          class="mt-0.5"
          @update:model-value="setRegistration($event === true)"
        />
        <span class="flex flex-col">
          <span>{{ $t('admin.registration.label') }}</span>
          <span class="text-label text-muted">{{ $t('admin.registration.hint') }}</span>
        </span>
      </label>
      <UiNotice v-if="toggle.error.value" tone="error">{{ toggle.error.value }}</UiNotice>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="ui-section-title">{{ $t('admin.limits.title') }}</h2>
      <form
        class="flex flex-col gap-4 sm:w-80"
        novalidate
        data-testid="instance-limits"
        @submit.prevent="saveLimits"
      >
        <UiField
          v-for="key in limitKeys"
          :key="key"
          :label="$t(`admin.limits.${key}.label`)"
          :for="`limit-${key}`"
          :hint="$t(`admin.limits.${key}.hint`)"
          :error="limitErrors[key]"
        >
          <UiInput
            :id="`limit-${key}`"
            v-model="limits[key]"
            inputmode="numeric"
            :invalid="!!limitErrors[key]"
          />
        </UiField>
        <UiNotice v-if="limitsSave.error.value" tone="error">{{ limitsSave.error.value }}</UiNotice>
        <UiButton
          type="submit"
          class="self-start"
          :disabled="limitsSave.pending.value || !instanceSettings.data.value"
        >
          {{ $t('common.save') }}
        </UiButton>
      </form>
    </section>

    <section v-if="status.data.value" class="flex flex-col gap-3" data-testid="instance-status">
      <h2 class="ui-section-title">{{ $t('admin.status.title') }}</h2>
      <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
        <dt class="text-muted">{{ $t('admin.status.version') }}</dt>
        <dd class="ui-numeric font-mono">{{ status.data.value.version }}</dd>
        <dt class="text-muted">{{ $t('admin.status.users') }}</dt>
        <dd class="ui-numeric font-mono">{{ status.data.value.user_count }}</dd>
        <dt class="text-muted">{{ $t('admin.status.email') }}</dt>
        <dd>
          {{ $t(status.data.value.smtp_configured ? 'admin.status.yes' : 'admin.status.no') }}
        </dd>
        <dt class="text-muted">{{ $t('admin.status.push') }}</dt>
        <dd>
          {{ $t(status.data.value.push_configured ? 'admin.status.yes' : 'admin.status.no') }}
        </dd>
        <dt class="text-muted">{{ $t('admin.status.oidc') }}</dt>
        <dd>
          {{ $t(status.data.value.oidc_configured ? 'admin.status.yes' : 'admin.status.no') }}
        </dd>
        <dt class="text-muted">{{ $t('admin.status.passwordLogin') }}</dt>
        <dd>
          {{
            $t(status.data.value.password_login_enabled ? 'admin.status.on' : 'admin.status.off')
          }}
        </dd>
      </dl>
      <div v-if="status.data.value.smtp_configured" class="flex flex-col gap-2">
        <UiButton
          class="self-start"
          :loading="testMail.pending.value"
          data-testid="test-mail"
          @click="sendTestMail"
        >
          {{ $t('admin.status.testMail') }}
        </UiButton>
        <UiNotice v-if="testMailSent" tone="success">
          {{ $t('admin.status.testMailSent', { email: me?.email }) }}
        </UiNotice>
        <UiNotice v-if="testMail.error.value" tone="error">{{ testMail.error.value }}</UiNotice>
      </div>
    </section>
  </main>
</template>
