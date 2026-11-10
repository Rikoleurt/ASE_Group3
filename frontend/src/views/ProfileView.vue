<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { loadSession, logoutSession } from '../state/session'

const router = useRouter()
const userId = ref(null)
const profile = ref(null)
const loading = ref(false)
const error = ref('')
const user = computed(() => ({
  name: profile.value?.username ?? 'Profile',
  avatar: '',
  details: [
    { label: 'Username', value: profile.value?.username ?? '—' },
    { label: 'Email', value: profile.value?.email ?? '—' },
    { label: 'Symbols clustered', value: '—' },
  ],
}))

async function loadProfile() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  profile.value = null
  try {
    profile.value = await loadSession()
    userId.value = profile.value.id
  } catch (failure) {
    error.value = failure.status === 401 ? failure.message : 'Your profile could not be loaded. Please try again.'
    userId.value = null
  } finally {
    loading.value = false
  }
}

async function logout() {
  try {
    await logoutSession()
  } catch {
    error.value = 'Unable to log out. Please try again.'
    return
  }
  profile.value = null
  await router.push('/login')
}

onMounted(loadProfile)
</script>

<template>
  <main class="px-4 pt-10 pb-10">
    <nav aria-label="Profile" class="mx-auto mb-8 flex max-w-4xl gap-4">
      <RouterLink
        to="/profile"
        class="relative rounded px-4 py-2 text-center hover:bg-bar focus-visible:outline-2"
        active-class="bg-bar font-bold"
        exact-active-class="bg-bar font-bold"
      >
        <span class="invisible font-bold" aria-hidden="true">Profile</span>
        <span class="absolute inset-0 flex items-center justify-center">
          Profile
        </span>
      </RouterLink>

      <RouterLink
        to="/profile/history"
        class="relative rounded px-4 py-2 text-center hover:bg-bar focus-visible:outline-2"
        active-class="bg-bar font-bold"
      >
        <span class="invisible font-bold" aria-hidden="true">History</span>
        <span class="absolute inset-0 flex items-center justify-center">
          History
        </span>
      </RouterLink>
    </nav>
    <section class="mx-auto flex max-w-4xl flex-col items-center gap-8 rounded-3xl bg-card p-8 sm:flex-row sm:items-start sm:gap-12 sm:p-10">
   
      <div class="h-48 w-48 shrink-0 overflow-hidden rounded-full ring-4 ring-bar">
        <img
          v-if="user.avatar"
          :src="user.avatar"
          alt=""
          class="h-full w-full object-cover"
        />
        <span v-else class="block h-full w-full bg-bar" />
      </div>

      <div class="w-full min-w-0 text-center sm:text-left">
        <h1 class="text-3xl font-bold">{{ user.name }}</h1>

        <p v-if="loading" role="status">Loading your profile…</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <template v-if="!userId && !loading">
          <p v-if="!error">Log in to view your profile.</p>
          <RouterLink to="/login">Log in</RouterLink>
        </template>
        <button v-if="error" type="button" @click="loadProfile">Try again</button>

        <dl v-if="profile" class="mt-6 divide-y divide-ink/10 text-left">
          <div
            v-for="item in user.details"
            :key="item.label"
            class="flex justify-between gap-4 py-2"
          >
            <dt class="text-ink/70">{{ item.label }}</dt>
            <dd class="font-medium">{{ item.value }}</dd>
          </div>
        </dl>

        <div v-if="profile" class="mt-8 flex justify-center gap-3 sm:justify-start">
          <button
            type="button"
            class="mx-auto cursor-pointer rounded bg-bar px-8 py-1.5 hover:brightness-75"
            @click="logout"
          >
            Log out
          </button>
        </div>
      </div>
    </section>
  </main>
</template>
