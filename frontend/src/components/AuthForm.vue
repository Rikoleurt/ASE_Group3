<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

const props = defineProps({
  mode: { type: String, required: true, validator: (value) => ['login', 'register'].includes(value) },
})

const isRegister = computed(() => props.mode === 'register')
const email = ref('')
const password = ref('')
const pending = ref(false)
const error = ref('')
const success = ref('')

async function submit() {
  if (pending.value) return
  pending.value = true
  error.value = ''
  success.value = ''

  try {
    const response = await fetch(`/api/users/${props.mode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value.trim(), password: password.value }),
    })

    if (!response.ok) {
      const messages = {
        401: 'Incorrect email or password.',
        409: 'An account with this email already exists. Please log in.',
        422: 'Please check your email and password.',
      }
      error.value = messages[response.status] || 'The service is unavailable. Please try again later.'
      return
    }

    const data = await response.json()
    if (isRegister.value) {
      success.value = 'Your account has been created. You can now log in.'
    } else if (data.authenticated && data.user?.email) {
      success.value = `Successfully logged in as ${data.user.email}.`
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
</script>

<template>
  <main lang="en" class="mx-auto w-full max-w-md px-5 py-12">
    <section class="rounded-2xl border border-ink/15 bg-card p-6 shadow-sm sm:p-8" aria-labelledby="auth-title">
      <h1 id="auth-title" class="text-3xl font-bold">
        {{ isRegister ? 'Create an account' : 'Log in' }}
      </h1>
      <p class="mt-2 text-sm">
        {{ isRegister ? 'Sign up with your email and a password.' : 'Log in with your email and password.' }}
      </p>

      <form class="mt-7 space-y-5" :aria-busy="pending" @submit.prevent="submit">
        <div>
          <label for="auth-email" class="mb-2 block font-semibold">Email</label>
          <input
            id="auth-email"
            v-model="email"
            name="email"
            type="email"
            autocomplete="username"
            required
            maxlength="255"
            :disabled="pending"
            class="w-full rounded-lg border border-ink/30 bg-white px-3 py-2.5 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
          />
        </div>

        <div>
          <label for="auth-password" class="mb-2 block font-semibold">Password</label>
          <input
            id="auth-password"
            v-model="password"
            name="password"
            type="password"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            required
            maxlength="1024"
            :disabled="pending"
            class="w-full rounded-lg border border-ink/30 bg-white px-3 py-2.5 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
          />
        </div>

        <p v-if="error" role="alert" class="rounded-lg border border-red-800/30 bg-red-50 p-3 text-sm text-red-900">
          {{ error }}
        </p>
        <p v-if="success" role="status" class="rounded-lg border border-green-800/30 bg-green-50 p-3 text-sm text-green-900">
          {{ success }}
        </p>

        <button
          type="submit"
          :disabled="pending"
          class="w-full cursor-pointer rounded-lg bg-ink px-4 py-3 font-semibold text-white hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-wait disabled:opacity-60"
        >
          {{ pending ? 'Submitting…' : isRegister ? 'Create my account' : 'Log in' }}
        </button>
      </form>

      <div class="mt-6 border-t border-ink/20 pt-5 text-center">
        <p class="mb-3 text-sm">{{ isRegister ? 'Already have an account?' : 'Don’t have an account yet?' }}</p>
        <RouterLink
          :to="isRegister ? '/login' : '/signup'"
          class="block rounded-lg border border-ink px-4 py-2.5 font-semibold hover:bg-page focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          {{ isRegister ? 'Go to login' : 'Create an account' }}
        </RouterLink>
      </div>
    </section>
  </main>
</template>
