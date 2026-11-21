import { ref } from 'vue'

const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
let listening = false

/** Whether the browser has a network. Offline the app is read-only (SPEC 12). */
export function useOnline() {
  if (!listening && typeof window !== 'undefined') {
    listening = true
    const update = () => (online.value = navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
  }
  return online
}
