import { defineStore } from 'pinia'
import { ref } from 'vue'

/** View state that belongs to this browser tab only (SPEC 11): never saved on the server. */
export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(true)
  const drawerOpen = ref(false)
  const tagFilter = ref<number[]>([])

  function toggleTag(id: number): void {
    tagFilter.value = tagFilter.value.includes(id)
      ? tagFilter.value.filter((tag) => tag !== id)
      : [...tagFilter.value, id]
  }

  return { sidebarOpen, drawerOpen, tagFilter, toggleTag }
})
