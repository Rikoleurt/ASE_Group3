<script setup>
import { onMounted, ref } from 'vue'

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
        <img
          v-if="tablet.imageUrl"
          :src="tablet.imageUrl"
          alt="HT13 tablet"
          @load="imageLoaded = true"
          @error="tablet.imageUrl = ''; imageLoaded = false"
          class="block w-full"
        />
        <div
          v-else
          role="alert"
          class="flex aspect-[3/4] w-full items-center justify-center rounded-lg bg-card p-4 text-center text-ink/70"
        >
          There was an issue loading the tablet image.
        </div>

        <template v-if="tablet.imageUrl && imageLoaded">
          <div
            v-for="symbol in predictions"
            :key="symbol.id"
            data-testid="prediction-box"
            class="pointer-events-none absolute"
            :class="
              activeId === symbol.id
                ? 'border-2 border-accent bg-accent/30'
                : 'border border-red-500'
            "
            :style="{
              left: symbol.box.x * 100 + '%',
              top: symbol.box.y * 100 + '%',
              width: symbol.box.w * 100 + '%',
              height: symbol.box.h * 100 + '%',
            }"
          />
        </template>
      </div>
      <p v-if="loading" role="status">Loading predictions…</p>
      <template v-else-if="error">
        <p role="alert">{{ error }}</p>
        <button type="button" @click="loadPredictions">Try again</button>
      </template>
      <p v-else-if="!predictions.length" role="status">No detections found on HT13.</p>
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
</template>