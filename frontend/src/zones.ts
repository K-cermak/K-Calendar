/** The IANA zone names the browser knows, with `current` first if the browser lacks it. */
export function timeZones(current?: string | null): string[] {
  const known = Intl.supportedValuesOf('timeZone')
  return current && !known.includes(current) ? [current, ...known] : known
}

// Zone names spell spaces as underscores and nest with slashes; people type "new york".
function fold(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLocaleLowerCase()
    .replace(/[_/\s]+/g, ' ')
    .trim()
}

/** The zones whose name contains `query` anywhere, ignoring case, accents and underscores. */
export function matchZones(zones: string[], query: string): string[] {
  const needle = fold(query)
  return needle ? zones.filter((zone) => fold(zone).includes(needle)) : zones
}
