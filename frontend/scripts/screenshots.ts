// Renders the README and website screenshots in Images from a fresh instance filled with a sample week.
// Run with `just screenshots`, which starts that instance; the base URL is the first argument.
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium, devices, request, type APIRequestContext, type Browser } from '@playwright/test'

const base = process.argv[2] ?? 'http://127.0.0.1:18200'
const outDir = fileURLToPath(new URL('../../Images/', import.meta.url))
mkdirSync(outDir, { recursive: true })

const zone = 'Europe/Prague'
const account = {
  display_name: 'Alex',
  email: 'alex@example.com',
  password: 'sample-password',
  timezone: zone,
}

// Next week, so no sample event is already over and shown faded.
const today = new Date()
const monday = new Date(today)
monday.setDate(today.getDate() - ((today.getDay() + 6) % 7) + 7)

function day(offset: number): string {
  const d = new Date(monday)
  d.setDate(monday.getDate() + offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

interface Sample {
  calendar: 'Personal' | 'Work' | 'Family'
  title: string
  day: number
  start?: string
  end?: string
  days?: number
  location?: string
  rrule?: string
  tags?: string[]
  reminders?: number[]
}

const samples: Sample[] = [
  {
    calendar: 'Work',
    title: 'Standup',
    day: 0,
    start: '09:30',
    end: '09:45',
    rrule: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR',
  },
  {
    calendar: 'Work',
    title: 'Design review',
    day: 1,
    start: '13:00',
    end: '14:30',
    location: 'Room 4',
  },
  {
    calendar: 'Work',
    title: 'Planning',
    day: 3,
    start: '10:30',
    end: '12:00',
    tags: ['Project'],
  },
  {
    calendar: 'Work',
    title: '1:1 with Sam',
    day: 2,
    start: '15:00',
    end: '15:30',
  },
  {
    calendar: 'Personal',
    title: 'Dentist',
    day: 2,
    start: '08:00',
    end: '08:45',
    location: 'Main Street 12',
    tags: ['Health'],
    reminders: [60],
  },
  {
    calendar: 'Personal',
    title: 'Running club',
    day: 1,
    start: '18:00',
    end: '19:00',
    rrule: 'FREQ=WEEKLY;BYDAY=TU,TH',
    tags: ['Sport'],
  },
  {
    calendar: 'Personal',
    title: 'Climbing',
    day: 5,
    start: '10:00',
    end: '12:30',
    tags: ['Sport'],
  },
  { calendar: 'Family', title: 'Dinner at Mum’s', day: 4, start: '18:30', end: '21:00' },
  { calendar: 'Family', title: 'Trip to the mountains', day: 5, days: 2 },
  { calendar: 'Family', title: 'Bin day', day: 0, days: 1, rrule: 'FREQ=WEEKLY' },
]

async function fill(api: APIRequestContext): Promise<void> {
  const setup = await api.post('/api/v1/auth/setup', { data: account })
  if (!setup.ok()) throw new Error(`Setup failed: ${await setup.text()}`)
  await api.patch('/api/v1/me', { data: { default_view: 'week' } })
  const calendars = (await (await api.get('/api/v1/calendars')).json()) as {
    id: number
    name: string
  }[]
  const ids: Record<string, number> = { Personal: calendars[0].id }
  await api.patch(`/api/v1/calendars/${ids.Personal}`, { data: { color: 'teal' } })
  for (const [name, color] of [
    ['Work', 'indigo'],
    ['Family', 'orange'],
  ] as const) {
    const created = (await (
      await api.post('/api/v1/calendars', { data: { name, color } })
    ).json()) as { id: number }
    ids[name] = created.id
  }
  for (const sample of samples) {
    const allDay = sample.days !== undefined
    const response = await api.post('/api/v1/events', {
      data: {
        calendar_id: ids[sample.calendar],
        title: sample.title,
        all_day: allDay,
        start: allDay ? day(sample.day) : `${day(sample.day)}T${sample.start}:00`,
        end: allDay ? day(sample.day + sample.days!) : `${day(sample.day)}T${sample.end}:00`,
        timezone: allDay ? null : zone,
        location: sample.location ?? '',
        rrule: sample.rrule ?? null,
        tags: sample.tags ?? [],
        reminders: sample.reminders ?? [],
      },
    })
    if (!response.ok()) throw new Error(`${sample.title}: ${await response.text()}`)
  }
}

async function shoot(
  browser: Browser,
  file: string,
  options: {
    theme: 'light' | 'dark'
    phone?: boolean
    path: string
    open?: string
    // 2 for the website, which wants sharp pictures on high-density screens.
    scale?: number
  },
): Promise<void> {
  const context = await browser.newContext({
    ...(options.phone ? devices['Pixel 7'] : { viewport: { width: 1440, height: 900 } }),
    ...(options.scale ? { deviceScaleFactor: options.scale } : {}),
    baseURL: base,
    colorScheme: options.theme,
    timezoneId: zone,
    locale: 'en-GB',
  })
  const login = await context.request.post('/api/v1/auth/login', {
    data: { email: account.email, password: account.password },
  })
  if (!login.ok()) throw new Error('Login failed')
  await context.request.patch('/api/v1/me', { data: { theme: options.theme } })
  const page = await context.newPage()
  await page.goto(options.path)
  await page.locator('.cal-event, [data-testid^="agenda-"]').first().waitFor()
  if (options.open) {
    await page.locator('.cal-event').filter({ hasText: options.open }).first().click()
    await page.getByTestId('event-detail').waitFor()
  }
  // Let fonts settle and the grid scroll to the working day.
  await page.waitForTimeout(600)
  await page.screenshot({ path: outDir + file })
  await context.close()
  console.log(`Wrote Images/${file}`)
}

const api = await request.newContext({ baseURL: base })
await fill(api)
await api.dispose()

const browser = await chromium.launch()
const week = `/week/${day(0)}`
const agenda = `/agenda/${day(0)}`
await shoot(browser, 'github-week-light.png', { theme: 'light', path: week })
await shoot(browser, 'github-week-dark.png', { theme: 'dark', path: week })
await shoot(browser, 'github-event.png', { theme: 'light', path: week, open: 'Dentist' })
await shoot(browser, 'github-phone.png', { theme: 'light', phone: true, path: agenda })
for (const theme of ['light', 'dark'] as const) {
  await shoot(browser, `web-week-${theme}.png`, { theme, path: week, scale: 2 })
  await shoot(browser, `web-event-${theme}.png`, { theme, path: week, open: 'Dentist', scale: 2 })
  await shoot(browser, `web-phone-${theme}.png`, { theme, phone: true, path: agenda })
}
await browser.close()
