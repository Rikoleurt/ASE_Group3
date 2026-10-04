<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { clearCurrentUserId, getCurrentUserId } from '../state/currentUser'

const userId = ref(getCurrentUserId())
const profile = ref(null)
const loading = ref(false)
const error = ref('')

async function loadProfile() {
  if (!userId.value || loading.value) return
  loading.value = true
  error.value = ''
  profile.value = null

  try {
    const responses = await Promise.all([
      fetch(`/api/users/${userId.value}/username`),
      fetch(`/api/users/${userId.value}/email`),
    ])
    if (responses.some((response) => response.status === 404)) {
      clearCurrentUserId()
      userId.value = null
      error.value = 'This account could not be found. Please log in again.'
      return
    }
    if (responses.some((response) => !response.ok)) {
      error.value = 'Your profile could not be loaded. Please try again.'
      return
    }
    const [username, email] = await Promise.all(responses.map((response) => response.json()))
    profile.value = { username: username.username, email: email.email }
  } catch {
    error.value = 'Unable to reach the server. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <main lang="en" class="mx-auto w-full max-w-md px-5 py-12">
    <section class="rounded-2xl border border-ink/15 bg-card p-6 shadow-sm sm:p-8" aria-labelledby="profile-title" :aria-busy="loading">
      <h1 id="profile-title" class="text-3xl font-bold">Profile</h1>
      <p v-if="loading" role="status" class="mt-6">Loading your profile…</p>
      <p v-if="error" role="alert" class="mt-6 rounded-lg border border-red-800/30 bg-red-50 p-3 text-sm text-red-900">{{ error }}</p>

      <dl v-if="profile" class="mt-7 space-y-5">
        <div>
          <dt class="font-semibold">Username</dt>
          <dd class="mt-1 break-words">{{ profile.username }}</dd>
        </div>
        <div>
          <dt class="font-semibold">Email</dt>
          <dd class="mt-1 break-words">{{ profile.email }}</dd>
        </div>
      </dl>

      <div v-if="!userId" class="mt-6">
        <p v-if="!error" class="mb-4">Log in to view your profile.</p>
        <RouterLink to="/login" class="mt-4 block rounded-lg bg-ink px-4 py-3 text-center font-semibold text-white hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">Log in</RouterLink>
      </div>
      <button v-else-if="error" type="button" class="mt-4 rounded-lg border border-ink px-4 py-2 font-semibold hover:bg-page focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" @click="loadProfile">Try again</button>
    </section>
  </main>
</template>
