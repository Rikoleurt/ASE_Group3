<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import { sessionFetch } from '../state/session'
import AnalysisComment from "@/components/AnalysisComment.vue";

const route = useRoute()
const router = useRouter()
const detail = ref(null)
const loading = ref(false)
const error = ref('')
let requestId = 0

async function load() {
  const request = ++requestId
  loading.value = true
  detail.value = null
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
      <button v-if="error" class="mt-4 rounded bg-bar px-6 py-2" @click="load">Try again</button>
      <template v-if="detail">
        <section class="mt-6 rounded-3xl bg-card p-6">
          <h2 class="break-all text-xl font-bold">{{ detail.filename }}</h2>
          <p class="mt-2 text-ink/70"><time :datetime="detail.created_at">{{ new Date(detail.created_at).toLocaleString() }}</time> · {{ detail.format }} · {{ (detail.size_bytes / 1024).toFixed(1) }} KiB</p>
          <p class="mt-4 text-sm text-ink/70">The original image is not retained. These are the results saved at the time of analysis.</p>
          <p class="mt-6">{{ detail.result.summary }}</p>
          <dl class="mt-4 divide-y divide-ink/10">
            <div class="flex justify-between gap-4 py-3"><dt>Interpretation</dt><dd>{{ detail.result.symbol_interpretation }}</dd></div>
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

        <AnalysisComment :analysis-id="detail.id" />
      </template>
    </div>
  </main>
</template>
