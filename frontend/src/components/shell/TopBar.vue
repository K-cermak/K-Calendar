<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight, Menu, PanelLeft } from '@lucide/vue'
import { VIEWS, type CalendarView } from '@/router'
import AccountMenu from './AccountMenu.vue'
import SearchField from './SearchField.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

/** Desktop: today, previous, next, the range, views and search. Phone: a compact version (SPEC 11). */
defineProps<{ compact: boolean; title: string; loading?: boolean }>()
const view = defineModel<CalendarView>('view', { required: true })
const emit = defineEmits<{ menu: []; today: []; previous: []; next: [] }>()

const { t } = useI18n()
const viewOptions = computed(() => VIEWS.map((value) => ({ value, label: t(`views.${value}`) })))
</script>

<template>
  <header
    class="relative flex h-14 shrink-0 items-center gap-2 border-b border-line px-2 pt-[env(safe-area-inset-top)] sm:px-3"
  >
    <button
      type="button"
      class="ui-icon-button"
      :aria-label="$t(compact ? 'shell.openMenu' : 'shell.toggleSidebar')"
      data-testid="menu-button"
      @click="emit('menu')"
    >
      <Menu v-if="compact" />
      <PanelLeft v-else />
    </button>
    <template v-if="!compact">
      <UiButton size="sm" class="ml-1" @click="emit('today')">{{ $t('shell.today') }}</UiButton>
      <div class="flex">
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('shell.previous')"
          @click="emit('previous')"
        >
          <ChevronLeft />
        </button>
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('shell.next')"
          @click="emit('next')"
        >
          <ChevronRight />
        </button>
      </div>
    </template>
    <h1
      class="min-w-0 flex-1 truncate text-base font-semibold tracking-[-0.02em] sm:ml-2"
      data-testid="range-title"
    >
      {{ title }}
    </h1>
    <!-- Shown only when loading takes a moment, so a quick load does not flicker. -->
    <span v-if="loading" class="cal-delayed flex text-muted"><UiSpinner /></span>
    <SearchField :compact="compact" />
    <UiSegmented
      v-if="!compact"
      v-model="view"
      :options="viewOptions"
      :label="$t('views.label')"
      class="mx-2 self-center"
    />
    <AccountMenu class="ml-1" />
  </header>
</template>
