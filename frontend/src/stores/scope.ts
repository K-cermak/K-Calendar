import { defineStore } from 'pinia'
import { shallowRef } from 'vue'

export type Scope = 'this' | 'following' | 'all'
export type ScopeAction = 'edit' | 'delete' | 'move'

export interface ScopeRequest {
  action: ScopeAction
  allowThis: boolean
  resolve: (scope: Scope | null) => void
}

/** Asks which occurrences of a series a change applies to (SPEC 5); null means cancelled. */
export const useScopeStore = defineStore('scope', () => {
  const request = shallowRef<ScopeRequest | null>(null)

  function ask(action: ScopeAction, allowThis = true): Promise<Scope | null> {
    request.value?.resolve(null)
    return new Promise((resolve) => {
      request.value = { action, allowThis, resolve }
    })
  }

  function answer(scope: Scope | null): void {
    request.value?.resolve(scope)
    request.value = null
  }

  return { request, ask, answer }
})
