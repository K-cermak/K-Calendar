import { createHmac } from 'node:crypto'
import { MONDAY, admin, expect, openGrid, test } from './helpers'
import { createEvent } from './api'

/** RFC 6238 TOTP for a base32 secret, as an authenticator app computes it. */
function totp(secret: string, at = Date.now()): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const char of secret.replace(/=+$/, '')) {
    bits += alphabet.indexOf(char).toString(2).padStart(5, '0')
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)))
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30_000)))
  const hash = createHmac('sha1', key).update(counter).digest()
  const offset = hash[hash.length - 1] & 0xf
  const value = (hash.readUInt32BE(offset) & 0x7fffffff) % 1_000_000
  return value.toString().padStart(6, '0')
}

test('two-step verification is set up in settings and asked for at sign-in', async ({
  page,
  user,
  browser,
}) => {
  await page.goto('/settings/security')
  await page.getByTestId('totp-start').click()
  const secret = (await page.getByTestId('totp-secret').textContent())!.trim()
  await page.getByLabel('Enter the 6-digit code it shows').fill(totp(secret))
  await page.getByRole('button', { name: 'Turn on' }).click()
  const codes = page.getByTestId('recovery-codes').getByRole('listitem')
  await expect(codes).toHaveCount(10)
  const recovery = (await codes.first().textContent())!.trim()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.getByTestId('totp-settings')).toContainText('10 recovery codes left')

  // A fresh browser needs the password and then a code; a recovery code does too.
  const context = await browser.newContext()
  const login = await context.newPage()
  await login.goto('/login')
  await login.locator('#login-email').fill(user.email)
  await login.locator('#login-password').fill(user.password)
  await login.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(login.getByTestId('totp-step')).toBeVisible()
  await login.getByLabel('Code').fill('000000')
  await login.getByRole('button', { name: 'Verify' }).click()
  await expect(login.getByRole('alert')).toContainText('The code is not correct')
  await login.getByLabel('Code').fill(recovery)
  await login.getByRole('button', { name: 'Verify' }).click()
  await expect(login.getByTestId('calendar-area')).toBeVisible()
  await context.close()
})

