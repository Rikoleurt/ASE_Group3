<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ColumnBars from '../components/benchmarks/ColumnBars.vue'
import CoverageChart from '../components/benchmarks/CoverageChart.vue'
import GlyphGrid from '../components/benchmarks/GlyphGrid.vue'
import MetricTiles from '../components/benchmarks/MetricTiles.vue'
import TabletGrid from '../components/benchmarks/TabletGrid.vue'
import GlyphOccurrencesPane from '../components/glyphs/GlyphOccurrencesPane.vue'
import { BUCKET_LABELS, BUCKET_ORDER, BUCKET_SHORT, GRADIENT, NO_DATA, bestVersion, gridMode, headline, pct, rankVersions, worstToBest } from '../components/benchmarks/benchmarkData'

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

// Side by side, the tablet grid starts at the same height as the glyph grid: measure where
// each would start and pad the higher one (usually the tablet grid, below the bar charts).
const gridsRow = ref(null)
const tabletPad = ref(0)
const glyphPad = ref(0)
// The grids row keeps the tallest height it has had (versions differ in sign count), so the
// page below it does not jump while switching or playing; a window resize starts over.
const rowMin = ref(0)
const tabletMin = ref(0) // likewise for the tablet grid, so the charts under it stay put
let resizer = null
function onWindowResize() { rowMin.value = 0; tabletMin.value = 0 }
function alignGrids() {
  const row = gridsRow.value
  if (row) rowMin.value = Math.max(rowMin.value, Math.round(row.getBoundingClientRect().height))
  const block = row?.querySelector('[data-testid="tablet-block"]')
  if (block) tabletMin.value = Math.max(tabletMin.value, Math.round(block.getBoundingClientRect().height))
  const glyphs = row?.querySelector('[data-testid="glyph-grid"]')
  const tablets = row?.querySelector('[data-testid="tablet-grid"]')
  if (!glyphs || !tablets) return
  const sideBySide = glyphs.getBoundingClientRect().left < tablets.getBoundingClientRect().left - 1
  // Where each grid would start unpadded; pad the higher one down to the other.
  const diff = (glyphs.getBoundingClientRect().top - glyphPad.value) - (tablets.getBoundingClientRect().top - tabletPad.value)
  tabletPad.value = sideBySide ? Math.max(0, Math.round(diff)) : 0
  glyphPad.value = sideBySide ? Math.max(0, Math.round(-diff)) : 0
}

// The row appears once a version has loaded; observe it from then on, and re-align on every version.
watch(gridsRow, (el, old) => {
  if (old) resizer?.unobserve(old)
  if (el) resizer?.observe(el)
})

onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    reduceMotion.value = motionQuery.matches
    motionQuery.addEventListener?.('change', onMotionChange)
  }
  if (typeof ResizeObserver !== 'undefined') resizer = new ResizeObserver(() => alignGrids())
  window.addEventListener?.('resize', onWindowResize)
  window.addEventListener?.('keydown', onKey)
  loadIndex()
})
onBeforeUnmount(() => {
  playToken++
  clearTimer()
  motionQuery?.removeEventListener?.('change', onMotionChange)
  resizer?.disconnect()
  window.removeEventListener?.('resize', onWindowResize)
  window.removeEventListener?.('keydown', onKey)
})

