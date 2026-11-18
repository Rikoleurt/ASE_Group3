// Test accounts are isolated by a unique `e2e-` username and deleted after each test.
// Deleting the user also deletes its sessions and analyses (ON DELETE CASCADE).
import { randomBytes } from 'node:crypto'
import mysql from 'mysql2/promise'

export const PREFIX = 'e2e-'

// The same defaults as .env.example and docker-compose.yml.
export const database = {
  MYSQL_HOST: process.env.MYSQL_HOST ?? '127.0.0.1',
  MYSQL_PORT: process.env.MYSQL_PORT ?? '3306',
  MYSQL_DATABASE: process.env.MYSQL_DATABASE ?? 'ase3',
  MYSQL_USER: process.env.MYSQL_USER ?? 'ase',
  MYSQL_PASSWORD: process.env.MYSQL_PASSWORD ?? 'ase',
}

async function connect() {
  return mysql.createConnection({
    host: database.MYSQL_HOST,
    port: Number(database.MYSQL_PORT),
    database: database.MYSQL_DATABASE,
    user: database.MYSQL_USER,
    password: database.MYSQL_PASSWORD,
  })
}

/** A new disposable account; nothing about it is reused between runs. */
export function testAccount() {
  const id = `${Date.now().toString(36)}${randomBytes(4).toString('hex')}`
  return {
    username: `${PREFIX}${id}`,
    email: `${PREFIX}${id}@example.com`,
    password: randomBytes(12).toString('base64url'),
  }
}

export async function deleteAccounts(usernames) {
  if (!usernames.length) return
  const connection = await connect()
  try {
    await connection.query('DELETE FROM `user` WHERE username IN (?)', [usernames])
  } finally {
    await connection.end()
  }
}

/** Removes accounts left by an interrupted run, so no run depends on an earlier one. */
export async function deleteLeftoverAccounts() {
  const connection = await connect()
  try {
    await connection.query('DELETE FROM `user` WHERE username LIKE ?', [`${PREFIX}%`])
  } finally {
    await connection.end()
  }
}
