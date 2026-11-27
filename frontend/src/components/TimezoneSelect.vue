<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ComboboxAnchor,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxPortal,
  ComboboxRoot,
  ComboboxViewport,
} from 'reka-ui'
import { Check } from '@lucide/vue'
import { matchZones, timeZones } from '@/zones'

/**
 * A time zone picker that searches as the user types. A native select lists all ~400 zones in a
 * menu as tall as the screen and finds them only by their first letters.
 */
defineProps<{ id: string }>()
const model = defineModel<string>({ required: true })

const query = ref('')
const zones = computed(() => timeZones(model.value))
// Opening the list shows the zone's own name in the field; only typing narrows the list.
const shown = computed(() =>
  query.value === model.value ? zones.value : matchZones(zones.value, query.value),
)
</script>

<template>
  <ComboboxRoot v-model="model" ignore-filter open-on-click>
    <ComboboxAnchor class="w-80 max-w-full">
      <ComboboxInput
        :id="id"
        v-model="query"
        class="ui-select w-full! cursor-text!"
        :display-value="(zone: string) => zone"
        autocomplete="off"
        spellcheck="false"
        data-testid="timezone-input"
      />
    </ComboboxAnchor>
    <ComboboxPortal>
      <ComboboxContent
        position="popper"
        :side-offset="4"
        :collision-padding="12"
        class="ui-panel w-(--reka-combobox-trigger-width)"
      >
        <ComboboxViewport class="max-h-72 overflow-y-auto py-1">
          <ComboboxEmpty class="px-3 py-2 text-label text-muted">
            {{ $t('common.noTimezone') }}
          </ComboboxEmpty>
          <ComboboxItem
            v-for="zone in shown"
            :key="zone"
            :value="zone"
            class="ui-menu-item h-9! justify-between"
          >
            {{ zone }}
            <ComboboxItemIndicator><Check :size="16" /></ComboboxItemIndicator>
          </ComboboxItem>
        </ComboboxViewport>
      </ComboboxContent>
    </ComboboxPortal>
  </ComboboxRoot>
</template>