test('a read token lists calendars and is refused when it writes or touches tokens', async ({
  page,
  browser,
}) => {
  await page.goto('/settings/tokens')
  const docs = page.getByTestId('api-docs')
  expect((await page.request.get((await docs.getAttribute('href'))!)).status()).toBe(200)
  await page.getByLabel('Name').fill('Reader')
  await page.getByRole('button', { name: 'Create token' }).click()
  const token = await page.getByTestId('new-token').getByRole('textbox').inputValue()
  expect(token).toMatch(/^cal_/)
  await expect(page.getByTestId('tokens')).toContainText('Reader')

  // A bare client, as curl would be: no cookies, only the token.
  const bare = await browser.newContext()
  const headers = { Authorization: `Bearer ${token}` }
  const list = await bare.request.get('/api/v1/calendars', { headers })
  expect(list.status()).toBe(200)
  const write = await bare.request.post('/api/v1/calendars', {
    headers,
    data: { name: 'x', color: 'blue' },
  })
  expect(write.status()).toBe(403)
  const tokens = await bare.request.get('/api/v1/me/tokens', { headers })
  expect(tokens.status()).toBe(403)
  await bare.close()

  await page.getByRole('button', { name: 'Revoke' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Revoke' }).click()
  await expect(page.getByTestId('tokens')).toHaveCount(0)
})

test('an admin deactivates a user, who is then signed out', async ({ page, user, browser }) => {
  const context = await browser.newContext()
  const adminPage = await context.newPage()
  await adminPage.goto('/login')
  await adminPage.locator('#login-email').fill(admin.email)
  await adminPage.locator('#login-password').fill(admin.password)
  await adminPage.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(adminPage.getByTestId('calendar-area')).toBeVisible()
  await adminPage.goto('/admin')
  const row = adminPage.getByRole('listitem').filter({ hasText: user.email })
  await row.getByTestId('user-actions').click()
  await adminPage.getByRole('menuitem', { name: 'Create password reset link' }).click()
  await expect(adminPage.getByTestId('reset-link').getByRole('textbox')).toHaveValue(/\/reset\//)
  await row.getByTestId('user-actions').click()
  await adminPage.getByRole('menuitem', { name: 'Deactivate' }).click()
  await expect(row).toContainText('Deactivated')

  const me = await page.request.get('/api/v1/me')
  expect(me.status()).toBe(401)
  await context.close()
})

test('a user deletes their own account', async ({ page, user }) => {
  await page.goto('/settings/security')
  const section = page.getByTestId('delete-account')
  await section.getByRole('button', { name: 'Delete account' }).click()
  await section.getByLabel('Password').fill(user.password)
  await section.getByRole('button', { name: 'Delete account' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete account' }).click()
  await expect(page).toHaveURL(/\/login$/)

  const login = await page.request.post('/api/v1/auth/login', {
    data: { email: user.email, password: user.password },
  })
  expect(login.status()).toBe(401)
})

test('the theme chosen in the account menu is saved and follows the user', async ({
  page,
  user,
  browser,
}) => {
  await page.goto('/')
  await expect(page.getByTestId('calendar-area')).toBeVisible()
  await page.getByTestId('account-menu').click()
  await page.getByTestId('theme-dark').click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  const context = await browser.newContext()
  const other = await context.newPage()
  const login = await other.request.post('/api/v1/auth/login', {
    data: { email: user.email, password: user.password },
  })
  expect(login.ok()).toBe(true)
  await other.goto('/')
  await expect(other.getByTestId('calendar-area')).toBeVisible()
  await expect(other.locator('html')).toHaveAttribute('data-theme', 'dark')
  await context.close()
})

test('a time zone is found by typing any part of its name', async ({ page }) => {
  await page.goto('/settings/profile')
  const field = page.getByTestId('timezone-input')
  await field.click()
  const list = page.getByRole('listbox')
  await expect(list.getByRole('option', { name: 'Europe/Prague' })).toBeInViewport()
  await field.fill('new york')
  await expect(list.getByRole('option')).toHaveCount(1)
  await list.getByRole('option', { name: 'America/New_York' }).click()
  await expect(field).toHaveValue('America/New_York')

  await expect
    .poll(async () => (await (await page.request.get('/api/v1/me')).json()).timezone)
    .toBe('America/New_York')
})

test('tag markers on events can be turned off in the profile', async ({ page }) => {
  const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)
  const event = await createEvent(page, {
    title: 'Flight',
    start: `${tomorrow}T09:00:00`,
    end: `${tomorrow}T10:00:00`,
    tags: ['travel'],
  })
  const row = page.getByTestId(`agenda-${event.id}`)
  await page.goto('/agenda')
  await expect(row.locator('.cal-tag-marker')).toHaveCount(1)

  await page.goto('/settings/profile')
  await page.getByTestId('show-event-tags').click()
  await expect(page.getByTestId('show-event-tags')).toHaveAttribute('data-state', 'unchecked')
  await page.goto('/agenda')
  await expect(row).toBeVisible()
  await expect(row.locator('.cal-tag-marker')).toHaveCount(0)
})

test('working hours with a break shade the rest of the day in the grid', async ({
  page,
  isMobile,
}) => {
  await openGrid(page, isMobile, MONDAY)
  await expect(page.locator('.cal-fc-off-hours')).toHaveCount(0)

  await page.goto('/settings/profile')
  const section = page.getByTestId('working-hours')
  await section.getByTestId('working-hours-enabled').click()
  const monday = section.getByTestId('working-monday')
  await monday.getByLabel('Monday, until').fill('12:00')
  await monday.getByRole('button', { name: 'Add time' }).click()
  await monday.getByLabel('Monday, from').nth(1).fill('11:00')
  await monday.getByLabel('Monday, until').nth(1).fill('17:00')
  await expect(section.getByText('must not overlap')).toBeVisible()
  await expect(section.getByTestId('working-hours-save')).toBeDisabled()
  await monday.getByLabel('Monday, from').nth(1).fill('13:00')
  await section.getByTestId('working-hours-save').click()
  await expect(section.getByTestId('working-hours-save')).toBeDisabled()

  const me = (await (await page.request.get('/api/v1/me')).json()) as {
    working_hours: { monday: { start: string; end: string }[] }
  }
  expect(me.working_hours.monday).toEqual([
    { start: '09:00', end: '12:00' },
    { start: '13:00', end: '17:00' },
  ])
  await openGrid(page, isMobile, MONDAY)
  await expect(page.locator('.cal-fc-off-hours').first()).toBeAttached()
})
