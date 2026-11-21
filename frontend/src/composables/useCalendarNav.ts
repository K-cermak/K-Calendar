import { computed, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { parseDate, shift, type PlainDate, type PlainDateTime } from '@/dates'
import { VIEWS, type CalendarView } from '@/router'

/** The view and date in the URL (/:view/:date?), and moving between ranges (SPEC 11). */
export function useCalendarNav(
  defaultView: Ref<CalendarView>,
  now: Ref<PlainDateTime | null>,
  compact: Ref<boolean>,
) {
  const route = useRoute()
  const router = useRouter()

  const view = computed<CalendarView>(
    () => VIEWS.find((v) => v === route.params.view) ?? defaultView.value,
  )
  const today = computed<PlainDate | null>(() => now.value?.toPlainDate() ?? null)
  const anchor = computed<PlainDate | null>(() => {
    const fromRoute = route.params.date
    if (typeof fromRoute === 'string' && fromRoute) {
      try {
        return parseDate(fromRoute)
      } catch {
        return today.value
      }
    }
    return today.value
  })

  function go(nextView: CalendarView, date: PlainDate | null, replace = false): void {
    const isToday = !date || (today.value && date.equals(today.value))
    const target = {
      name: 'calendar',
      params: { view: nextView, date: isToday ? undefined : date.toString() },
    }
    void (replace ? router.replace(target) : router.push(target))
  }

  return {
    view,
    anchor,
    today,
    setView: (next: CalendarView) => go(next, anchor.value),
    goToday: () => go(view.value, null),
    goTo: (date: PlainDate, nextView: CalendarView = view.value) => go(nextView, date),
    step: (direction: -1 | 1) => {
      if (anchor.value) go(view.value, shift(view.value, anchor.value, direction, compact.value))
    },
  }
}
