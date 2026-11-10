import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { acceptSession, loginDestination } from '../state/session'

export function useAuth(mode) {
  const router = useRouter()
  const route = useRoute()
  const username = ref('')
  const email = ref('')
  const password = ref('')
  const pending = ref(false)
  const error = ref('')

  async function submit() {
    if (pending.value) return
    pending.value = true
    error.value = ''
    try {
      const payload = { username: username.value.trim(), password: password.value }
      if (mode === 'register') payload.email = email.value.trim()
      const response = await fetch(`/api/users/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'ASE' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const body = typeof response.json === 'function' ? await response.json().catch(() => null) : null
        const duplicateField = body?.detail?.field
        error.value = {
          401: 'Incorrect username or password.',
          422: 'Please check your details.',
        }[response.status] || 'The service is unavailable. Please try again later.'
        if (response.status === 409) {
          error.value = duplicateField === 'email'
            ? 'This email is already registered. Please log in or use another email.'
            : duplicateField === 'username'
              ? 'This username is already taken. Please choose another username.'
              : 'This email or username is already in use. Please log in or choose different details.'
        }
        return
      }
      const data = await response.json()
      if (mode === 'register') {
        await router.push('/login')
      } else if (data.authenticated && Number.isSafeInteger(data.user?.id) && data.user.id > 0) {
        acceptSession(data)
        await router.push(loginDestination(route))
      } else {
        error.value = 'Your login could not be confirmed. Please try again.'
      }
    } catch {
      error.value = 'Unable to reach the server. Check your connection and try again.'
    } finally {
      password.value = ''
      pending.value = false
    }
  }

  return { username, email, password, pending, error, submit }
}
