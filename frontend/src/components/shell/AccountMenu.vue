<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { LogOut, Settings, Shield } from '@lucide/vue'
import { signOut, useMe } from '@/api/session'
import { useSubmit } from '@/composables/useSubmit'
import { useToastStore } from '@/stores/toast'
import { menuItem, menuPanel } from '@/components/ui/menu'

const router = useRouter()
const me = useMe()
const toast = useToastStore()
const leaving = useSubmit()

async function logout(): Promise<void> {
  if (await leaving.run(signOut)) await router.replace('/login')
  else if (leaving.error.value) toast.show(leaving.error.value)
}
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger
      class="grid size-9 cursor-pointer place-items-center border border-line bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] font-medium text-ink hover:border-line-hover pointer-coarse:size-11"
      :aria-label="$t('account.menu')"
      data-testid="account-menu"
    >
      {{ me?.display_name.charAt(0).toUpperCase() }}
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :class="[menuPanel, 'min-w-[260px]']" align="end" :side-offset="6">
        <DropdownMenuLabel class="flex flex-col px-3 py-2">
          <span class="font-medium" data-testid="signed-in-as">{{ me?.display_name }}</span>
          <span class="text-label text-muted">{{ me?.email }}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator class="ui-menu-separator" />
        <DropdownMenuItem :class="menuItem" @select="router.push('/settings')">
          <Settings :size="16" /> {{ $t('settings.title') }}
        </DropdownMenuItem>
        <DropdownMenuItem v-if="me?.is_admin" :class="menuItem" @select="router.push('/admin')">
          <Shield :size="16" /> {{ $t('admin.title') }}
        </DropdownMenuItem>
        <DropdownMenuItem :class="menuItem" @select="logout">
          <LogOut :size="16" /> {{ $t('account.signOut') }}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
