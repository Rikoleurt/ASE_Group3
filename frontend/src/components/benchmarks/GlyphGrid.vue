<script setup>
import { computed, ref } from 'vue'
import '../analysis/linearA.css'
import { BUCKET_LABELS, BUCKET_ORDER, accuracyColor, pct, signAccuracy, sortSigns, textRgb } from './benchmarkData'

const props = defineProps({
  signs: { type: Array, required: true },
  mode: { type: String, default: 'id' },
  reduceMotion: { type: Boolean, default: false },
  // The sign whose occurrences and comments are open (highlighted); click a tile to pick one.
  picked: { type: String, default: null },
})
const emit = defineEmits(['pick'])

const sortBy = ref('frequency')
const role = ref('all')
const bucket = ref('all')
const active = ref(null)

const rows = computed(() => props.signs.map((s) => ({ ...s, ...signAccuracy(s, props.mode) })))
const roles = computed(() => [...new Set(props.signs.map((s) => s.role))].sort())
const buckets = computed(() => {
  const present = new Set(props.signs.map((s) => s.bucket).filter(Boolean))
  return [...BUCKET_ORDER.filter((b) => present.has(b)), ...[...present].filter((b) => !BUCKET_ORDER.includes(b))]
})
const shown = computed(() =>
  sortSigns(
    rows.value.filter((s) => (role.value === 'all' || s.role === role.value) && (bucket.value === 'all' || s.bucket === bucket.value)),
    sortBy.value,
  ),
)

const what = computed(() => (props.mode === 'id' ? 'named correctly on the true box' : 'read correctly end to end'))
function describe(s) {
  const acc = s.n ? `${pct(s.rate, 0)} ${what.value} (${s.correct} of ${s.n})` : 'no examples in this set'
  const conf = s.confused_with?.length ? `; most often confused with ${s.confused_with.map((c) => `${c.sign} (${c.count})`).join(', ')}` : ''
  return `${s.sign}: ${acc}${conf}`
}
// Signs with no Unicode character show a drawing from the corpus (black ink on white), served by
// the app; it blends into the tile: darkened on light fills, inverted on dark ones. If the
// drawing cannot load (no corpus on this server), the sign ID is shown as before.
const drawingUrl = (d) => `/api/tablets/${encodeURIComponent(d.tablet)}/signs/${d.position}.png`
const lightInk = (s) => textRgb(s.rate).every((v) => v > 200)
const broken = ref(new Set())
const markBroken = (sign) => { broken.value = new Set([...broken.value, sign]) }
const tileStyle = (s) => {
  const c = accuracyColor(s.rate)
  return { backgroundColor: c.bg, color: c.fg }
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
      <label class="flex items-center gap-1 text-xs font-semibold">Sort by
        <select v-model="sortBy" class="rounded border border-ink/30 bg-page px-1 py-0.5 text-xs font-normal">
          <option value="frequency">Frequency</option>
          <option value="accuracy">Accuracy</option>
          <option value="sign">Sign ID</option>
        </select>
      </label>
      <label class="flex items-center gap-1 text-xs font-semibold">Role
        <select v-model="role" class="rounded border border-ink/30 bg-page px-1 py-0.5 text-xs font-normal">
          <option value="all">All roles</option>
          <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
        </select>
      </label>
      <label class="flex items-center gap-1 text-xs font-semibold">Training examples
        <select v-model="bucket" class="rounded border border-ink/30 bg-page px-1 py-0.5 text-xs font-normal">
          <option value="all">Any number</option>
          <option v-for="b in buckets" :key="b" :value="b">{{ BUCKET_LABELS[b] ?? b }}</option>
        </select>
      </label>
      <p class="text-xs" role="status" data-testid="glyph-count">{{ shown.length }} of {{ rows.length }} signs</p>
    </div>

    <ul class="mt-1.5 flex flex-wrap gap-0.5" aria-label="Accuracy per sign" data-testid="glyph-grid" @mouseleave="active = null">
      <li v-for="s in shown" :key="s.sign">
        <button
          type="button"
          :data-sign="s.sign"
          :title="describe(s)"
          :aria-label="describe(s)"
          class="glyph-tile flex h-8 w-8 cursor-pointer items-center justify-center rounded-sm border border-ink/25 leading-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          :class="{ 'border-dashed': s.rate == null, 'no-motion': reduceMotion }"
          :style="tileStyle(s)"
          :aria-pressed="picked === s.sign"
          :data-picked="picked === s.sign || null"
          @click="emit('pick', s)"
          @mouseenter="active = s"
          @focus="active = s"
          @blur="active = null"
        >
          <span v-if="s.glyph" class="linear-a text-xl" aria-hidden="true">{{ s.glyph }}</span>
          <img
            v-else-if="s.drawing && !broken.has(s.sign)"
            :src="drawingUrl(s.drawing)"
            alt=""
            class="sign-drawing h-6 w-6 object-contain"
            :class="lightInk(s) ? 'light-ink' : 'dark-ink'"
            loading="lazy"
            data-testid="sign-drawing"
            @error="markBroken(s.sign)"
          >
          <span v-else :class="s.sign === 'unidentified' ? 'text-base font-bold' : 'text-[0.55rem] font-semibold'" aria-hidden="true">{{ s.sign === 'unidentified' ? '?' : s.sign }}</span>
        </button>
      </li>
    </ul>
    <p v-if="!shown.length" class="mt-2 text-sm">No signs match these filters.</p>
    <p class="mt-1.5 min-h-9 rounded bg-card px-2 py-1 text-xs" data-testid="glyph-detail">
      {{ active ? describe(active) : 'Hover or focus a sign for its ID, accuracy, number of examples and top confusions.' }}
    </p>

    <details class="mt-1.5">
      <summary class="cursor-pointer text-xs font-semibold">Show as a table</summary>
      <div class="mt-2 max-h-72 overflow-auto">
        <table class="w-full text-left text-sm">
          <caption class="sr-only">Accuracy per sign</caption>
          <thead><tr><th scope="col">Sign</th><th scope="col">Role</th><th scope="col">Training</th><th scope="col">n</th><th scope="col">Correct</th><th scope="col">Accuracy</th><th scope="col">Confused with</th></tr></thead>
          <tbody>
            <tr v-for="s in shown" :key="s.sign">
              <th scope="row" class="font-semibold">{{ s.sign }}</th><td>{{ s.role }}</td><td>{{ s.bucket ?? '—' }}</td><td>{{ s.n }}</td><td>{{ s.correct }}</td><td>{{ pct(s.rate, 0) }}</td>
              <td>{{ (s.confused_with ?? []).map((c) => `${c.sign} (${c.count})`).join(', ') || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </div>
</template>

<style scoped>
.glyph-tile { transition: background-color 0.6s ease, color 0.6s ease; }
.glyph-tile.no-motion { transition: none; }
.glyph-tile[data-picked] { outline: 3px solid var(--color-accent); outline-offset: 1px; }
.sign-drawing.dark-ink { mix-blend-mode: multiply; }
.sign-drawing.light-ink { filter: invert(1); mix-blend-mode: screen; }
@media (prefers-reduced-motion: reduce) { .glyph-tile { transition: none; } }
</style>
