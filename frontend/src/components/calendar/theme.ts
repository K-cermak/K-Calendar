import type { PluginInput } from '@fullcalendar/vue3'

/*
 * The grid's look, as a FullCalendar theme: v7 renders unstyled parts and asks for class names.
 * Every class maps to styles/fullcalendar.css, which uses the design tokens only (SPEC 11).
 */
type Info = Record<string, unknown>
const cx = (...parts: (string | false | null | undefined)[]): string =>
  parts.filter(Boolean).join(' ')

const resizer = (info: Info, axis: 'row' | 'column', side: 'start' | 'end'): string => {
  const resizable = side === 'start' ? info.isStartResizable : info.isEndResizable
  if (!resizable) return ''
  return cx('cal-fc-resizer', `cal-fc-resizer--${axis}-${side}`, !!info.isSelected && 'is-touch')
}

export const calendarTheme = {
  name: 'theme-calendar',
  optionDefaults: {
    className: 'cal-fc',
    viewClass: 'cal-fc-view',
    eventClass: (info: Info) =>
      cx('cal-fc-event', !!info.isDragging && 'is-dragging', !!info.isSelected && 'is-selected'),
    blockEventClass: 'cal-fc-block-event',
    blockEventInnerClass: 'cal-fc-block-event__inner',
    rowEventClass: (info: Info) =>
      cx('cal-fc-row-event', !!info.isStart && 'is-start', !!info.isEnd && 'is-end'),
    rowEventBeforeClass: (info: Info) => resizer(info, 'row', 'start'),
    rowEventAfterClass: (info: Info) => resizer(info, 'row', 'end'),
    rowEventInnerClass: 'cal-fc-fill',
    columnEventClass: 'cal-fc-column-event',
    columnEventBeforeClass: (info: Info) => resizer(info, 'column', 'start'),
    columnEventAfterClass: (info: Info) => resizer(info, 'column', 'end'),
    columnEventInnerClass: 'cal-fc-fill',
    listItemEventClass: 'cal-fc-row-event is-start is-end',
    listItemEventInnerClass: 'cal-fc-fill',
    moreLinkClass: 'cal-fc-more',
    rowMoreLinkClass: 'cal-fc-more cal-fc-more--row',
    columnMoreLinkClass: 'cal-fc-more cal-fc-more--column',
    dayHeaderAlign: 'center',
    dayHeaderClass: (info: Info) => cx('cal-fc-day-header', !!info.inPopover && 'in-popover'),
    dayHeaderInnerClass: 'cal-fc-day-header__inner',
    dayHeaderDividerClass: 'cal-fc-divider-bottom',
    dayHeaderRowClass: 'cal-fc-row',
    dayRowClass: 'cal-fc-row',
    dayCellClass: (info: Info) => cx('cal-fc-cell', !!info.isOther && 'is-other'),
    dayCellTopClass: 'cal-fc-cell__top',
    dayCellTopInnerClass: (info: Info) =>
      cx('cal-fc-day-number', !!info.isToday && 'is-today', !!info.isOther && 'is-other'),
    dayCellBottomClass: 'cal-fc-cell__bottom',
    dayLaneClass: 'cal-fc-lane',
    dayLaneInnerClass: (info: Info) =>
      info.isStack ? 'cal-fc-lane__inner--stack' : 'cal-fc-lane__inner',
    slotLaneClass: (info: Info) => cx('cal-fc-slot', !!info.isMinor && 'is-minor'),
    slotHeaderClass: (info: Info) => cx('cal-fc-slot-header', !!info.isMinor && 'is-minor'),
    slotHeaderInnerClass: 'cal-fc-slot-header__inner',
    slotHeaderRowClass: 'cal-fc-row',
    slotHeaderDividerClass: 'cal-fc-divider-end',
    allDayHeaderClass: 'cal-fc-all-day-header',
    allDayHeaderInnerClass: 'cal-fc-all-day-header__inner',
    allDayDividerClass: 'cal-fc-divider-all-day',
    nowIndicatorLineClass: 'cal-fc-now-line',
    nowIndicatorHeaderClass: 'cal-fc-now-header',
    popoverClass: 'cal-fc-popover',
    popoverCloseClass: 'cal-fc-popover__close',
    highlightClass: 'cal-fc-highlight',
    fillerClass: 'cal-fc-filler',
    tableHeaderClass: 'cal-fc-table-header',
    navLinkClass: 'cal-fc-nav-link',
  },
} as unknown as PluginInput
