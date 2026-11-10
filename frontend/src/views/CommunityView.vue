<script setup>
import { onMounted, ref } from 'vue'
import { communityApi } from '../composables/communityApi'

const discussions = ref([])
const before = ref(null)
const loaded = ref(false)
const loading = ref(false)
const error = ref('')
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const page = await communityApi(`/discussions?limit=20${before.value ? `&before=${before.value}` : ''}`)
    discussions.value.push(...page.items)
    before.value = page.next_before
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
  <main class="mx-auto max-w-5xl px-6 py-10">
    <h1 class="text-3xl font-bold">Community</h1>
    <p class="mt-2 text-ink/70">Explore shared tablets and discuss the model’s readings.</p>
    <RouterLink to="/analysis" class="mt-4 inline-block underline">Analyze a tablet to share →</RouterLink>
    <ul v-if="discussions.length" class="mt-8 divide-y divide-ink/10 overflow-hidden rounded-2xl bg-card">
      <li v-for="discussion in discussions" :key="discussion.id">
        <RouterLink :to="`/community/${discussion.id}`" class="block px-6 py-5 hover:bg-bar focus-visible:bg-bar">
          <h2 class="break-words text-lg font-semibold">{{ discussion.title }}</h2>
          <p class="mt-1 text-sm text-ink/70">{{ discussion.author_username }} · <time :datetime="discussion.created_at">{{ new Date(discussion.created_at).toLocaleString() }}</time></p>
        </RouterLink>
      </li>
    </ul>
    <p v-else-if="loaded" class="mt-8 rounded-2xl bg-card p-6">No discussions yet. Share an analysis to start the conversation.</p>
    <p v-if="loading" role="status" class="mt-6">Loading discussions…</p>
    <p v-if="error" role="alert" class="mt-6 text-conf-low">{{ error }}</p>
    <button v-if="error || before" type="button" :disabled="loading" class="mt-6 rounded bg-bar px-6 py-2 disabled:opacity-50" @click="load">{{ error ? 'Try again' : 'Load more' }}</button>
  </main>
</template>
