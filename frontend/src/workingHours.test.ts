import { describe, expect, it } from 'vitest'
import type { WorkingHours } from '@/api/client'
import { dayIsInvalid, nextInterval, orderedDays, toBusinessHours } from './workingHours'

const none = {
  monday: [],
  tuesday: [],
  wednesday: [],
  thursday: [],
  friday: [],
  saturday: [],
  sunday: [],
} satisfies WorkingHours

describe('working hours', () => {
  it('numbers the days from Sunday for the grid, one entry per interval', () => {
    const hours: WorkingHours = {
      ...none,
      monday: [
        { start: '08:00', end: '12:00' },
        { start: '13:00', end: '16:30' },
      ],
      sunday: [{ start: '10:00', end: '11:00' }],
    }
    expect(toBusinessHours(hours)).toEqual([
      { daysOfWeek: [1], startTime: '08:00', endTime: '12:00' },
      { daysOfWeek: [1], startTime: '13:00', endTime: '16:30' },
      { daysOfWeek: [0], startTime: '10:00', endTime: '11:00' },
    ])
  })

  it('orders the days by the start of the week', () => {
    expect(orderedDays('monday')[0]).toBe('monday')
    expect(orderedDays('sunday')).toEqual([
      'sunday',
      'monday',
      'tuesday',
      'wednesday',
      'thursday',
      'friday',
      'saturday',
    ])
  })

  it('finds backward and overlapping times, but not back-to-back ones', () => {
    expect(dayIsInvalid([{ start: '12:00', end: '09:00' }])).toBe(true)
    expect(
      dayIsInvalid([
        { start: '13:00', end: '17:00' },
        { start: '09:00', end: '13:30' },
      ]),
    ).toBe(true)
    expect(
      dayIsInvalid([
        { start: '13:00', end: '17:00' },
        { start: '09:00', end: '13:00' },
      ]),
    ).toBe(false)
    expect(dayIsInvalid([{ start: '', end: '10:00' }])).toBe(true)
  })

  it('adds office hours to an empty day and the next hour after the last time', () => {
    expect(nextInterval([])).toEqual({ start: '09:00', end: '17:00' })
    expect(nextInterval([{ start: '09:00', end: '12:00' }])).toEqual({
      start: '12:00',
      end: '13:00',
    })
    expect(nextInterval([{ start: '20:00', end: '23:30' }])).toEqual({
      start: '23:30',
      end: '23:59',
    })
    expect(nextInterval([{ start: '20:00', end: '23:59' }])).toBeNull()
  })
})
