// Profile selection only: this ID is not an authentication credential.
const storageKey = 'ase.profileUserId'
let currentUserId = null

export function rememberUserId(id) {
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error('Invalid user ID')
  currentUserId = id
  try {
    sessionStorage.setItem(storageKey, String(id))
  } catch {
    // Keep navigation working when browser storage is disabled.
  }
}

export function getCurrentUserId() {
  try {
    const id = Number(sessionStorage.getItem(storageKey))
    if (Number.isSafeInteger(id) && id > 0) return id
  } catch {
    // Fall back to the ID from the current page session.
  }
  return currentUserId
}

export function clearCurrentUserId() {
  currentUserId = null
  try {
    sessionStorage.removeItem(storageKey)
  } catch {
    // Storage may be unavailable.
  }
}
