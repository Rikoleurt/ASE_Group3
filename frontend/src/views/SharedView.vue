<script setup>
// Corrected copies other people shared with you, or with everyone logged in (#84).
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'

const LEVEL_TEXT = { view: 'Can view', comment: 'Can comment', edit: 'Can edit', manage: 'Can edit and share' }
const router = useRouter()
const COPIES = ref([])
const LOADING = ref(true)
const ERROR = ref('')

async function load() {
  LOADING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch('/api/users/me/shared-copies')
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: '/shared' } })
      return
    }
    if (!response.ok) throw new Error('The shared copies could not be loaded. Please try again.')
    COPIES.value = await response.json()
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
  } finally {
    LOADING.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="mx-auto max-w-4xl px-6 py-10">
    <h1 class="text-3xl font-bold">Shared with me</h1>
    <p class="mt-1 text-ink/70">Other people's corrected boxes that you can open.</p>
    <p v-if="LOADING" role="status" class="mt-6">Loading…</p>
    <p v-else-if="ERROR" role="alert" class="mt-6 text-confidence-low">{{ ERROR }}</p>
    <p v-else-if="!COPIES.length" class="mt-6 rounded-2xl bg-card p-6">Nothing has been shared with you yet.</p>
    <ul v-else class="mt-6 divide-y divide-ink/10 rounded-2xl bg-card">
      <li v-for="copy in COPIES" :key="copy.id">
        <RouterLink :to="`/box-sets/${copy.id}`" class="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-3 hover:bg-bar focus-visible:bg-bar" data-testid="shared-copy">
          <span class="font-semibold">{{ copy.title }}</span>
          <span class="text-sm text-ink/70">{{ copy.kind === 'tablet' ? 'Corpus tablet' : 'Upload' }} · by {{ copy.owner }}</span>
          <span class="ml-auto text-sm">{{ LEVEL_TEXT[copy.permission] }}<template v-if="copy.shared_with_everyone"> · shared with everyone</template></span>
        </RouterLink>
      </li>
    </ul>
  </main>
</template>
