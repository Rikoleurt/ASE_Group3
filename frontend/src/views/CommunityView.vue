<script setup>
import { computed, onMounted, ref } from 'vue'
import { communityApi } from '../composables/communityApi'

const discussions = ref([])
const before = ref(null)
const loaded = ref(false)
const loading = ref(false)
const error = ref('')

// A symbol can arrive before its tablet thread on an older page. Keep a
// filename heading until that thread is loaded, then make the heading a link.
// Map insertion order follows the most recent discussion in each tablet group.
const tabletGroups = computed(() => {
  const groups = new Map()
  for (const discussion of discussions.value) {
    let group = groups.get(discussion.analysis_id)
    if (!group) {
      group = { analysisId: discussion.analysis_id, filename: '', parent: null, symbols: [] }
      groups.set(discussion.analysis_id, group)
    }
    if (discussion.tablet_filename) group.filename = discussion.tablet_filename
    if (discussion.sign_id == null) group.parent = discussion
    else group.symbols.push(discussion)
  }
  return [...groups.values()]
})

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
    <p class="mt-2 text-ink/70">Explore shared tablets and symbols, and discuss the model’s readings.</p>
    <RouterLink to="/analysis" class="mt-4 inline-block underline">Analyze a tablet to share →</RouterLink>
    <ul v-if="tabletGroups.length" aria-label="Tablet discussions" class="mt-8 space-y-4">
      <li v-for="group in tabletGroups" :key="group.analysisId" :data-analysis-id="group.analysisId" class="overflow-hidden rounded-2xl bg-card">
        <RouterLink v-if="group.parent" :to="`/community/${group.parent.id}`" class="block px-6 py-5 hover:bg-bar focus-visible:bg-bar">
          <p class="text-xs font-semibold uppercase tracking-wide text-ink/70">Tablet</p>
          <h2 class="mt-1 break-words text-lg font-semibold">{{ group.parent.title }}</h2>
          <p class="mt-1 text-sm text-ink/70">{{ group.parent.author_username }}</p>
        </RouterLink>
        <div v-else class="px-6 py-5">
          <p class="text-xs font-semibold uppercase tracking-wide text-ink/70">Tablet</p>
          <h2 class="mt-1 break-words text-lg font-semibold">{{ group.filename || `Tablet ${group.analysisId}` }}</h2>
        </div>
        <ul v-if="group.symbols.length" :aria-label="`Symbol discussions for ${group.filename || group.parent?.title || group.analysisId}`" class="mx-6 mb-5 border-l-2 border-ink/20 pl-4 sm:ml-8">
          <li v-for="symbol in group.symbols" :key="symbol.id" class="relative before:absolute before:-left-4 before:top-7 before:w-4 before:border-t-2 before:border-ink/20">
            <RouterLink :to="`/community/${symbol.id}`" class="block rounded-lg px-4 py-3 hover:bg-bar focus-visible:bg-bar">
              <div class="flex flex-wrap items-center gap-2">
                <span class="rounded bg-ink/10 px-2 py-0.5 text-xs font-semibold">Symbol</span>
                <h3 class="break-words font-semibold">{{ symbol.title }}</h3>
              </div>
              <p v-if="symbol.symbol_name && symbol.symbol_name !== symbol.title" class="mt-1 text-sm text-ink/70">Model reading: {{ symbol.symbol_name }}</p>
              <p class="mt-1 text-sm text-ink/70">{{" Author : " + symbol.author_username }}</p>
            </RouterLink>
          </li>
        </ul>
      </li>
    </ul>
    <p v-else-if="loaded" class="mt-8 rounded-2xl bg-card p-6">No discussions yet. Share an analysis to start the conversation.</p>
    <p v-if="loading" role="status" class="mt-6">Loading discussions…</p>
    <p v-if="error" role="alert" class="mt-6 text-conf-low">{{ error }}</p>
    <button v-if="error || before" type="button" :disabled="loading" class="mt-6 rounded bg-bar px-6 py-2 disabled:opacity-50" @click="load">{{ error ? 'Try again' : 'Load more' }}</button>
  </main>
</template>
