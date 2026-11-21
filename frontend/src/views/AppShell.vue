<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Plus } from '@lucide/vue'
import { useMe } from '@/api/session'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { VIEWS, type CalendarView } from '@/router'
import { useUiStore } from '@/stores/ui'
import PhoneDrawer from '@/components/shell/PhoneDrawer.vue'
import SidebarContent from '@/components/shell/SidebarContent.vue'
import TopBar from '@/components/shell/TopBar.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const me = useMe()
const ui = useUiStore()
const compact = useMediaQuery('(max-width: 767px)')

/** The view in the URL, or the user's default: week on a wide screen, agenda on a phone. */
const defaultView = computed<CalendarView>(() => {
  const chosen = me.value?.default_view
  if (chosen && chosen !== 'auto') return chosen
  return compact.value ? 'agenda' : 'week'
})

const view = computed<CalendarView>({
  get: () => {
    const fromRoute = route.params.view
    return VIEWS.find((v) => v === fromRoute) ?? defaultView.value
  },
  set: (value) => {
    void router.push({ name: 'calendar', params: { view: value, date: route.params.date } })
  },
})

watch(
  () => route.name,
  (name) => {
    if (name === 'home') void router.replace({ name: 'calendar', params: { view: view.value } })
  },
  { immediate: true },
)

function toggleMenu(): void {
  if (compact.value) ui.drawerOpen = true
  else ui.sidebarOpen = !ui.sidebarOpen
}

const title = computed(() => t(`views.${view.value}`))
</script>

<template>
  <div class="flex h-dvh flex-col">
    <TopBar v-model:view="view" :compact="compact" :title="title" @menu="toggleMenu" />
    <div class="flex min-h-0 flex-1">
      <aside
        v-if="!compact && ui.sidebarOpen"
        class="w-64 shrink-0 overflow-y-auto border-r border-line"
        data-testid="sidebar"
      >
        <SidebarContent />
      </aside>
      <main class="min-w-0 flex-1 overflow-auto" data-testid="calendar-area" />
    </div>
    <PhoneDrawer v-if="compact" v-model:open="ui.drawerOpen">
      <SidebarContent />
    </PhoneDrawer>
    <button
      v-if="compact"
      type="button"
      class="ui-button ui-button--primary ui-button--icon fixed right-4 bottom-[max(16px,env(safe-area-inset-bottom))] z-20 size-14!"
      :aria-label="$t('shell.newEvent')"
      data-testid="fab"
    >
      <Plus :size="24" />
    </button>
  </div>
</template>
