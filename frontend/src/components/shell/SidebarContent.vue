<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useQuery } from '@tanstack/vue-query'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Check, CircleAlert, EllipsisVertical, Plus, Rss } from '@lucide/vue'
import {
  calendarApi,
  calendarsQuery,
  tagApi,
  tagsQuery,
  useCalendarVisibility,
} from '@/api/calendar'
import type { Calendar, Tag } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import type { PlainDate, WeekStart } from '@/dates'
import { colorVar } from '@/palette'
import { useConfirmStore } from '@/stores/confirm'
import { useToastStore } from '@/stores/toast'
import { useUiStore } from '@/stores/ui'
import CalendarDialog from '@/components/calendar/CalendarDialog.vue'
import CalendarSettings from '@/components/calendar/CalendarSettings.vue'
import SubscribeDialog from '@/components/calendar/SubscribeDialog.vue'
import MonthGrid from '@/components/calendar/MonthGrid.vue'
import TagDialog from '@/components/calendar/TagDialog.vue'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'
import UiButton from '@/components/ui/UiButton.vue'

/** What the desktop sidebar and the phone drawer share (SPEC 7, 11). */
defineProps<{
  selected: PlainDate | null
  today: PlainDate | null
  weekStart: WeekStart
  locale: string
  readOnly: boolean
  showMiniMonth: boolean
}>()
const emit = defineEmits<{ select: [day: PlainDate]; newEvent: [] }>()

const { t } = useI18n()
const ui = useUiStore()
const confirm = useConfirmStore()
const toast = useToastStore()
const calendars = useQuery(calendarsQuery)
const tags = useQuery(tagsQuery)
const visibility = useCalendarVisibility()
const action = useSubmit()

const calendarDialog = ref(false)
const editingCalendar = ref<Calendar | null>(null)
const settingsOpen = ref(false)
const settingsFor = ref<number | null>(null)
const subscribeOpen = ref(false)
const tagDialog = ref(false)
const editingTag = ref<Tag | null>(null)

function newCalendar(): void {
  editingCalendar.value = null
  calendarDialog.value = true
}

function openSettings(calendar: Calendar): void {
  settingsFor.value = calendar.id
  settingsOpen.value = true
}

async function deleteCalendar(calendar: Calendar): Promise<void> {
  const sure = await confirm.ask({
    title: t('calendars.deleteTitle', { name: calendar.name }),
    message: t('calendars.deleteMessage'),
    confirmLabel: t('calendars.delete'),
    danger: true,
  })
  if (!sure) return
  if (!(await action.run(() => calendarApi.remove(calendar.id))) && action.error.value) {
    toast.show(action.error.value)
  }
}

function editTag(tag: Tag): void {
  editingTag.value = tag
  tagDialog.value = true
}

async function deleteTag(tag: Tag): Promise<void> {
  const sure = await confirm.ask({
    title: t('tags.deleteTitle', { name: tag.name }),
    message: t('tags.deleteMessage'),
    confirmLabel: t('tags.delete'),
    danger: true,
  })
  if (!sure) return
  if (await action.run(() => tagApi.remove(tag.id))) {
    ui.tagFilter = ui.tagFilter.filter((id) => id !== tag.id)
  } else if (action.error.value) {
    toast.show(action.error.value)
  }
}

const row = 'group flex min-h-9 items-center gap-2 pl-1 pointer-coarse:min-h-11 hover:bg-hover-tint'
</script>

