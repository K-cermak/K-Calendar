import { MONDAY, expect, test } from './helpers'

test('the sign-in page shows the version from /config', async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  const config = (await (await page.request.get('/api/v1/config')).json()) as { version: string }
  await page.goto('/login')
  await expect(page.getByTestId('version')).toContainText(config.version)
  await context.close()
})

test('client routes survive a reload', async ({ page }) => {
  await page.goto(`/month/${MONDAY}`)
  await expect(page.getByTestId('calendar-area')).toBeVisible()
  await page.reload()
  await expect(page).toHaveURL(new RegExp(`/month/${MONDAY}$`))
  await expect(page.getByTestId('calendar-area')).toBeVisible()
})

test('pages are served with a strict content security policy', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  const response = await page.goto(`/week/${MONDAY}`)
  expect(response?.headers()['content-security-policy']).toContain("script-src 'self'")
  await expect(page.getByTestId('calendar-area')).toBeVisible()
  expect(errors.filter((e) => e.includes('Content Security Policy'))).toEqual([])
})
