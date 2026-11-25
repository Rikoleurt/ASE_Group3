<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { communityApi } from '../composables/communityApi'
import LoadingIndicator from '../components/LoadingIndicator.vue'

const discussions = ref([])
const parents = ref(new Map())
const nextCursor = ref(null)
const loaded = ref(false)
const loading = ref(false)
const waitingForSearch = ref(false)
const error = ref('')
const route = useRoute()
function routeSearch() {
  const values = route?.query || {}
  const mode = ['recent', 'tablet', 'author'].includes(values.filter_by) ? values.filter_by : 'recent'
  const id = mode === 'author' && typeof values.author_id === 'string' && /^[1-9][0-9]{0,19}$/.test(values.author_id) ? values.author_id : null
  return { mode, id, text: !id && typeof values.q === 'string' ? values.q.slice(0, 255) : '' }
}
const initialSearch = routeSearch()
const filterBy = ref(initialSearch.mode)
const query = ref(initialSearch.text)
const authorId = ref(initialSearch.id)
function selectFilter(mode) {
  authorId.value = null
  filterBy.value = mode
}
const sentinel = ref(null)
const filters = [
  { value: 'recent', label: 'Most recent' },
  { value: 'tablet', label: 'Tablet name' },
  { value: 'author', label: 'Author' },
]
const busy = computed(() => loading.value || waitingForSearch.value)
let generation = 0
let activeRequest
let searchTimer
let observer

// Parent context never creates a separate result or changes the match order.
const tabletGroups = computed(() => {
  const groups = new Map()
  for (const discussion of discussions.value) {
    let group = groups.get(discussion.analysis_id)
    if (!group) {
      group = { analysisId: discussion.analysis_id, filename: '',
        parent: parents.value.get(discussion.analysis_id) || null, symbols: [] }
      groups.set(discussion.analysis_id, group)
    }
    if (discussion.tablet_filename) group.filename = discussion.tablet_filename
    if (discussion.sign_id == null) group.parent = discussion
    else group.symbols.push(discussion)
  }
  return [...groups.values()]
})

async function loadNextPage() {
  if (busy.value || (loaded.value && !nextCursor.value)) return
  const requestGeneration = generation
  const controller = new AbortController()
  activeRequest = controller
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ limit: '30', filter_by: filterBy.value })
  if (filterBy.value === 'author' && authorId.value) params.set('author_id', authorId.value)
  else if (filterBy.value !== 'recent' && query.value.trim()) params.set('q', query.value.trim())
  if (nextCursor.value) params.set('cursor', nextCursor.value)
  try {
    const page = await communityApi(`/discussions?${params}`, { signal: controller.signal })
    if (requestGeneration !== generation) return
    const items = new Map(discussions.value.map((item) => [item.id, item]))
    for (const item of page.items) items.set(item.id, item)
    discussions.value = [...items.values()]
    for (const parent of page.parents || []) parents.value.set(parent.analysis_id, parent)
    nextCursor.value = page.next_cursor
    loaded.value = true
  } catch (failure) {
    if (requestGeneration === generation && !controller.signal.aborted) error.value = failure.message
  } finally {
    if (requestGeneration === generation) {
      loading.value = false
      activeRequest = null
      // Re-observe after rendering. If a short page still leaves the marker in
      // view, the observer requests one more page until the viewport is filled.
      await nextTick()
      if (requestGeneration === generation && observer && sentinel.value) {
        observer.unobserve(sentinel.value)
        observer.observe(sentinel.value)
      }
    }
  }
}

function restartSearch(delay = 0) {
  generation++
  activeRequest?.abort()
  activeRequest = null
  clearTimeout(searchTimer)
  discussions.value = []
  parents.value = new Map()
  nextCursor.value = null
  loaded.value = false
  loading.value = false
  error.value = ''
  waitingForSearch.value = delay > 0
  if (delay) {
    searchTimer = setTimeout(() => {
      waitingForSearch.value = false
      loadNextPage()
    }, delay)
  } else loadNextPage()
}

watch(() => route?.query, () => {
  const search = routeSearch()
  filterBy.value = search.mode
  authorId.value = search.id
  query.value = search.text
})
watch([filterBy, query, authorId], ([mode], [previousMode]) => restartSearch(mode === previousMode ? 300 : 0))
onMounted(() => {
  if (typeof IntersectionObserver !== 'undefined') {
    observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting) && loaded.value && !error.value) loadNextPage()
    }, { rootMargin: '200px' })
    observer.observe(sentinel.value)
  }
  loadNextPage()
})
onBeforeUnmount(() => {
  generation++
  clearTimeout(searchTimer)
  activeRequest?.abort()
  observer?.disconnect()
})
</script>

<template>
  <main class="mx-auto max-w-5xl px-6 py-10">
    <h1 class="text-3xl font-bold">Community</h1>
    <p class="mt-2 text-ink/70">Explore shared tablets and symbols, and discuss the model’s readings.</p>
    <RouterLink to="/analysis" class="mt-4 inline-block underline">Analyze a tablet to share →</RouterLink>
    <div class="mt-6 flex flex-wrap items-center justify-between gap-4">
      <div role="group" aria-label="Filter discussions" class="flex flex-wrap gap-2">
        <button v-for="filter in filters" :key="filter.value" type="button" :aria-pressed="filterBy === filter.value"
          class="cursor-pointer rounded-lg border border-ink/20 px-4 py-2 font-semibold hover:bg-bar focus-visible:outline-2 focus-visible:outline-offset-2"
          :class="filterBy === filter.value ? 'bg-bar' : 'bg-card'" @click="selectFilter(filter.value)">
          {{ filter.label }}
        </button>
      </div>
      <form v-if="filterBy !== 'recent'" role="search" class="w-full sm:ml-auto sm:w-72" @submit.prevent="restartSearch()">
        <label for="discussion-search" class="sr-only">{{ filterBy === 'tablet' ? 'Search by tablet name' : 'Search by author' }}</label>
        <input id="discussion-search" v-model="query" type="search" @input="authorId = null" maxlength="255" autocomplete="off"
          :placeholder="filterBy === 'tablet' ? 'Search tablet names…' : 'Search authors…'"
          class="w-full rounded-lg border border-ink/30 bg-card px-4 py-2 focus-visible:outline-2 focus-visible:outline-offset-2" />
      </form>
    </div>
    <p v-if="authorId" class="mt-3 text-sm text-ink/70">Showing discussions by the mentioned user. <button type="button" class="hover:underline" @click="authorId = null">Clear author selection</button></p>
    <ul v-if="tabletGroups.length" :aria-busy="busy" aria-label="Tablet discussions" class="mt-8 space-y-4">
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
    <p v-else-if="loaded && !busy" class="mt-8 rounded-2xl bg-card p-6">
      {{ filterBy === 'recent' || !query.trim() ? 'No discussions yet. Share an analysis to start the conversation.' : 'No discussions match your search.' }}
    </p>
    <LoadingIndicator v-if="busy" class="mt-6" :label="waitingForSearch ? 'Searching discussions…' : 'Loading discussions…'" />
    <p v-if="error" role="alert" class="mt-6 text-conf-low">{{ error }}</p>
    <button v-if="error || nextCursor" type="button" :disabled="busy" class="mt-6 rounded bg-bar px-6 py-2 disabled:opacity-50" @click="loadNextPage">{{ error ? 'Try again' : 'Load more' }}</button>
    <p v-if="loaded && discussions.length && !nextCursor && !busy" class="mt-6 text-sm text-ink/70">All matching discussions have been loaded.</p>
    <div ref="sentinel" aria-hidden="true" class="h-px" />
  </main>
</template>
