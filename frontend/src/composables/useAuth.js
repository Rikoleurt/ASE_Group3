import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { rememberUserId } from '../state/currentUser'

export function useAuth(mode) {
  const router = useRouter()
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        error.value = {
          401: 'Incorrect username or password.',
          409: 'An account with this email already exists. Please log in.',
          422: 'Please check your details.',
        }[response.status] || 'The service is unavailable. Please try again later.'
        return
      }
      const data = await response.json()
      if (mode === 'register') {
        await router.push('/login')
      } else if (data.authenticated && Number.isSafeInteger(data.user?.id) && data.user.id > 0) {
        rememberUserId(data.user.id)
        await router.push('/profile')
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
