// Upload a real tablet and read it with the trained sign reader: browser, backend,
// model and MySQL together. Asserts that each part of the result is shown, not
// exact counts or confidences, which change with the model.
import { FIXTURE } from '../helpers/fixture.js'
import { expect, logIn, register, test } from '../helpers/test.js'

test.beforeEach(async ({ page, account }) => {
  await register(page, account)
  await page.goto('/analysis')
  await expect(page).toHaveURL(/\/login\?redirect=/)
  await logIn(page, account)
  await expect(page).toHaveURL(/\/analysis$/)
})

test('reads a tablet, draws its signs, checks its fractions and saves it to history', async ({ page }) => {
  const analysed = page.waitForResponse((response) =>
    response.url().endsWith('/api/analysis') && response.request().method() === 'POST')
  await page.locator('input[type="file"]').setInputFiles(FIXTURE)

  const response = await analysed
  expect(response.status()).toBe(200)
  const result = await response.json()
  // The generic fallback model would also return 200: insist on the Linear A reader.
  expect(result.trained).toBe(true)
  expect(result.signs.length).toBeGreaterThan(0)

  await expect(page.getByRole('img', { name: 'ht13.png' })).toBeVisible()
  await expect(page.getByTestId('sign-box').first()).toBeVisible()
  await expect(page.getByTestId('sign-box')).toHaveCount(result.signs.length)
  await expect(page.getByText(result.symbol_interpretation, { exact: true })).toBeVisible()
  await expect(page.getByTestId('formula').first()).toBeVisible()
  await expect(page.getByTestId('verdict').first()).not.toBeEmpty()

  await page.getByRole('link', { name: /Saved in your history/ }).click()
  await expect(page).toHaveURL(new RegExp(`/profile/history/${result.analysis_id}$`))
  await expect(page.getByText(result.symbol_interpretation).first()).toBeVisible()
})

test('refuses a file that is not an image before uploading it', async ({ page }) => {
  let uploaded = false
  page.on('request', (request) => { uploaded ||= request.url().endsWith('/api/analysis') })
  await page.locator('input[type="file"]').setInputFiles({
    name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('not a tablet'),
  })

  await expect(page.getByRole('alert')).toHaveText('Only PNG or JPG allowed')
  expect(uploaded).toBe(false)
})
