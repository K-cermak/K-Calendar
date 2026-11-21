import {
  MONDAY,
  TUESDAY,
  WEDNESDAY,
  chooseScope,
  dragEvent,
  eventBlock,
  expect,
  fillTimes,
  newEvent,
  openGrid,
  selectTime,
  test,
} from './helpers'
import { createEvent } from './api'

test('quick create puts a new event in the grid', async ({ page, isMobile }) => {
  await openGrid(page, isMobile, MONDAY)
  if (isMobile) {
    // A phone has no room to drag out a time; the round button is its quick way in.
    const editor = await newEvent(page, isMobile)
    await editor.getByLabel('Title').fill('Coffee')
    await fillTimes(editor, MONDAY, '10:00', '11:00')
    await editor.getByTestId('editor-save').click()
  } else {
    await selectTime(page, MONDAY, '10:00', '11:00')
    const quick = page.getByTestId('quick-create')
    await expect(quick).toContainText('10:00')
    await quick.getByLabel('Title').fill('Coffee')
    await quick.getByRole('button', { name: 'Save' }).click()
    await expect(quick).toHaveCount(0)
  }
  await expect(eventBlock(page, 'Coffee')).toContainText('10:00')
  await page.reload()
  await expect(eventBlock(page, 'Coffee')).toBeVisible()
})

test('a repeating event: change one occurrence, then the whole series', async ({
  page,
  isMobile,
}) => {
  await openGrid(page, isMobile, MONDAY)
  const editor = await newEvent(page, isMobile)
  await editor.getByLabel('Title').fill('Standup')
  await fillTimes(editor, MONDAY, '09:00', '09:30')
  await editor.getByTestId('repeat-select').selectOption({ label: 'Every day' })
  await editor.getByTestId('editor-save').click()
  await expect(editor).toHaveCount(0)

  const day = (date: string) => page.locator(`.cal-fc-lane[data-date="${date}"]`)
  if (isMobile) {
    await expect(eventBlock(page, 'Standup')).toHaveCount(1)
    await openGrid(page, isMobile, TUESDAY)
  } else {
    await expect(eventBlock(page, 'Standup')).toHaveCount(7)
  }

  await day(TUESDAY).locator('.cal-event').click()
  await page.getByTestId('detail-edit').click()
  await page.getByTestId('event-editor').getByLabel('Title').fill('Standup with Petr')
  await page.getByTestId('editor-save').click()
  await chooseScope(page, 'This event')
  await expect(day(TUESDAY).locator('.cal-event')).toContainText('Standup with Petr')

  await openGrid(page, isMobile, MONDAY)
  await day(MONDAY).locator('.cal-event').click()
  await page.getByTestId('detail-edit').click()
  await page.getByTestId('event-editor').getByLabel('Title').fill('Daily sync')
  await page.getByTestId('editor-save').click()
  await chooseScope(page, 'All events')
  await expect(day(MONDAY).locator('.cal-event')).toContainText('Daily sync')

  // Only the title changed, so the occurrence edited on its own keeps its own title (SPEC 5).
  await openGrid(page, isMobile, TUESDAY)
  await expect(day(TUESDAY).locator('.cal-event')).toContainText('Standup with Petr')
  if (!isMobile) await expect(eventBlock(page, 'Daily sync')).toHaveCount(6)
})

test('dragging an event moves it to another day and time', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Dragging is a pointer gesture; phones edit times in the form.')
  const event = await createEvent(page, {
    title: 'Dentist',
    start: `${MONDAY}T10:00:00`,
    end: `${MONDAY}T11:00:00`,
  })
  await openGrid(page, isMobile, MONDAY)
  await dragEvent(page, 'Dentist', WEDNESDAY, '14:00')
  await expect(page.getByTestId('toast')).toContainText('Event moved')
  await expect(
    page.locator(`.cal-fc-lane[data-date="${WEDNESDAY}"]`).locator('.cal-event'),
  ).toContainText('14:00')
  const moved = (await (await page.request.get(`/api/v1/events/${event.id}`)).json()) as {
    start: string
  }
  expect(moved.start).toBe(`${WEDNESDAY}T14:00:00`)
})
