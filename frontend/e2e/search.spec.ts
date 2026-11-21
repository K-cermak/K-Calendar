import { createEvent } from './api'
import { MONDAY, expect, test } from './helpers'

test('search ignores accents and opens the event it finds', async ({ page, isMobile }) => {
  await createEvent(page, {
    title: 'Zubař',
    start: `${MONDAY}T08:00:00`,
    end: `${MONDAY}T08:30:00`,
    location: 'Brno',
  })
  await createEvent(page, { title: 'Gym', start: `${MONDAY}T18:00:00`, end: `${MONDAY}T19:00:00` })
  await page.goto('/')
  if (isMobile) await page.getByTestId('search-open').click()
  await page.getByTestId('search-input').fill('zubar')
  const results = page.getByTestId('search-results')
  await expect(results.getByRole('option')).toHaveCount(1)
  await expect(results.getByRole('option')).toContainText('Zubař')
  await results.getByRole('option').click()
  // The event's address gives way to the day it is on, with its details open.
  await expect(page).toHaveURL(new RegExp(MONDAY))
  await expect(page.getByTestId('event-detail')).toContainText('Brno')
})