<template>
  <div class="flex flex-col gap-6 p-4">
    <UiButton
      v-if="!readOnly"
      variant="primary"
      class="self-start"
      data-testid="new-event"
      @click="emit('newEvent')"
    >
      <Plus :size="16" /> {{ $t('shell.newEvent') }}
    </UiButton>

    <MonthGrid
      v-if="showMiniMonth && selected"
      :selected="selected"
      :today="today"
      :week-start="weekStart"
      :locale="locale"
      @select="emit('select', $event)"
    />

    <section class="flex flex-col gap-1" data-testid="calendar-list">
      <div class="flex items-center justify-between">
        <h2 class="text-label font-medium text-muted">{{ $t('shell.calendars') }}</h2>
        <DropdownMenuRoot v-if="!readOnly" :modal="false">
          <DropdownMenuTrigger
            :class="iconButton"
            class="size-8!"
            :aria-label="$t('calendars.add')"
            data-testid="add-calendar"
          >
            <Plus :size="16" />
          </DropdownMenuTrigger>
          <DropdownMenuPortal>
            <DropdownMenuContent :class="menuPanel" align="end" :side-offset="4">
              <DropdownMenuItem :class="menuItem" data-testid="new-calendar" @select="newCalendar">
                {{ $t('calendars.new') }}
              </DropdownMenuItem>
              <DropdownMenuItem
                :class="menuItem"
                data-testid="new-subscription"
                @select="subscribeOpen = true"
              >
                {{ $t('subscription.newTitle') }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenuRoot>
      </div>
      <ul>
        <li v-for="calendar in calendars.data.value" :key="calendar.id" :class="row">
          <label class="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 py-1">
            <input
              type="checkbox"
              class="peer sr-only"
              :checked="calendar.is_visible"
              :disabled="readOnly"
              @change="
                visibility.mutate({
                  id: calendar.id,
                  visible: ($event.target as HTMLInputElement).checked,
                })
              "
            />
            <span
              class="grid size-4 shrink-0 place-items-center border-2 text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink"
              :style="{
                borderColor: colorVar(calendar.color),
                background: calendar.is_visible ? colorVar(calendar.color) : 'transparent',
              }"
              aria-hidden="true"
            >
              <Check v-if="calendar.is_visible" :size="12" class="stroke-[2.6]!" />
            </span>
            <span class="truncate" :class="!calendar.is_visible && 'text-muted'">
              {{ calendar.name }}
            </span>
            <Rss
              v-if="calendar.subscription"
              :size="12"
              class="shrink-0 text-faint"
              :aria-label="$t('subscription.title')"
            />
            <CircleAlert
              v-if="calendar.subscription?.last_status === 'error'"
              :size="14"
              class="shrink-0 text-warning"
              :aria-label="$t('subscription.hasError')"
            />
          </label>
          <DropdownMenuRoot v-if="!readOnly" :modal="false">
            <DropdownMenuTrigger
              :class="iconButton"
              class="size-8! opacity-0 group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 pointer-coarse:opacity-100"
              :aria-label="$t('calendars.actions', { name: calendar.name })"
            >
              <EllipsisVertical :size="16" />
            </DropdownMenuTrigger>
            <DropdownMenuPortal>
              <DropdownMenuContent :class="menuPanel" align="end" :side-offset="4">
                <DropdownMenuItem :class="menuItem" @select="openSettings(calendar)">
                  {{ $t('calendars.settings') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  :class="[menuItem, 'text-danger']"
                  @select="deleteCalendar(calendar)"
                >
                  {{ $t('calendars.delete') }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenuPortal>
          </DropdownMenuRoot>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-1" data-testid="tag-list">
      <h2 class="text-label font-medium text-muted">{{ $t('shell.tags') }}</h2>
      <p v-if="!tags.data.value?.length" class="ui-meta">{{ $t('tags.empty') }}</p>
      <ul>
        <li v-for="tag in tags.data.value" :key="tag.id" :class="row">
          <button
            type="button"
            class="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 py-1 text-left"
            :aria-pressed="ui.tagFilter.includes(tag.id)"
            @click="ui.toggleTag(tag.id)"
          >
            <span
              class="cal-tag-marker"
              :class="ui.tagFilter.includes(tag.id) && 'outline-1 outline-offset-2 outline-ink'"
              :style="{ '--tag-color': colorVar(tag.color) }"
            />
            <span
              class="truncate"
              :class="ui.tagFilter.length > 0 && !ui.tagFilter.includes(tag.id) && 'text-muted'"
              >{{ tag.name }}</span
            >
          </button>
          <DropdownMenuRoot v-if="!readOnly" :modal="false">
            <DropdownMenuTrigger
              :class="iconButton"
              class="size-8! opacity-0 group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 pointer-coarse:opacity-100"
              :aria-label="$t('tags.actions', { name: tag.name })"
            >
              <EllipsisVertical :size="16" />
            </DropdownMenuTrigger>
            <DropdownMenuPortal>
              <DropdownMenuContent :class="menuPanel" align="end" :side-offset="4">
                <DropdownMenuItem :class="menuItem" @select="editTag(tag)">
                  {{ $t('tags.edit') }}
                </DropdownMenuItem>
                <DropdownMenuItem :class="[menuItem, 'text-danger']" @select="deleteTag(tag)">
                  {{ $t('tags.delete') }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenuPortal>
          </DropdownMenuRoot>
        </li>
      </ul>
      <button
        v-if="ui.tagFilter.length"
        type="button"
        class="self-start text-label text-accent"
        @click="ui.tagFilter = []"
      >
        {{ $t('tags.clearFilter') }}
      </button>
    </section>
    <CalendarDialog v-model:open="calendarDialog" :calendar="editingCalendar" />
    <CalendarSettings v-model:open="settingsOpen" :calendar-id="settingsFor" />
    <SubscribeDialog v-model:open="subscribeOpen" />
    <TagDialog v-model:open="tagDialog" :tag="editingTag" />
  </div>
</template>
