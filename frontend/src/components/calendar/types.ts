import type { EventDetail, Occurrence } from '@/api/client'
import type { Draft } from '@/eventDraft'

/** A span picked on the grid, as wall-clock values in the display zone. */
export interface GridSpan {
  start: string
  end: string
  allDay: boolean
}

export interface GridChange extends GridSpan {
  occurrence: Occurrence
  revert: () => void
}

export type EditorTarget = { kind: 'create'; draft: Draft } | { kind: 'edit'; event: EventDetail }
