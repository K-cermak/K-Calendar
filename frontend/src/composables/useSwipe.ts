import { onScopeDispose, watch, type Ref } from 'vue'

const MIN_DISTANCE = 60
const MAX_DRIFT = 40
const MAX_DURATION_MS = 600

/**
 * Calls back with -1 or 1 after a quick horizontal swipe (right means back). Slow or vertical
 * movements are scrolling, and a long press starts a drag in the grid, so neither counts.
 */
export function useSwipe(target: Ref<HTMLElement | null>, onSwipe: (direction: -1 | 1) => void) {
  let start: { x: number; y: number; time: number } | null = null

  const down = (e: TouchEvent) => {
    const touch = e.touches[0]
    start =
      e.touches.length === 1 && touch
        ? { x: touch.clientX, y: touch.clientY, time: Date.now() }
        : null
  }
  const up = (e: TouchEvent) => {
    const touch = e.changedTouches[0]
    if (!start || !touch) return
    const dx = touch.clientX - start.x
    const dy = touch.clientY - start.y
    const quick = Date.now() - start.time < MAX_DURATION_MS
    start = null
    if (quick && Math.abs(dx) >= MIN_DISTANCE && Math.abs(dy) <= MAX_DRIFT) onSwipe(dx < 0 ? 1 : -1)
  }

  const stop = watch(
    target,
    (element, _old, onCleanup) => {
      if (!element) return
      element.addEventListener('touchstart', down, { passive: true })
      element.addEventListener('touchend', up, { passive: true })
      onCleanup(() => {
        element.removeEventListener('touchstart', down)
        element.removeEventListener('touchend', up)
      })
    },
    { immediate: true },
  )
  onScopeDispose(stop)
}
