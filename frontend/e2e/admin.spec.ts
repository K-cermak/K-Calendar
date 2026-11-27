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
