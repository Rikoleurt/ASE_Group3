// `account` is a fresh test account for one test, deleted afterwards even when the test fails.
import { appendFileSync } from 'node:fs'
import { test as base, expect } from '@playwright/test'
import { deleteAccounts, testAccount } from './database.js'
import { SECRETS } from './fixture.js'

export const test = base.extend({
  account: async ({}, use) => {
    const account = testAccount()
    appendFileSync(SECRETS, `${account.password}\n`)
    try {
      await use(account)
    } finally {
      await deleteAccounts([account.username])
    }
  },
})

export { expect }

/** Creates the account through the API, as the signup form would. */
export async function register(page, account) {
  const response = await page.request.post('/api/users/register', {
    data: account,
    headers: { 'X-Requested-With': 'ASE' },
  })
  expect(response.status()).toBe(201)
}

export async function logIn(page, account) {
  await page.getByLabel('Username').fill(account.username)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
}
