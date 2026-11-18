// Sign up, log out, log in again: the account and its session go through MySQL.
import { expect, logIn, register, test } from '../helpers/test.js'

test('signs up, logs out and logs back in to the same profile', async ({ page, account }) => {
  await page.goto('/signup')
  await page.getByLabel('Username').fill(account.username)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign Up' }).click()
  await expect(page).toHaveURL(/\/login$/)

  await logIn(page, account)
  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(account.username)
  await expect(page.getByText(account.email)).toBeVisible()

  await page.locator('header').getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.locator('header').getByRole('link', { name: 'Login' })).toBeVisible()
  // The session is gone on the server too: the profile asks to log in again.
  await page.goto('/profile')
  await expect(page).toHaveURL(/\/login\?redirect=/)

  await logIn(page, account)
  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(account.username)
})

test('refuses a wrong password and stays logged out', async ({ page, account }) => {
  await register(page, account)
  await page.goto('/login')
  await logIn(page, { ...account, password: `${account.password}-wrong` })

  await expect(page.getByRole('alert')).toHaveText('Incorrect username or password.')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Log out' })).toHaveCount(0)
})
