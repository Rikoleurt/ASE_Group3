<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ColumnBars from '../components/benchmarks/ColumnBars.vue'
import CoverageChart from '../components/benchmarks/CoverageChart.vue'
import GlyphGrid from '../components/benchmarks/GlyphGrid.vue'
import MetricTiles from '../components/benchmarks/MetricTiles.vue'
import TabletGrid from '../components/benchmarks/TabletGrid.vue'
import { BUCKET_LABELS, BUCKET_ORDER, GRADIENT, NO_DATA, bestVersion, gridMode, headline, pct, rankVersions, worstToBest } from '../components/benchmarks/benchmarkData'

const STEP_MS = 1500

const versions = ref([])
const selected = ref('')
const data = ref(null)
const loading = ref(true)
const error = ref('')
const detailError = ref('')
const cache = new Map()
let loadToken = 0

// Playback: 'idle' | 'playing' | 'paused'
const mode = ref('idle')
const order = ref([])
const step = ref(-1)
const finished = ref(false)
let timer = null
let restore = ''
let playToken = 0
const skipped = ref([])

const reduceMotion = ref(false)
let motionQuery = null
const onMotionChange = (event) => { reduceMotion.value = event.matches }

async function getJson(url, what) {
  let response
  try {
    response = await fetch(url)
  } catch {
    throw new Error(`The ${what} could not be loaded. Is the server running?`)
  }
  if (!response.ok) {
    let detail = ''
    try { detail = (await response.json()).detail ?? '' } catch { /* no body */ }
    throw new Error(detail || `The ${what} could not be loaded (error ${response.status}).`)
  }
  return response.json()
}

async function fetchVersion(name) {
  if (!cache.has(name)) cache.set(name, await getJson(`/api/benchmarks/${encodeURIComponent(name)}`, `results for ${name}`))
  return cache.get(name)
}

async function select(name) {
  selected.value = name
  const token = ++loadToken
  detailError.value = ''
  try {
    const doc = await fetchVersion(name)
    if (token === loadToken) data.value = doc
  } catch (failure) {
    if (token === loadToken) detailError.value = failure.message
  }
}

async function loadIndex() {
  loading.value = true
  error.value = ''
  try {
    const index = await getJson('/api/benchmarks', 'benchmark list')
    versions.value = index.versions ?? []
    const best = bestVersion(versions.value)
    if (best) await select(best.version)
  } catch (failure) {
    error.value = failure.message
  } finally {
    loading.value = false
  }
}

function clearTimer() {
  if (timer !== null) clearTimeout(timer)
  timer = null
}

function onPick(name) {
  if (mode.value !== 'idle') { playToken++; halt() }
  finished.value = false
  step.value = -1
  select(name)
}

function halt() {
  clearTimer()
  mode.value = 'idle'
}

function schedule() {
  clearTimer()
  timer = setTimeout(advance, STEP_MS)
}

function show(index) {
  step.value = index
  const name = order.value[index].version
  selected.value = name
  const doc = cache.get(name)
  if (doc) { data.value = doc; detailError.value = '' }
}

function advance() {
  if (mode.value !== 'playing') return
  if (step.value + 1 >= order.value.length) {
    halt()
    finished.value = true
    return
  }
  show(step.value + 1)
  schedule()
}

async function play() {
  if (mode.value !== 'idle' || !versions.value.length) return
  const token = ++playToken
  const wanted = worstToBest(versions.value)
  restore = selected.value
  finished.value = false
  detailError.value = ''
  skipped.value = []
  order.value = wanted
  mode.value = 'playing'
  step.value = -1
  const results = await Promise.allSettled(wanted.map((entry) => fetchVersion(entry.version)))
  if (token !== playToken || mode.value !== 'playing') return
  skipped.value = wanted.filter((_, i) => results[i].status === 'rejected').map((entry) => entry.version)
  order.value = wanted.filter((_, i) => results[i].status === 'fulfilled')
  if (!order.value.length) {
    mode.value = 'idle'
    detailError.value = 'None of the versions could be loaded for playback.'
    return
  }
  loadToken++
  show(0)
  schedule()
}

function togglePause() {
  if (mode.value === 'playing') {
    clearTimer()
    mode.value = 'paused'
  } else if (mode.value === 'paused') {
    mode.value = 'playing'
    schedule()
  }
}

function stop() {
  playToken++
  halt()
  finished.value = false
  step.value = -1
  if (restore) select(restore)
}

onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    reduceMotion.value = motionQuery.matches
    motionQuery.addEventListener?.('change', onMotionChange)
  }
  loadIndex()
})
onBeforeUnmount(() => {
  playToken++
  clearTimer()
  motionQuery?.removeEventListener?.('change', onMotionChange)
})