const scoreText = (entry) => {
  const h = headline(entry)
  return h.value == null ? 'no score' : `${pct(h.value)} ${h.fallback ? 'named' : 'read'}`
}
// Clicking a sign opens its occurrences and comments (the same pane as on the tablet pages).
// Its tabs offer the sign and the signs it is most often confused with in this version.
const picked = ref(null)
function pick(s) {
  if (s.sign === 'unidentified') return // no sign ID, so no occurrences to list
  picked.value = picked.value?.sign === s.sign ? null : s
}
function unpick() { picked.value = null }
const selection = computed(() => {
  const s = picked.value
  if (!s) return null
  const candidates = [{ sign: s.sign, label: s.sign }, ...(s.confused_with ?? []).map((c) => ({ sign: c.sign, label: c.sign }))]
  return { sign: s.sign, candidates, ...(s.drawing ? { reference: s.drawing } : {}) }
})
// The pane scrolls inside the column rather than lengthening the page.
const paneMax = 'max(20rem, calc(100vh - 8.5rem))' // the window below the header, minus the pane title
function onKey(e) { if (e.key === 'Escape' && picked.value) unpick() }
const aboutVersion = computed(() => {
  const c = current.value
  if (!c) return ''
  const only = c.stages && !c.stages.detection ? ' · identification only'
    : c.stages && !c.stages.identification && c.kind !== 'one_stage' ? ' · detection only' : ''
  return `${c.version}: ${c.description} · ${c.split} split · ${c.tablets} tablets · vs ${c.reference}${only}`
})
const optionText = (entry) => `${entry.version} — ${scoreText(entry)}${headline(entry).fallback && headline(entry).value != null ? ' (identification only)' : ''}`

const grids = computed(() => gridMode(data.value))
const tiers = computed(() => rankVersions(versions.value))
const current = computed(() => (data.value && data.value.version === selected.value ? data.value : null))
watch(() => current.value, () => nextTick(alignGrids))
const playing = computed(() => mode.value !== 'idle')
const showProgress = computed(() => playing.value || finished.value)
const progressEntry = computed(() => (step.value >= 0 ? order.value[step.value] : null))

