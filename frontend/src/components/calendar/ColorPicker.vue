<script setup lang="ts">
import { Check } from '@lucide/vue'
import type { PaletteColor } from '@/api/client'
import { PALETTE, colorVar } from '@/palette'

defineProps<{ label: string; allowNone?: boolean }>()
const model = defineModel<PaletteColor | null>({ required: true })
</script>

<template>
  <div role="radiogroup" :aria-label="label" class="flex flex-wrap gap-1.5">
    <button
      v-if="allowNone"
      type="button"
      role="radio"
      :aria-checked="model === null"
      :aria-label="$t('palette.none')"
      :title="$t('palette.none')"
      class="grid size-7 cursor-pointer place-items-center border border-line text-muted"
      @click="model = null"
    >
      <Check v-if="model === null" :size="14" />
    </button>
    <button
      v-for="color in PALETTE"
      :key="color"
      type="button"
      role="radio"
      :aria-checked="model === color"
      :aria-label="$t(`palette.${color}`)"
      :title="$t(`palette.${color}`)"
      class="grid size-7 cursor-pointer place-items-center text-on-accent"
      :style="{ background: colorVar(color) }"
      @click="model = color"
    >
      <Check v-if="model === color" :size="14" class="stroke-[2.4]!" />
    </button>
  </div>
</template>
