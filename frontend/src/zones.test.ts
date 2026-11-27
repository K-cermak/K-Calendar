import { describe, expect, it } from 'vitest'
import { matchZones, timeZones } from './zones'

const ZONES = ['America/New_York', 'Europe/Prague', 'Europe/Paris', 'Asia/Ho_Chi_Minh', 'UTC']

describe('time zones', () => {
  it('finds a zone by any part of its name', () => {
    expect(matchZones(ZONES, 'prag')).toEqual(['Europe/Prague'])
    expect(matchZones(ZONES, 'RAGUE')).toEqual(['Europe/Prague'])
    expect(matchZones(ZONES, 'europe/pa')).toEqual(['Europe/Paris'])
  })

  it('reads spaces as the underscores and slashes in zone names', () => {
    expect(matchZones(ZONES, 'new york')).toEqual(['America/New_York'])
    expect(matchZones(ZONES, 'america new')).toEqual(['America/New_York'])
    expect(matchZones(ZONES, 'hồ chí')).toEqual(['Asia/Ho_Chi_Minh'])
  })

  it('lists every zone for an empty query', () => {
    expect(matchZones(ZONES, '  ')).toEqual(ZONES)
  })

  it('keeps a zone the browser does not know', () => {
    expect(timeZones('Mars/Olympus')[0]).toBe('Mars/Olympus')
    expect(timeZones('Europe/Prague')).toEqual(Intl.supportedValuesOf('timeZone'))
  })
})
