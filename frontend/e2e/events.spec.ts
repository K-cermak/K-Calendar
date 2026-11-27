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

test('closing the editor with changes asks to save, cancel or discard', async ({
  page,
  isMobile,
}) => {
  await createEvent(page, {
    title: 'Dentist',
    start: `${MONDAY}T08:00:00`,
    end: `${MONDAY}T09:00:00`,
    tags: ['health'],
    rrule: 'FREQ=WEEKLY',
  })
  await openGrid(page, isMobile, MONDAY)
  const editor = page.getByTestId('event-editor')
  const prompt = page.getByTestId('unsaved-dialog')
  const openEditor = async () => {
    await eventBlock(page, 'Dentist').click()
    await page.getByTestId('detail-edit').click()
    await expect(editor).toBeVisible()
  }

  // Unchanged, it closes without a question, though the fields were filled from a repeating event.
  await openEditor()
  await page.keyboard.press('Escape')
  await expect(editor).toHaveCount(0)

  await openEditor()
  await editor.getByLabel('Title').fill('Dentist at 8')
  await page.keyboard.press('Escape')
  // The question dims the editor behind it, so the editor does not get the pointer there.
  const field = (await editor.getByLabel('Title').boundingBox())!
  const reachesEditor = await page.evaluate(
    ([x, y]) => !!document.elementFromPoint(x, y)?.closest('[data-testid="event-editor"]'),
    [field.x + 4, field.y + 4],
  )
  expect(reachesEditor).toBe(false)
  await prompt.getByRole('button', { name: 'Cancel' }).click()
  await expect(editor.getByLabel('Title')).toHaveValue('Dentist at 8')

  await page.getByRole('button', { name: 'Close' }).click()
  await prompt.getByRole('button', { name: 'Discard' }).click()
  await expect(editor).toHaveCount(0)
  await expect(eventBlock(page, 'Dentist')).toBeVisible()

  await openEditor()
  await editor.getByLabel('Title').fill('Dentist at 8')
  // The corner of the dimmed page, which neither the dialog nor the phone's sheet covers.
  await page
    .locator('.ui-overlay')
    .last()
    .click({ position: { x: 8, y: 8 } })
  await expect(prompt.getByRole('button', { name: 'Save' })).toBeFocused()
  await page.keyboard.press('Enter')
  await chooseScope(page, 'This event')
  await expect(editor).toHaveCount(0)
  await expect(eventBlock(page, 'Dentist at 8')).toBeVisible()
})

test('the chosen time stays marked while quick create is filled in', async ({ page, isMobile }) => {
  test.skip(isMobile, 'A phone opens the full editor instead of quick create.')
  const quick = page.getByTestId('quick-create')
  const highlight = page.locator('.cal-fc-highlight')

  await page.goto(`/month/${MONDAY}`)
  await page.locator(`.cal-fc-cell[data-date="${WEDNESDAY}"]`).click()
  await expect(quick).toBeVisible()
  await expect(highlight).toHaveCount(1)
  await quick.getByLabel('Title').click()
  await quick.getByLabel('Title').fill('Picnic')
  await expect(highlight).toHaveCount(1)

  // Closing quick create clears the mark.
  await quick.getByRole('button', { name: 'Cancel' }).click()
  await expect(highlight).toHaveCount(0)

  await openGrid(page, isMobile, MONDAY)
  await selectTime(page, MONDAY, '10:00', '11:00')
  await quick.getByLabel('Title').click()
  await expect(page.getByTestId('selection-mirror')).toBeVisible()
})