const bucketBars = computed(() => {
  const d = current.value
  if (!d) return []
  const keys = Object.keys(d.by_bucket ?? {})
  const sorted = [...BUCKET_ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !BUCKET_ORDER.includes(k))]
  return sorted.map((k) => ({ key: k, label: BUCKET_LABELS[k] ?? k, short: BUCKET_SHORT[k], value: d.by_bucket[k], count: d.bucket_counts?.[k] }))
})
const roleBars = computed(() => {
  const d = current.value
  if (!d) return []
  // True signs per role as published (role_counts); older files fall back to summing per-sign counts.
  let counts = d.role_counts
  if (!counts || !Object.keys(counts).length) {
    counts = {}
    for (const s of d.signs ?? []) counts[s.role] = (counts[s.role] ?? 0) + (s.n ?? 0)
  }
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
  <main class="mx-auto max-w-[1800px] px-3 py-3 sm:px-4" :class="{ 'reduce-motion': reduceMotion }" :data-reduce-motion="reduceMotion">
    <h1 class="sr-only">Benchmarks</h1>

    <p v-if="loading" role="status">Loading benchmark results…</p>
    <div v-else-if="error" role="alert" class="rounded-2xl bg-card p-4">
      <p>{{ error }}</p>
      <button type="button" class="mt-2 cursor-pointer rounded bg-bar px-4 py-1.5 hover:brightness-95" @click="loadIndex">Try again</button>
    </div>
    <p v-else-if="!versions.length" class="rounded-2xl bg-card p-4">No benchmark results have been published yet.</p>

    <template v-else>
      <!-- Two columns from the top: header and sign grid on the left; on the right the tablet grid
           and charts (aligned with the sign grid), or a picked sign's pane at full height. -->
      <div ref="gridsRow" class="grid content-start gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]" :style="rowMin ? { minHeight: `${rowMin}px` } : null">
        <div class="min-w-0">
              <!-- Fixed slots, so switching or playing versions never moves the page: controls and
                   progress, then the metric squares (fixed size) beside them. -->
              <section class="flex flex-wrap items-start gap-x-4 gap-y-2" aria-label="Version and playback">
            <div class="w-full min-w-0 sm:w-[27rem]">
              <label class="block text-xs font-semibold" for="version-select">Model version</label>
              <div class="mt-0.5 flex items-center gap-2">
                  <select
                    :value="selected"
                    id="version-select" :title="aboutVersion || null" aria-describedby="version-about" class="min-w-0 flex-1 rounded border border-ink/30 bg-page px-2 py-1 text-sm font-normal"
                    data-testid="version-select"
                    @change="onPick($event.target.value)"
                  >
                    <optgroup v-if="tiers.endToEnd.length" label="Read end to end (played)">
                      <option v-for="v in tiers.endToEnd" :key="v.version" :value="v.version" :title="v.description || null">{{ optionText(v) }}</option>
                    </optgroup>
                    <optgroup v-if="tiers.idOnly.length" label="Named on true boxes only (not comparable, not played)">
                      <option v-for="v in tiers.idOnly" :key="v.version" :value="v.version" :title="v.description || null">{{ optionText(v) }}</option>
                    </optgroup>
                    <optgroup v-if="tiers.unscored.length" label="No score (not played)">
                      <option v-for="v in tiers.unscored" :key="v.version" :value="v.version" :title="v.description || null">{{ optionText(v) }}</option>
                    </optgroup>
                  </select>
                  <button v-if="!playing" type="button" class="cursor-pointer rounded bg-bar px-3 py-1 text-sm font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" title="Play every version, worst to best" aria-label="Play worst to best" data-testid="play" @click="play">
                    <span aria-hidden="true">▶︎</span>
                  </button>
                  <template v-else>
                    <button type="button" class="cursor-pointer rounded bg-bar px-3 py-1 text-sm font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" data-testid="pause" :title="mode === 'paused' ? 'Resume' : 'Pause'" :aria-label="mode === 'paused' ? 'Resume' : 'Pause'" @click="togglePause">
                      <span aria-hidden="true">{{ mode === 'paused' ? '▶︎' : '⏸︎' }}</span>
                    </button>
                    <button type="button" class="cursor-pointer rounded bg-card px-3 py-1 text-sm font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" title="Stop" aria-label="Stop" data-testid="stop" @click="stop"><span aria-hidden="true">■︎</span></button>
                  </template>
              </div>
              <div class="mt-1 h-5" data-testid="progress-slot">
                <div v-if="showProgress" class="flex min-w-0 items-center gap-2" data-testid="progress">
                  <progress class="h-2 w-24" :value="Math.max(step + 1, 0)" :max="order.length" aria-label="Progress through the versions" />
                  <p role="status" class="min-w-0 truncate text-xs">
                    <template v-if="progressEntry">
                      <strong>Version {{ step + 1 }} of {{ order.length }}: {{ progressEntry.version }}</strong>, {{ scoreText(progressEntry) }}
                      <span v-if="mode === 'paused'"> (paused)</span>
                      <span v-if="finished"> (done, best version)</span>
                    </template>
                    <template v-else>Loading all versions…</template>
                  </p>
                </div>
              </div>
            </div>
            <!-- The description is hover text on the dropdown (and each option); kept here for screen readers. -->
            <p id="version-about" class="sr-only" data-testid="meta">{{ aboutVersion }}</p>
            <div class="sm:h-[5.5rem]">
              <MetricTiles v-if="current" :version="current" />
            </div>
          </section>

          <p v-if="skipped.length" role="status" class="mt-1 text-xs" data-testid="skipped">Skipped in playback (could not be loaded): {{ skipped.join(', ') }}</p>
          <p v-if="detailError" role="alert" class="mt-2 rounded-2xl bg-card p-3">{{ detailError }}</p>

          <section v-if="current" aria-labelledby="glyphs-h" class="mt-3 min-w-0" :style="glyphPad ? { paddingTop: `${glyphPad}px` } : null">
            <h2 id="glyphs-h" class="text-sm font-bold">Every sign</h2>
            <p v-if="!grids" class="mt-1 rounded-2xl bg-card p-3 text-sm" data-testid="grid-note">Not measured: this version finds signs but does not name them, so there is no per-sign result.</p>
            <template v-else>
              <div class="flex flex-wrap items-center gap-2 text-xs" aria-label="Colour legend" data-testid="legend">
                <span>{{ grids === 'id' ? 'Named correctly' : 'Read correctly' }}: 0%</span>
                <span class="inline-block h-2.5 w-28 rounded border border-ink/25" :style="{ backgroundImage: GRADIENT }" role="img" aria-label="Colour scale from 0% accuracy (light) to 100% (dark)" />
                <span>100%</span>
                <span class="inline-flex items-center gap-1"><span class="inline-block h-2.5 w-2.5 rounded-sm border border-dashed border-ink/40" :style="{ backgroundColor: NO_DATA.bg }" />no examples</span>
              </div>
              <div class="mt-1"><GlyphGrid :signs="current.signs ?? []" :mode="grids" :reduce-motion="reduceMotion" :picked="picked?.sign ?? null" @pick="pick" /></div>
            </template>
          </section>
          <p v-if="!current && !detailError" role="status" class="mt-4">Loading {{ selected }}…</p>
        </div>
        <div v-if="current" class="min-w-0">
          <!-- A picked sign's corpus occurrences and shared comments take the place of the
               tablet grid and charts, so the page still fits on one screen. -->
          <section v-if="picked" aria-label="Occurrences of the picked sign" class="min-w-0" data-testid="picked-pane">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-bold">Every tablet with {{ picked.sign }}</h2>
              <button type="button" class="cursor-pointer rounded bg-card px-3 py-1 text-sm font-semibold hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" data-testid="close-pane" @click="unpick">
                Back to charts
              </button>
            </div>
            <div class="mt-1 overflow-y-auto" :style="{ maxHeight: paneMax }">
              <GlyphOccurrencesPane compact :selection="selection" />
            </div>
          </section>
          <!-- From the top: the two bar charts, then the tablet grid level with the sign grid
               (alignGrids pads whichever side is higher), then the coverage chart and cost. -->
          <section v-show="!picked" aria-labelledby="tablets-h" class="min-w-0">
            <div class="grid gap-x-4 gap-y-3 sm:grid-cols-2" data-testid="side-charts">
              <ColumnBars compact title="Named correctly, by training examples" :bars="bucketBars" :reduce-motion="reduceMotion" empty="This version does not identify signs." />
              <ColumnBars compact title="Named correctly, by sign role" :bars="roleBars" :reduce-motion="reduceMotion" empty="This version does not identify signs." />
            </div>
            <div class="mt-2" :style="tabletPad ? { paddingTop: `${tabletPad}px` } : null">
              <h2 id="tablets-h" class="text-sm font-bold">Every tablet</h2>
              <div data-testid="tablet-block" :style="tabletMin ? { minHeight: `${tabletMin}px` } : null">
              <template v-if="grids">
                <p class="text-xs text-ink/80">Share of its signs {{ grids === 'id' ? 'named correctly' : 'read correctly' }}, same scale. Hover for counts.</p>
                <div class="mt-1" data-testid="tablet-grid-wrap"><TabletGrid :tablets="current.tablet_results ?? []" :mode="grids" :reduce-motion="reduceMotion" /></div>
              </template>
              <p v-else class="rounded-2xl bg-card p-3 text-sm" data-testid="tablet-note">Not measured: no per-tablet result without sign names.</p>
              </div>
            </div>
            <div class="mt-3 grid gap-x-4 gap-y-3 sm:grid-cols-2" data-testid="side-extra">
              <CoverageChart v-if="current.coverage_curve?.length" compact :points="current.coverage_curve" />
              <figure v-else class="m-0 sm:min-h-[12.5rem]" data-testid="coverage-empty">
                <figcaption class="text-sm leading-tight font-semibold">Accuracy when answering only the most confident signs</figcaption>
                <p class="mt-2 text-sm text-ink/80">— Not measured for this version.</p>
              </figure>
              <section aria-labelledby="cost-h">
                <h2 id="cost-h" class="text-sm font-semibold">Cost</h2>
                <dl class="mt-1 grid gap-y-1 text-sm" data-testid="cost">
                  <div v-for="c in cost" :key="c.key" class="flex gap-1">
                    <dt class="text-ink/80">{{ c.label }}:</dt>
                    <dd class="font-semibold tabular-nums">{{ c.value ?? '—' }}</dd>
                  </div>
                </dl>
              </section>
            </div>
          </section>
        </div>
      </div>
    </template>
  </main>
</template>
