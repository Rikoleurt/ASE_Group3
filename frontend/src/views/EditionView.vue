<script setup>
// One release of an edition (workbench, story E): a snapshot that never changes, so this page is
// its permalink, to share and cite. It shows the boxes on the tablet, the reading, who made it and
// what it was merged from.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'

const route = useRoute()
const RELEASE = ref(null)
const ERROR = ref('')
const LOADING = ref(false)

let request = 0
async function load() {
  const mine = ++request
  RELEASE.value = null
  ERROR.value = ''
  LOADING.value = true
  try {
    const response = await fetch(`/api/editions/${encodeURIComponent(route.params.id)}`)
    if (mine !== request) return
    const body = await response.json().catch(() => null)
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The edition could not be loaded.',
      )
    RELEASE.value = body
  } catch (failure) {
    if (mine === request)
      ERROR.value =
        failure instanceof TypeError
          ? "Couldn't reach the server. Check your connection and try again."
          : failure.message
  } finally {
    if (mine === request) LOADING.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })

const TABLET = computed(() => RELEASE.value?.tablet.replaceAll('-', ' ') ?? '')
const TITLE = computed(
  () => RELEASE.value?.title || `${RELEASE.value?.owner}'s edition of ${TABLET.value}`,
)
const DATE = computed(
  () =>
    RELEASE.value &&
    new Date(RELEASE.value.created_at).toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }),
)

function sourceName(source) {
  if (source.kind === 'scholar') return "the scholars' boxes"
  if (source.kind === 'model') return "the model's boxes"
  return `${source.owner}'s ${source.kind === 'edition' ? 'edition' : 'copy'}${source.title ? ` “${source.title}”` : ''}`
}
</script>

<template>
  <main class="mx-auto max-w-5xl px-6 py-10">
    <p v-if="LOADING" role="status">Loading…</p>
    <p v-else-if="ERROR" role="alert" class="text-confidence-low">{{ ERROR }}</p>
    <template v-if="RELEASE">
      <RouterLink :to="`/tablets/${RELEASE.tablet}`" class="underline">← {{ TABLET }}</RouterLink>
      <h1 class="mt-2 text-3xl font-bold">{{ TITLE }}</h1>
      <p class="mt-1 text-ink/70" data-testid="release-meta">
        Release {{ RELEASE.number }} · {{ DATE }} · edited by {{ RELEASE.owner }}
      </p>
      <p
        v-if="RELEASE.contributors.length"
        class="text-sm text-ink/70"
        data-testid="release-contributors"
      >
        Contributors: {{ RELEASE.contributors.join(', ') }}
      </p>
      <p v-if="RELEASE.merged_from.length" class="text-sm text-ink/70">
        Merged from {{ RELEASE.merged_from.map(sourceName).join(', ') }}.
      </p>
      <p v-if="RELEASE.notes" class="mt-3 rounded-lg bg-card p-3">{{ RELEASE.notes }}</p>

      <div class="mt-6 lg:w-3/4">
        <TabletOverlay :signs="RELEASE.reading.signs" :formulas="RELEASE.reading.formulas">
          <img
            :src="`/api${RELEASE.image_url}`"
            :alt="`${TABLET} tracing`"
            class="w-full rounded-lg bg-white"
          />
        </TabletOverlay>
      </div>
      <p class="mt-4">{{ RELEASE.reading.summary }}</p>
      <p class="mt-1" data-testid="release-reading">
        <span class="text-ink/70">Transliteration:</span>
        {{ RELEASE.reading.symbol_interpretation }}
      </p>
      <FractionCheck
        :analysis="{
          ...RELEASE.reading,
          width: RELEASE.width,
          height: RELEASE.height,
          trained: true,
        }"
        class="mt-6"
      />
      <p class="mt-6 text-sm text-ink/70">Drawings: SigLA via lineara.eu, CC BY-NC-SA 4.0.</p>
    </template>
  </main>
</template>
