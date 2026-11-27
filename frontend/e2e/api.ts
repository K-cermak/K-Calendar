import { expect, type Page } from '@playwright/test'

/** Setting up data through the API, for tests about something other than creating it. */
export async function createEvent(
  page: Page,
  fields: {
    title: string
    start: string
    end: string
    location?: string
    tags?: string[]
    rrule?: string
  },
): Promise<{ id: number }> {
  const calendars = (await (await page.request.get('/api/v1/calendars')).json()) as {
    id: number
  }[]
  const response = await page.request.post('/api/v1/events', {
    data: { calendar_id: calendars[0].id, ...fields },
  })
  expect(response.status()).toBe(201)
  return (await response.json()) as { id: number }
}
