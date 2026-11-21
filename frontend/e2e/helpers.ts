import { test as base, expect, type Locator, type Page } from '@playwright/test'

export const admin = { name: 'Ada Admin', email: 'ada@example.com', password: 'admin-password' }

/** A week away from any daylight saving change, so times read the same in every test. */
export const MONDAY = '2027-02-01'
export const TUESDAY = '2027-02-02'
export const WEDNESDAY = '2027-02-03'

interface User {
  email: string
  password: string
}

/**
 * `user` is a fresh account per test, invited by the admin through the API, so parallel tests
 * never see each other's events. `page` is signed in as that user.
 */
export const test = base.extend<{ user: User }>({
  user: async ({ playwright, baseURL }, use) => {
    const api = await playwright.request.newContext({ baseURL })
    const login = await api.post('/api/v1/auth/login', {
      data: { email: admin.email, password: admin.password },
    })
    expect(login.ok()).toBe(true)
    const invite = (await (await api.post('/api/v1/admin/invites', { data: {} })).json()) as {
      url: string
    }
    const user = { email: `user-${crypto.randomUUID()}@example.com`, password: 'user-password' }
    const accepted = await api.post('/api/v1/auth/invite/accept', {
      data: {
        token: invite.url.split('/').pop(),
        email: user.email,
        display_name: 'Tester',
        password: user.password,
        timezone: 'Europe/Prague',
      },
    })
    expect(accepted.ok()).toBe(true)
    await api.dispose()
    await use(user)
  },
  page: async ({ page, user }, use) => {
    const login = await page.request.post('/api/v1/auth/login', {
      data: { email: user.email, password: user.password },
    })
    expect(login.ok()).toBe(true)
    await use(page)
  },
})

export { expect }

/** The day or week grid for a date: a week on a desktop, one day on a phone. */
export async function openGrid(page: Page, isMobile: boolean, date: string): Promise<void> {
  await page.goto(`/${isMobile ? 'day' : 'week'}/${date}`)
  await expect(page.locator('.cal-fc-lane').first()).toBeVisible()
}

export function eventBlock(page: Page, title: string): Locator {
  return page.locator('.cal-event').filter({ hasText: title })
}

/** Drags over empty time in the grid, as a person does to create an event. */
export async function selectTime(
  page: Page,
  date: string,
  from: string,
  to: string,
): Promise<void> {
  const lane = page.locator(`.cal-fc-lane[data-date="${date}"]`)
  const first = page.locator(`.cal-fc-slot[data-time="${from}:00"]`)
  const last = page.locator(`.cal-fc-slot[data-time="${halfHourBefore(to)}:00"]`)
  await first.scrollIntoViewIfNeeded()
  const x = await centre(lane, 'x')
  const top = (await box(first)).y + 4
  const bottom = (await box(last)).y + (await box(last)).height - 4
  await page.mouse.move(x, top)
  await page.mouse.down()
  await page.mouse.move(x, bottom, { steps: 8 })
  await page.mouse.up()
}

/** Drags an event block to another day and time. */
export async function dragEvent(
  page: Page,
  title: string,
  date: string,
  time: string,
): Promise<void> {
  const block = eventBlock(page, title)
  const target = page.locator(`.cal-fc-slot[data-time="${time}:00"]`)
  const from = await box(block)
  const lane = page.locator(`.cal-fc-lane[data-date="${date}"]`)
  await page.mouse.move(from.x + from.width / 2, from.y + 6)
  await page.mouse.down()
  await page.mouse.move(await centre(lane, 'x'), (await box(target)).y + 6, { steps: 12 })
  await page.mouse.up()
}

/** Opens the editor for a new event: the sidebar button on a desktop, the round button on a phone. */
export async function newEvent(page: Page, isMobile: boolean): Promise<Locator> {
  await page.getByTestId(isMobile ? 'fab' : 'new-event').click()
  const editor = page.getByTestId('event-editor')
  await expect(editor).toBeVisible()
  return editor
}

export async function fillTimes(
  editor: Locator,
  date: string,
  start: string,
  end: string,
): Promise<void> {
  await editor.locator('#event-start-date').fill(date)
  await editor.getByLabel('Start time').fill(start)
  await editor.locator('#event-end-date').fill(date)
  await editor.getByLabel('End time').fill(end)
}

export async function chooseScope(
  page: Page,
  scope: 'This event' | 'This and following events' | 'All events',
): Promise<void> {
  const dialog = page.getByTestId('scope-dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByLabel(scope).check()
  await dialog.getByTestId('scope-confirm').click()
  await expect(dialog).toHaveCount(0)
}

function halfHourBefore(time: string): string {
  const [h, m] = time.split(':').map(Number) as [number, number]
  const minutes = h * 60 + m - 30
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

async function box(
  locator: Locator,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const found = await locator.boundingBox()
  if (!found) throw new Error(`${String(locator)} is not visible`)
  return found
}

async function centre(locator: Locator, axis: 'x' | 'y'): Promise<number> {
  const found = await box(locator)
  return axis === 'x' ? found.x + found.width / 2 : found.y + found.height / 2
}
