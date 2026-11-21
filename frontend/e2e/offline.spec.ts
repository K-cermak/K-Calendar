import { createEvent } from './api'
import { MONDAY, eventBlock, expect, openGrid, test } from './helpers'

test('offline, the loaded calendar stays readable and editing is off', async ({
  page,
  context,
  isMobile,
}) => {
  await createEvent(page, {
    title: 'Train to Vienna',
    start: `${MONDAY}T07:00:00`,
    end: `${MONDAY}T09:00:00`,
  })
  await openGrid(page, isMobile, MONDAY)
  await page.evaluate(() => navigator.serviceWorker.ready)
  // Load once more under the service worker, so it has the app and the occurrences cached.
  await page.reload()
  await expect(eventBlock(page, 'Train to Vienna')).toBeVisible()
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByTestId('offline-banner')).toBeVisible()
  await expect(eventBlock(page, 'Train to Vienna')).toBeVisible()
  await expect(page.getByTestId(isMobile ? 'fab' : 'new-event')).toHaveCount(0)

  await eventBlock(page, 'Train to Vienna').click()
  await expect(page.getByTestId('event-detail')).toContainText('Train to Vienna')
  await expect(page.getByTestId('detail-edit')).toHaveCount(0)

  await context.setOffline(false)
  await expect(page.getByTestId('offline-banner')).toHaveCount(0)
})
