<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'

const router = useRouter()
const items = ref([])
const cursor = ref(null)
const loading = ref(false)
const error = ref('')
const loaded = ref(false)
const date = (value) => new Date(value).toLocaleString()

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const query = cursor.value ? `&cursor=${encodeURIComponent(cursor.value)}` : ''
    const response = await sessionFetch(`/api/users/me/analyses?limit=20${query}`)
    if (response.status === 401) {
      items.value = []
      await router.push({ path: '/login', query: { redirect: '/profile/history' } })
      return
    }
    if (!response.ok) throw new Error('Your history could not be loaded. Please try again.')
    const page = await response.json()
    items.value.push(...page.items)
    cursor.value = page.next_cursor
    loaded.value = true
  } catch (failure) {
    error.value = failure.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
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

    <div class="mx-auto max-w-4xl">
      <h1 class="text-3xl font-bold">Analysis history</h1>
      <p class="mt-2 text-ink/70">Your saved results, most recent first.</p>
      <ul v-if="items.length" class="mt-6 divide-y divide-ink/10 overflow-hidden rounded-2xl bg-card">
        <li v-for="item in items" :key="item.id">
          <RouterLink :to="`/profile/history/${item.id}`" class="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-bar focus-visible:bg-bar focus-visible:outline-2 focus-visible:outline-offset-[-2px]" :aria-label="`View analysis of ${item.filename}, ${date(item.created_at)}`">
            <span class="min-w-0 flex-1 break-all font-semibold">{{ item.filename }}</span>
            <span class="text-sm">{{ item.format }} · {{ (item.size_bytes / 1024).toFixed(1) }} KiB</span>
            <time :datetime="item.created_at" class="text-sm text-ink/70">{{ date(item.created_at) }}</time>
            <span aria-hidden="true">→</span>
          </RouterLink>
        </li>
      </ul>
      <p v-if="loaded && !items.length" class="mt-8 rounded-2xl bg-card p-6">No analyses yet. <RouterLink to="/analysis" class="underline">Analyze your first image</RouterLink>.</p>
      <p v-if="loading" role="status" class="mt-6">Loading your history…</p>
      <p v-if="error" role="alert" class="mt-6">{{ error }}</p>
      <button v-if="error || cursor" :disabled="loading" class="mt-6 cursor-pointer rounded bg-bar px-6 py-2 hover:brightness-95 disabled:opacity-50" @click="load">{{ error ? 'Try again' : 'Load more' }}</button>
    </div>
  </main>
</template>
