import { admin, expect, test } from './helpers'

// The limits apply to the whole instance while other tests run in parallel, so this one runs in
// one project only, and puts the sign-in length back, which no other test depends on.
test('an admin sets the sign-in length under Limits', async ({ page, isMobile }) => {
  test.skip(isMobile, 'An instance setting; once is enough.')
  const login = await page.request.post('/api/v1/auth/login', {
    data: { email: admin.email, password: admin.password },
  })
  expect(login.ok()).toBe(true)
  await page.goto('/admin')
  const form = page.getByTestId('instance-limits')
  const save = form.getByRole('button', { name: 'Save' })
  const days = form.getByLabel('Sign people out after inactivity (days)')
  await expect(days).toHaveValue('180')

  await days.fill('0')
  await save.click()
  await expect(form).toContainText('Enter a whole number from 1 to 3650.')

  await days.fill('90')
  await save.click()
  await expect(page.getByTestId('toast')).toContainText('Changes saved')
  await page.reload()
  await expect(days).toHaveValue('90')

  await days.fill('180')
  await save.click()
  await expect(days).toHaveValue('180')
  // The field shows the value at once; the server has it only when the request is done.
  await expect
    .poll(
      async () =>
        (
          (await (await page.request.get('/api/v1/admin/settings')).json()) as {
            session_days: number
          }
        ).session_days,
    )
    .toBe(180)
})

// Like the limits, e-mail applies to the whole instance, so this runs once and turns it off again.
test('an admin sets up the mail server, whose password is never shown', async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, 'An instance setting; once is enough.')
  const login = await page.request.post('/api/v1/auth/login', {
    data: { email: admin.email, password: admin.password },
  })
  expect(login.ok()).toBe(true)
  await page.goto('/admin')
  const form = page.getByTestId('smtp-settings')
  const save = form.getByRole('button', { name: 'Save' })
  await expect(page.getByTestId('test-mail')).toHaveCount(0)
  // Save turns on once the saved settings are in the form, which would overwrite earlier typing.
  await expect(save).toBeEnabled()

  await form.getByLabel('Mail server').fill('mail.example.com')
  await save.click()
  await expect(form).toContainText('Fill in both the mail server and the sender address')

  await form.getByLabel('User name').fill('calendar')
  await form.getByLabel('Password').fill('mail-secret')
  await form.getByLabel('Sender address').fill('calendar@example.com')
  await save.click()
  await expect(page.getByTestId('test-mail')).toBeVisible()

  await page.reload()
  await expect(form.getByLabel('Mail server')).toHaveValue('mail.example.com')
  await expect(form.getByLabel('Password')).toHaveValue('')
  await expect(form).toContainText('A password is saved')
  const stored = await (await page.request.get('/api/v1/admin/smtp')).text()
  expect(stored).not.toContain('mail-secret')

  // A save with the password left empty keeps it.
  await form.getByLabel('Port').fill('2525')
  await save.click()
  // The form fills in again from the answer, so the next change waits for it.
  await expect(save).not.toHaveAttribute('aria-busy', 'true')
  await expect
    .poll(async () => (await (await page.request.get('/api/v1/admin/smtp')).json()).port)
    .toBe(2525)
  await expect(form).toContainText('A password is saved')

  await form.getByLabel('Mail server').fill('')
  await form.getByLabel('User name').fill('')
  await form.getByLabel('Sender address').fill('')
  await save.click()
  await expect(page.getByTestId('test-mail')).toHaveCount(0)
  await expect
    .poll(async () => (await (await page.request.get('/api/v1/config')).json()).email_enabled)
    .toBe(false)
  // Without a user name the password goes too.
  await expect(form).not.toContainText('A password is saved')
})
