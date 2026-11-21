import { MONDAY, eventBlock, expect, openGrid, test } from './helpers'

const ICS = [
  'BEGIN:VCALENDAR',
  'VERSION:2.0',
  'PRODID:-//e2e//EN',
  'BEGIN:VEVENT',
  'UID:e2e-one@example.com',
  'DTSTAMP:20270101T000000Z',
  'DTSTART;TZID=Europe/Prague:20270201T130000',
  'DTEND;TZID=Europe/Prague:20270201T140000',
  'SUMMARY:Imported lunch',
  'END:VEVENT',
  'BEGIN:VEVENT',
  'UID:e2e-two@example.com',
  'DTSTAMP:20270101T000000Z',
  'DTSTART:20270201T160000Z',
  'DTEND:20270201T170000Z',
  'SUMMARY:Imported call',
  'END:VEVENT',
  'END:VCALENDAR',
  '',
].join('\r\n')

test('an .ics file imports into a calendar', async ({ page, isMobile }) => {
  await openGrid(page, isMobile, MONDAY)
  if (isMobile) await page.getByTestId('menu-button').click()
  await page.getByRole('button', { name: 'Actions for Personal' }).click()
  await page.getByRole('menuitem', { name: 'Settings' }).click()
  await page.getByTestId('import-file').setInputFiles({
    name: 'events.ics',
    mimeType: 'text/calendar',
    buffer: Buffer.from(ICS),
  })
  await expect(page.getByTestId('import-result')).toHaveText('Created 2, updated 0, skipped 0.')
  await page.keyboard.press('Escape')
  if (isMobile) await page.keyboard.press('Escape')
  await expect(eventBlock(page, 'Imported lunch')).toContainText('13:00')
  // 16:00 UTC is 17:00 in Prague in winter.
  await expect(eventBlock(page, 'Imported call')).toContainText('17:00')
})
