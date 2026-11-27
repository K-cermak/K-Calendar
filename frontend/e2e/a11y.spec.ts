import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { createEvent } from './api'
import { MONDAY, TUESDAY, admin, eventBlock, expect, newEvent, openGrid, test } from './helpers'

/** Fails with axe's findings, as rule, impact and the elements involved, so the report is readable. */
async function expectAccessible(page: Page, where: string): Promise<void> {
  // Mid-animation colours are blends of the final ones, which axe would measure instead.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  )
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    // The app does not zoom like a page, by the owner's decision (SPEC 11, Zoom).
    .disableRules(['meta-viewport'])
    // SPEC 11 sets hour labels and day numbers in the faint colour, which in the light theme is
    // below 4.5:1. Left out until the spec decides between that look and the contrast.
    .exclude('.cal-fc-slot-header__inner')
    .exclude('.cal-fc-all-day-header__inner')
    .exclude('.cal-fc-day-number')
    .exclude('[data-testid="mini-month"] button > .text-faint')
    .exclude('[data-testid="month-dots"] button > .text-faint')
    .analyze()
  const found = violations.map(
    (v) =>
      `${where}: ${v.id} (${v.impact}) ${v.help}\n` +
      v.nodes
        .map((n) => `    ${n.target.join(' ')}: ${n.any[0]?.message ?? n.failureSummary}`)
        .join('\n'),
  )
  // Soft, so that one run lists the findings of every screen.
  expect.soft(found, found.join('\n')).toEqual([])
}

async function expectNoSidewaysScroll(page: Page, where: string): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect.soft(overflow, `${where} is wider than the screen`).toBeLessThanOrEqual(0)
}

async function sampleWeek(page: Page): Promise<void> {
  await createEvent(page, {
    title: 'Dentist',
    start: `${MONDAY}T08:00:00`,
    end: `${MONDAY}T08:45:00`,
    location: 'Main Street 12',
  })
  await createEvent(page, {
    title: 'Design review',
    start: `${TUESDAY}T13:00:00`,
    end: `${TUESDAY}T14:30:00`,
  })
}

const SETTINGS = ['/settings/profile', '/settings/security', '/settings/tokens', '/settings/device']

for (const colorScheme of ['light', 'dark'] as const) {
  test(`the calendar screens pass an accessibility check in the ${colorScheme} theme`, async ({
    page,
    isMobile,
  }) => {
    await page.emulateMedia({ colorScheme })
    await sampleWeek(page)

    await openGrid(page, isMobile, MONDAY)
    await expect(eventBlock(page, 'Dentist')).toBeVisible()
    await expectAccessible(page, 'grid')

    await eventBlock(page, 'Dentist').click()
    await expect(page.getByTestId('event-detail')).toBeVisible()
    await expectAccessible(page, 'event details')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('event-detail')).toHaveCount(0)

    await newEvent(page, isMobile)
    await expectAccessible(page, 'editor')
    await page.keyboard.press('Escape')

    for (const view of ['month', 'agenda']) {
      await page.goto(`/${view}/${MONDAY}`)
      await expect(page.getByText('Dentist').first()).toBeVisible()
      await expectAccessible(page, view)
    }

    if (isMobile) await page.getByTestId('search-open').click()
    await page.getByTestId('search-input').fill('dent')
    await expect(page.getByTestId('search-results').getByRole('option')).toHaveCount(1)
    await expectAccessible(page, 'search')
    await page.keyboard.press('Escape')

    for (const path of SETTINGS) {
      await page.goto(path)
      await expect(page.getByRole('heading').first()).toBeVisible()
      await expectAccessible(page, path)
    }
  })
}

test('the administration and sign-in pages pass an accessibility check', async ({ page }) => {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme })
    await page.request.post('/api/v1/auth/logout')
    await page.goto('/login')
    await expect(page.locator('#login-email')).toBeVisible()
    await expectAccessible(page, `login, ${colorScheme}`)

    await page.request.post('/api/v1/auth/login', {
      data: { email: admin.email, password: admin.password },
    })
    await page.goto('/admin')
    await expect(page.getByTestId('users')).toBeVisible()
    await expectAccessible(page, `admin, ${colorScheme}`)
  }
})

test.describe('at 360 px', () => {
  test.use({ viewport: { width: 360, height: 740 } })

  test('no screen scrolls sideways', async ({ page, isMobile }) => {
    test.skip(!isMobile, 'The phone layout is the one that has to fit.')
    await sampleWeek(page)
    for (const view of ['agenda', 'day', 'week', 'month']) {
      await page.goto(`/${view}/${MONDAY}`)
      await expect(page.getByText('Dentist').first()).toBeVisible()
      await expectNoSidewaysScroll(page, view)
    }
    await page.getByTestId('fab').click()
    await expect(page.getByTestId('event-editor')).toBeVisible()
    await expectNoSidewaysScroll(page, 'editor')
    await page.keyboard.press('Escape')
    for (const path of SETTINGS) {
      await page.goto(path)
      await expect(page.getByRole('heading').first()).toBeVisible()
      await expectNoSidewaysScroll(page, path)
    }
    await page.request.post('/api/v1/auth/login', {
      data: { email: admin.email, password: admin.password },
    })
    await page.goto('/admin')
    await expect(page.getByTestId('users')).toBeVisible()
    await expectNoSidewaysScroll(page, 'admin')
  })
})

test('an event can be created and opened with the keyboard alone', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Phones are used by touch; the desktop layout is the keyboard one.')
  await openGrid(page, isMobile, MONDAY)
  const focusedText = () => page.evaluate(() => document.activeElement?.textContent ?? '')

  async function tabTo(match: (text: string, testId: string | null) => boolean): Promise<void> {
    for (let i = 0; i < 80; i++) {
      await page.keyboard.press('Tab')
      const testId = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'))
      if (match(await focusedText(), testId ?? null)) return
    }
    throw new Error('Tab never reached the element')
  }

  await tabTo((_, id) => id === 'new-event')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('event-editor')).toBeVisible()
  await page.keyboard.type('Typed with keys')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('event-editor')).toHaveCount(0)

  await tabTo((text) => text.includes('Typed with keys'))
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('event-detail')).toContainText('Typed with keys')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('event-detail')).toHaveCount(0)
  expect(await focusedText()).toContain('Typed with keys')
})
