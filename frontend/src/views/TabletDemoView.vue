<script setup>
import { computed, onMounted, ref } from 'vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import GlyphOccurrencesPane from '../components/glyphs/GlyphOccurrencesPane.vue'

const tablet = ref({ imageUrl: '/api/tablet-demo/ht13?annotated=false' })
const symbols = ref([
  { id: 1, label: 'ha', confidence: 72, imageUrl: '', box: { x: 0.12, y: 0.1, w: 0.14, h: 0.08 } },
  { id: 2, label: 'lo', confidence: 15, imageUrl: '', box: { x: 0.32, y: 0.1, w: 0.12, h: 0.1 } },
  { id: 3, label: 'sa', confidence: 99, imageUrl: '', box: { x: 0.55, y: 0.1, w: 0.14, h: 0.12 } },
  { id: 4, label: 'es', confidence: 98, imageUrl: '', box: { x: 0.15, y: 0.4, w: 0.14, h: 0.08 } },
  { id: 5, label: 'an', confidence: 93, imageUrl: '', box: { x: 0.4, y: 0.4, w: 0.12, h: 0.1 } },
  { id: 6, label: 'en', confidence: 56, imageUrl: '', box: { x: 0.65, y: 0.4, w: 0.14, h: 0.12 } },
])
const predictions = ref([])
const activeId = ref(null)
const loading = ref(false)
const error = ref('')
const imageLoaded = ref(false)

// Clicking a detected box opens the other-tablets pane for the sign the reader chose.
const selection = computed(() => {
  const symbol = predictions.value.find((item) => item.id === activeId.value)
  const sign = symbol?.candidates?.[0]?.sign
  return sign ? { sign, candidates: symbol.candidates, crop: symbol.imageUrl || null } : null
})

function select(symbol) {
  activeId.value = symbol.id
}

// The predictions as the Analysis page's overlay draws them: one box per sign, coloured by
// role, with the hover card (glyph, reading, confidence, runner-up readings).
const characters = ref({})
const ROLE_ORDER = ['fraction', 'syllabogram', 'logogram']
const overlaySigns = computed(() => predictions.value.map((symbol) => {
  const top = symbol.candidates?.[0] ?? null
  const roles = top?.roles ?? []
  const reading = /\(([^)]+)\)$/.exec(top?.label ?? '')?.[1] ?? null
  return {
    id: symbol.id,
    box: symbol.box,
    sign: top?.sign ?? null,
    label: symbol.label,
    reading,
    role: ROLE_ORDER.find((role) => roles.includes(role)) ?? roles[0] ?? 'other',
    glyph: top ? characters.value[top.sign] ?? null : null,
    confidence: symbol.confidence,
    candidates: symbol.candidates ?? [],
  }
}))

async function loadCharacters() {
  const signs = [...new Set(predictions.value.map((symbol) => symbol.candidates?.[0]?.sign).filter(Boolean))]
  if (!signs.length) return
  try {
    const response = await fetch(`/api/glyphs/characters?signs=${signs.join(',')}`)
    if (response.ok) characters.value = await response.json()
  } catch {
    // The glyphs are decoration: the boxes and readings stand without them.
  }
}

async function loadPredictions() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/tablet-demo/ht13/predictions')
    if (!response.ok) {
      error.value = 'Predictions could not be loaded. Please try again.'
      return
    }
    const data = await response.json()
    predictions.value = data.predictions.map((symbol) => ({
      ...symbol, confidence: Number(symbol.confidence.toFixed(1)),
    }))
    loadCharacters()
  } catch {
    error.value = 'Unable to reach the server. Check your connection and try again.'
  } finally {
    loading.value = false
  }
}

function confidenceClass(confidence) {
  if (confidence >= 90) return 'text-confidence-high'
  if (confidence >= 60) return 'text-confidence-mid'
  return 'text-confidence-low'
}

function learnMore(symbol) {
  console.log('Placeholder for learn more operation', symbol.label)
}

onMounted(loadPredictions)
</script>

<template>
  <main class="flex flex-col gap-6 p-6 md:h-[calc(100vh-60px)] md:flex-row">
    
    <section class="md:w-1/3 md:overflow-y-auto">
      <div class="relative">
        <TabletOverlay
          v-if="tablet.imageUrl"
          :signs="imageLoaded ? overlaySigns : []"
          :formulas="[]"
          :selected-id="activeId"
          @select="select"
        >
          <img
            :src="tablet.imageUrl"
            alt="HT13 tablet"
            @load="imageLoaded = true"
            @error="tablet.imageUrl = ''; imageLoaded = false"
            class="block w-full"
          />
        </TabletOverlay>
        <div
          v-else
          role="alert"
          class="flex aspect-[3/4] w-full items-center justify-center rounded-lg bg-card p-4 text-center text-ink/70"
        >
          There was an issue loading the tablet image.
        </div>

      </div>
      <p v-if="loading" role="status">Loading predictions…</p>
      <template v-else-if="error">
        <p role="alert">{{ error }}</p>
        <button type="button" @click="loadPredictions">Try again</button>
      </template>
      <p v-else-if="!predictions.length" role="status">No detections found on HT13.</p>
      <RouterLink to="/tablet-reading" class="mt-3 inline-block font-bold underline hover:text-accent">
        Read this tablet: transcription and arithmetic check
      </RouterLink>
    </section>

    <div class="hidden w-0.5 bg-ink md:block" />

    <section class="rounded-3xl bg-card p-6 md:flex-1 md:overflow-y-auto">
      <ul class="grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-3">
        <li
          v-for="symbol in symbols"
          :key="symbol.id"
          class="text-sm"
        >
          <div class="mb-2 h-40 overflow-hidden rounded bg-page">
            <img
              v-if="symbol.imageUrl"
              :src="symbol.imageUrl"
              class="h-full w-full object-contain"
            />
            <div v-else class="flex h-full w-full items-center justify-center p-4 text-center text-ink/70">
              There was an issue loading the symbol image.
            </div>
          </div>

          <p class="font-bold">Symbol: {{ symbol.label }}</p>
          <p class="font-bold">
            Confidence:
            <span :class="confidenceClass(symbol.confidence)">
              {{ symbol.confidence }}
            </span>%
          </p>
          <button
            type="button"
            class="cursor-pointer font-bold underline hover:text-accent"
            @click="learnMore(symbol)"
          >
            Learn More
          </button>
        </li>
      </ul>
    </section>
  </main>
  <GlyphOccurrencesPane :selection="selection" class="mx-6 mb-6" />
</template>
