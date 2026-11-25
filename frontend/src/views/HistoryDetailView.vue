<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import { openCopy } from '../composables/useBoxSet'
import { sessionFetch, sessionUser } from '../state/session'
import AnalysisComment from "@/components/AnalysisComment.vue";
import ShareAnalysis from '../components/ShareAnalysis.vue'
import SymbolDiscussionDialog from '../components/SymbolDiscussionDialog.vue'

const route = useRoute()
const router = useRouter()
const detail = ref(null)
const selectedSymbol = ref(null)

function openSymbolDiscussion(symbol) {
  selectedSymbol.value = symbol
}
const loading = ref(false)
const error = ref('')
// The kept image failed to load (e.g. removed from the server): show the saved results without it.
const imageMissing = ref(false)
const opening = ref(false)
const openError = ref('')

async function correct() {
  opening.value = true
  openError.value = ''
  try {
    await router.push(`/box-sets/${await openCopy(detail.value.id)}`)
  } catch (failure) {
    openError.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  } finally {
    opening.value = false
  }
}
let requestId = 0

async function load() {
  selectedSymbol.value = null
  const request = ++requestId
  loading.value = true
  detail.value = null
  imageMissing.value = false
  error.value = ''
  try {
    const response = await sessionFetch(`/api/users/me/analyses/${encodeURIComponent(route.params.id)}`)
    if (request !== requestId) return
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    if (!response.ok) throw new Error(response.status === 404 ? 'Analysis not found.' : 'This analysis could not be loaded. Please try again.')
    const body = await response.json()
    if (request === requestId) detail.value = body
  } catch (failure) {
    if (request === requestId) error.value = failure.message
  } finally {
    if (request === requestId) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
</script>

<template>
  <main class="px-4 pt-10 pb-10">
    <div class="mx-auto max-w-4xl">
      <RouterLink to="/profile/history" class="underline">← History</RouterLink>
      <h1 class="mt-6 text-3xl font-bold">Saved analysis</h1>
      <p v-if="loading" role="status" class="mt-6">Loading analysis…</p>
      <p v-if="error" role="alert" class="mt-6">{{ error }}</p>
      <button v-if="error && error !== 'Analysis not found.'" class="mt-4 rounded bg-bar px-6 py-2" @click="load">Try again</button>
      <template v-if="detail">
        <section class="mt-6 rounded-3xl bg-card p-6">
          <h2 class="break-all text-xl font-bold">{{ detail.filename }}</h2>
          <p class="mt-2 text-ink/70"><time :datetime="detail.created_at">{{ new Date(detail.created_at).toLocaleString() }}</time> · {{ detail.format }} · {{ (detail.size_bytes / 1024).toFixed(1) }} KiB</p>
          <TabletOverlay v-if="detail.image_url && !imageMissing" class="mt-6" data-testid="history-image" :signs="detail.result.signs" :formulas="detail.result.formulas" can-discuss @discuss="openSymbolDiscussion">
            <img :src="detail.image_url" :alt="detail.filename" class="w-full rounded-lg bg-white" @error="imageMissing = true" />
          </TabletOverlay>
          <p v-else-if="detail.image_url" role="alert" class="mt-4 text-sm text-ink/70">The image could not be loaded. These are the results saved at the time of analysis.</p>
          <p v-else class="mt-4 text-sm text-ink/70">This older analysis has no saved image. Upload and analyze the tablet again to share it.</p>
          <div v-if="detail.image_url && detail.result.trained" class="mt-6">
            <button type="button" class="cursor-pointer rounded bg-bar px-5 py-2 font-semibold hover:brightness-95 disabled:opacity-60" :disabled="opening" data-testid="correct-boxes" @click="correct">
              {{ opening ? 'Opening…' : 'Correct the boxes' }}
            </button>
            <p v-if="openError" role="alert" class="mt-2 text-confidence-low">{{ openError }}</p>
          </div>
          <ShareAnalysis v-if="detail.image_url" :analysis-id="detail.id" :filename="detail.filename" :discussion-id="detail.discussion_id" />
          <p class="mt-6">{{ detail.result.summary }}</p>
          <dl class="mt-4 divide-y divide-ink/10">
            <div class="flex justify-between gap-4 py-3"><dt>Transliteration</dt><dd>{{ detail.result.symbol_interpretation }}</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Confidence</dt><dd>{{ detail.result.confidence }}%</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Processing time</dt><dd>{{ detail.result.time_taken }} s</dd></div>
          </dl>
        </section>
        <section v-if="detail.result.signs.length" class="mt-6 rounded-3xl bg-card p-6">
          <h2 class="text-xl font-bold">Recognized signs</h2>
          <ul class="mt-4 divide-y divide-ink/10">
            <li v-for="sign in detail.result.signs" :key="sign.id" class="flex flex-wrap justify-between gap-3 py-3">
              <span><span class="linear-a text-2xl">{{ sign.glyph }}</span> {{ sign.reading || sign.label }} <span v-if="sign.meaning">— {{ sign.meaning }}</span></span>
              <span>{{ sign.confidence }}%</span>
            </li>
          </ul>
        </section>
        <FractionCheck :analysis="detail.result" class="mt-6" />

        <p class="mt-6 text-sm text-ink/70">History comments below are private and are not included when sharing.</p>
        <AnalysisComment :analysis-id="detail.id" :current-user-id="sessionUser?.id ?? null" />
      </template>
      <SymbolDiscussionDialog v-if="selectedSymbol && detail" :analysis-id="detail.id" :filename="detail.filename" :symbol="selectedSymbol" @close="selectedSymbol = null" />
    </div>
  </main>
</template>
