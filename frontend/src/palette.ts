/** The keys of the shared calendar, event and tag palette in styles/palette.css (SPEC 11). */
export const PALETTE = [
  'red',
  'orange',
  'amber',
  'lime',
  'green',
  'teal',
  'cyan',
  'blue',
  'indigo',
  'violet',
  'pink',
  'brown',
  'graphite',
] as const

export type PaletteColor = (typeof PALETTE)[number]

export function colorVar(color: string): string {
  return `var(--cal-${color})`
}