const scoreText = (entry) => {
  const h = headline(entry)
  return h.value == null ? 'no score' : `${pct(h.value)} ${h.fallback ? 'named' : 'read'}`
}
const optionText = (entry) => `${entry.version} — ${scoreText(entry)}${headline(entry).fallback && headline(entry).value != null ? ' (identification only)' : ''}`

const grids = computed(() => gridMode(data.value))
const tiers = computed(() => rankVersions(versions.value))
const tierOfProgress = computed(() => (progressEntry.value ? headline(progressEntry.value).fallback : false))
const current = computed(() => (data.value && data.value.version === selected.value ? data.value : null))
const playing = computed(() => mode.value !== 'idle')
const showProgress = computed(() => playing.value || finished.value)
const progressEntry = computed(() => (step.value >= 0 ? order.value[step.value] : null))

const bucketBars = computed(() => {
  const d = current.value
  if (!d) return []
  const keys = Object.keys(d.by_bucket ?? {})
  const sorted = [...BUCKET_ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !BUCKET_ORDER.includes(k))]
  return sorted.map((k) => ({ key: k, label: BUCKET_LABELS[k] ?? k, value: d.by_bucket[k], count: d.bucket_counts?.[k] }))
})
const roleBars = computed(() => {
  const d = current.value
  if (!d) return []
  const counts = {}
  for (const s of d.signs ?? []) counts[s.role] = (counts[s.role] ?? 0) + (s.n ?? 0)
  return Object.keys(d.by_role ?? {}).sort().map((k) => ({ key: k, label: k, value: d.by_role[k], count: counts[k] }))
})
const cost = computed(() => {
  const c = current.value?.cost ?? {}
  return [
    { key: 'latency', label: 'CPU time per tablet', value: c.latency_s != null ? `${c.latency_s.toFixed(2)} s` : null },
    { key: 'weights', label: 'Model weights', value: c.weights_mb != null ? `${c.weights_mb.toFixed(1)} MB` : null },
    { key: 'train', label: 'Training time', value: c.train_minutes != null ? `${Math.round(c.train_minutes)} min` : null },
  ]
})
</script>

