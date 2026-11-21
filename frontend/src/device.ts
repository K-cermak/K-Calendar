/** The device's IANA zone, as the browser reports it. Only ever sent to the server or compared. */
export function deviceTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    return undefined
  }
}
