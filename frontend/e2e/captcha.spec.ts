import { expect, test } from '@playwright/test'
import { admin } from './helpers'

// A captcha applies to every sign-in on the instance, so this project runs after all the others
// (playwright.config.ts). ALTCHA is the one provider that works without the internet.

test('with ALTCHA on, signing in needs the solved check', async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  const signIn = await page.request.post('/api/v1/auth/login', {
    data: { email: admin.email, password: admin.password },
  })
  expect(signIn.ok()).toBe(true)
  await page.goto('/admin')
  const section = page.getByTestId('captcha-settings')
  await section.getByLabel('Captcha', { exact: true }).selectOption('altcha')
  await section.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByTestId('toast')).toContainText('Changes saved')
  try {
    const visitor = await browser.newContext()
    const login = await visitor.newPage()
    await login.goto('/login')

    const refused = await visitor.request.post('/api/v1/auth/login', {
      data: { email: admin.email, password: admin.password },
    })
    expect(refused.status()).toBe(400)

    const widget = login.frameLocator('[data-testid=captcha-frame]').locator('altcha-widget')
    await expect(widget).toContainText('Verified')
    await login.locator('#login-email').fill(admin.email)
    await login.locator('#login-password').fill(admin.password)
    await login.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(login.getByTestId('calendar-area')).toBeVisible()
    await visitor.close()
  } finally {
    // Through the API, so it works even when the test failed halfway.
    const off = await context.request.put('/api/v1/admin/captcha', {
      data: { provider: 'none', placement: 'both' },
    })
    expect(off.ok()).toBe(true)
    await context.close()
  }
})