<template>
  <main class="mx-auto max-w-6xl px-4 py-8 sm:px-6" :class="{ 'reduce-motion': reduceMotion }" :data-reduce-motion="reduceMotion">
    <h1 class="text-3xl font-bold">Benchmarks</h1>
    <p class="mt-2 max-w-3xl text-ink/80">
      How each version of the sign reader does on the same tablets. Every version is scored the same way and compared with the released reader.
    </p>

    <p v-if="loading" role="status" class="mt-6">Loading benchmark results…</p>
    <div v-else-if="error" role="alert" class="mt-6 rounded-2xl bg-card p-5">
      <p>{{ error }}</p>
      <button type="button" class="mt-3 cursor-pointer rounded bg-bar px-5 py-2 hover:brightness-95" @click="loadIndex">Try again</button>
    </div>
    <p v-else-if="!versions.length" class="mt-6 rounded-2xl bg-card p-5">No benchmark results have been published yet.</p>

    <template v-else>
      <section class="mt-6 flex flex-wrap items-end gap-4" aria-label="Version and playback">
        <label class="flex min-w-0 flex-col text-sm font-semibold">Model version
          <select
            :value="selected"
            class="mt-1 max-w-full rounded border border-ink/30 bg-page px-3 py-2 text-base font-normal"
            data-testid="version-select"
            @change="onPick($event.target.value)"
          >
            <optgroup v-if="tiers.endToEnd.length" label="Read end to end">
              <option v-for="v in tiers.endToEnd" :key="v.version" :value="v.version">{{ optionText(v) }}</option>
            </optgroup>
            <optgroup v-if="tiers.idOnly.length" label="Named on true boxes only (not comparable with the group above)">
              <option v-for="v in tiers.idOnly" :key="v.version" :value="v.version">{{ optionText(v) }}</option>
            </optgroup>
            <optgroup v-if="tiers.unscored.length" label="No score (skipped in playback)">
              <option v-for="v in tiers.unscored" :key="v.version" :value="v.version">{{ optionText(v) }}</option>
            </optgroup>
          </select>
        </label>
        <div class="flex flex-wrap items-center gap-2">
          <button v-if="!playing" type="button" class="cursor-pointer rounded bg-bar px-5 py-2 font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2" data-testid="play" @click="play">
            Play worst → best
          </button>
          <template v-else>
            <button type="button" class="cursor-pointer rounded bg-bar px-5 py-2 font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2" data-testid="pause" @click="togglePause">
              {{ mode === 'paused' ? 'Resume' : 'Pause' }}
            </button>
            <button type="button" class="cursor-pointer rounded bg-card px-5 py-2 font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2" data-testid="stop" @click="stop">Stop</button>
          </template>
        </div>
      </section>

      <div v-if="showProgress" class="mt-3 max-w-xl" data-testid="progress">
        <progress class="h-2 w-full" :value="Math.max(step + 1, 0)" :max="order.length" aria-label="Progress through the versions" />
        <p role="status" class="mt-1 text-sm">
          <template v-if="progressEntry">
            <strong>Version {{ step + 1 }} of {{ order.length }}: {{ progressEntry.version }}</strong>,
            {{ scoreText(progressEntry) }}
            <span v-if="tierOfProgress" class="rounded bg-card px-1" data-testid="tier-note">named on true boxes, not comparable with the end-to-end versions before it</span>
            <span v-if="mode === 'paused'"> (paused)</span>
            <span v-if="finished"> (done, best version)</span>
          </template>
          <template v-else>Loading all versions…</template>
        </p>
      </div>

      <p v-if="skipped.length" role="status" class="mt-2 text-sm" data-testid="skipped">Skipped in playback (could not be loaded): {{ skipped.join(', ') }}</p>

      <p v-if="detailError" role="alert" class="mt-4 rounded-2xl bg-card p-4">{{ detailError }}</p>

      <template v-if="current">
        <section class="mt-5 rounded-2xl bg-card p-4" aria-label="About this version">
          <h2 class="text-xl font-bold">{{ current.version }}</h2>
          <p class="mt-1">{{ current.description }}</p>
          <p class="mt-1 text-sm text-ink/80" data-testid="meta">
            Scored on the {{ current.split }} split · {{ current.tablets }} tablets · compared with {{ current.reference }}
            <span v-if="current.stages && !current.stages.detection"> · identification only</span>
            <span v-else-if="current.stages && !current.stages.identification && current.kind !== 'one_stage'"> · detection only</span>
          </p>
        </section>

        <h2 class="mt-8 text-2xl font-bold">Across the corpus</h2>
        <div class="mt-3"><MetricTiles :version="current" /></div>

        <section class="mt-8" aria-labelledby="glyphs-h">
          <h3 id="glyphs-h" class="text-xl font-bold">Every sign</h3>
          <p v-if="grids" class="text-sm text-ink/80">
            Each tile is one sign, coloured by how often it is {{ grids === 'id' ? 'named correctly when the box is right' : 'read correctly end to end' }}.
          </p>
          <p v-if="!grids" class="mt-2 rounded-2xl bg-card p-4" data-testid="grid-note">Not measured: this version finds signs but does not name them, so there is no per-sign result.</p>
          <div v-if="grids" class="mt-2 flex flex-wrap items-center gap-3 text-sm" aria-label="Colour legend" data-testid="legend">
            <span>0%</span>
            <span class="inline-block h-3 w-40 rounded border border-ink/25" :style="{ backgroundImage: GRADIENT }" role="img" aria-label="Colour scale from 0% accuracy (light) to 100% (dark)" />
            <span>100%</span>
            <span class="inline-flex items-center gap-1"><span class="inline-block h-3 w-3 rounded-sm border border-dashed border-ink/40" :style="{ backgroundColor: NO_DATA.bg }" />no examples</span>
          </div>
          <div v-if="grids" class="mt-3"><GlyphGrid :signs="current.signs ?? []" :mode="grids" :reduce-motion="reduceMotion" /></div>
        </section>

        <section v-if="grids" class="mt-8" aria-labelledby="tablets-h">
          <h3 id="tablets-h" class="text-xl font-bold">Every tablet</h3>
          <p class="text-sm text-ink/80">
            One cell per tablet, coloured by the share of its signs {{ grids === 'id' ? 'named correctly' : 'read correctly' }} (same scale as above). Hover for counts.
          </p>
          <div v-if="grids" class="mt-3"><TabletGrid :tablets="current.tablet_results ?? []" :mode="grids" :reduce-motion="reduceMotion" /></div>
        </section>

        <section class="mt-8 grid gap-8 md:grid-cols-2" aria-label="Accuracy by group">
          <ColumnBars title="Named correctly, by training examples" :bars="bucketBars" :reduce-motion="reduceMotion" empty="This version does not identify signs." />
          <ColumnBars title="Named correctly, by sign role" :bars="roleBars" :reduce-motion="reduceMotion" empty="This version does not identify signs." />
        </section>

        <section v-if="current.coverage_curve?.length" class="mt-8"><CoverageChart :points="current.coverage_curve" /></section>

        <section class="mt-8" aria-labelledby="cost-h">
          <h3 id="cost-h" class="text-xl font-bold">Cost</h3>
          <dl class="mt-2 flex flex-wrap gap-x-8 gap-y-2" data-testid="cost">
            <div v-for="c in cost" :key="c.key">
              <dt class="text-sm text-ink/80">{{ c.label }}</dt>
              <dd class="text-lg font-semibold tabular-nums">{{ c.value ?? '—' }}</dd>
            </div>
          </dl>
        </section>
      </template>
      <p v-else-if="!detailError" role="status" class="mt-6">Loading {{ selected }}…</p>
    </template>
  </main>
</template>
