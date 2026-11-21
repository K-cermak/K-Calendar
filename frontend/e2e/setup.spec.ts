import { expect, test } from '@playwright/test'
import { admin } from './helpers'

test('first-run setup creates the admin, who can sign out and back in', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/setup$/)
  await page.locator('#account-name').fill(admin.name)
  await page.locator('#account-email').fill(admin.email)
  await page.locator('#account-password').fill(admin.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByTestId('calendar-area')).toBeVisible()

  await page.getByTestId('account-menu').click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)

  await page.locator('#login-email').fill(admin.email)
  await page.locator('#login-password').fill('not-the-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('not correct')

  await page.locator('#login-password').fill(admin.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByTestId('calendar-area')).toBeVisible()
  // Setup is done once: the page now sends people to sign in instead.
  await page.goto('/setup')
  await expect(page).not.toHaveURL(/\/setup$/)
})
