import { ref } from 'vue'
import { clearCurrentUserId, rememberUserId } from './currentUser'

let csrfToken = null
export const sessionUser = ref(null)
// Whether the user may review sign corrections; the server enforces it either way.
export const sessionReviewer = ref(false)
// Whether the user may manage roles on the admin page; the server enforces it either way.
export const sessionAdmin = ref(false)

export function acceptSession(data) {
  csrfToken = data.csrf_token
  rememberUserId(data.user.id)
  sessionUser.value = data.user
  sessionReviewer.value = data.reviewer === true
  sessionAdmin.value = data.admin === true
  return data.user
}

export function forgetSession() {
  csrfToken = null
  sessionUser.value = null
  sessionReviewer.value = false
  sessionAdmin.value = false
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

export async function sessionFetch(url, { anyUser = false, ...options } = {}) {
  const write = options.method && options.method !== 'GET'
  // Refresh before a write: another tab may have logged in as a different user. Then this page
  // still shows the first user's work, so refuse the write instead of saving it as someone else
  // (#98). Logging out (anyUser) is always allowed.
  if (write) {
    const before = sessionUser.value?.id
    await loadSession()
    if (!anyUser && before != null && sessionUser.value?.id !== before) {
      throw Object.assign(new Error('You logged in as someone else in another tab. Reload this page to continue.'), { status: 409 })
    }
  }
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

export async function logoutSession() {
  try {
    const response = await sessionFetch('/api/users/logout', { method: 'POST', anyUser: true })
    if (!response.ok && response.status !== 401) throw new Error('Logout failed')
  } catch (failure) {
    if (failure.status !== 401) throw failure
  }
  forgetSession()
}
