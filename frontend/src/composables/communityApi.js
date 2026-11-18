import { sessionFetch } from '../state/session'

export async function communityApi(path, options = {}) {
  const response = options.method
    ? await sessionFetch(`/api/community${path}`, options)
    : await fetch(`/api/community${path}`, { cache: 'no-store' })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(typeof body?.detail === 'string'
      ? body.detail : 'The community could not be reached. Please try again.')
    error.status = response.status
    throw error
  }
  return body
}
