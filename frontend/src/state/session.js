import { clearCurrentUserId, rememberUserId } from './currentUser'

let csrfToken = null

export function acceptSession(data) {
  csrfToken = data.csrf_token
  rememberUserId(data.user.id)
  return data.user
}

export function forgetSession() {
  csrfToken = null
  clearCurrentUserId()
}

export async function loadSession() {
  const response = await fetch('/api/users/me', { cache: 'no-store' })
  if (!response.ok) {
    if (response.status === 401) forgetSession()
    const error = new Error(response.status === 401 ? 'Your session has expired. Please log in.' : 'Unable to load your account. Please try again.')
    error.status = response.status
    throw error
  }
  return acceptSession(await response.json())
}

export async function sessionFetch(url, options = {}) {
  const write = options.method && options.method !== 'GET'
  // Refresh before a write: another tab may have logged in as a different user.
  if (write) await loadSession()
  const response = await fetch(url, {
    ...options,
    cache: 'no-store',
    headers: { ...options.headers, ...(write ? { 'X-CSRF-Token': csrfToken } : {}) },
  })
  if (response.status === 401) forgetSession()
  return response
}

export function loginDestination(route) {
  const next = route.query.redirect
  return typeof next === 'string' && /^\/(?!\/)/.test(next) && !next.includes('\\') ? next : '/profile'
}
