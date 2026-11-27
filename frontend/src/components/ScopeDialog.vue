<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  AlertDialogContent,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import { useScopeStore, type Scope } from '@/stores/scope'
import UiButton from '@/components/ui/UiButton.vue'

const store = useScopeStore()
const choice = ref<Scope>('this')

watch(
  () => store.request,
  (request) => {
    if (request) choice.value = request.allowThis ? 'this' : 'following'
  },
)
</script>

<template>
  <AlertDialogRoot
    :open="store.request !== null"
    @update:open="(open) => !open && store.answer(null)"
  >
    <AlertDialogPortal>
      <!-- Above the editor's sheet (z 50), which a dialog asked from it has to cover. -->
      <AlertDialogOverlay class="ui-overlay z-60" />
      <AlertDialogContent v-if="store.request" class="ui-dialog z-60" data-testid="scope-dialog">
        <AlertDialogTitle class="ui-dialog__title">
          {{ $t(`scope.${store.request.action}Title`) }}
        </AlertDialogTitle>
        <div class="flex flex-col gap-3" role="radiogroup">
          <label
            v-for="scope in ['this', 'following', 'all'] as const"
            :key="scope"
            class="flex cursor-pointer items-center gap-3"
            :class="scope === 'this' && !store.request.allowThis && 'cursor-not-allowed text-faint'"
          >
            <input
              v-model="choice"
              type="radio"
              class="ui-radio"
              :value="scope"
              :disabled="scope === 'this' && !store.request.allowThis"
            />
            {{ $t(`scope.${scope}`) }}
          </label>
        </div>
        <!-- Plain buttons: Reka's Action and Cancel close the dialog before the click handler runs. -->
        <div class="ui-dialog__actions">
          <UiButton @click="store.answer(null)">{{ $t('common.cancel') }}</UiButton>
          <UiButton
            :variant="store.request.action === 'delete' ? 'danger' : 'primary'"
            data-testid="scope-confirm"
            @click="store.answer(choice)"
          >
            {{ $t(store.request.action === 'delete' ? 'event.delete' : 'common.save') }}
          </UiButton>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
