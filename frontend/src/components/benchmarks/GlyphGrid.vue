<script setup>
import { computed, ref } from 'vue'
import '../analysis/linearA.css'
import { BUCKET_LABELS, BUCKET_ORDER, accuracyColor, pct, signAccuracy, sortSigns } from './benchmarkData'

const props = defineProps({
  signs: { type: Array, required: true },
  mode: { type: String, default: 'id' },
  reduceMotion: { type: Boolean, default: false },
})

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
const tileStyle = (s) => {
  const c = accuracyColor(s.rate)
  return { backgroundColor: c.bg, color: c.fg }
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end gap-4">
      <label class="flex flex-col text-sm font-semibold">Sort by
        <select v-model="sortBy" class="mt-1 rounded border border-ink/30 bg-page px-2 py-1 font-normal">
          <option value="frequency">Frequency</option>
          <option value="accuracy">Accuracy</option>
          <option value="sign">Sign ID</option>
        </select>
      </label>
      <label class="flex flex-col text-sm font-semibold">Role
        <select v-model="role" class="mt-1 rounded border border-ink/30 bg-page px-2 py-1 font-normal">
          <option value="all">All roles</option>
          <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
        </select>
      </label>
      <label class="flex flex-col text-sm font-semibold">Training examples
        <select v-model="bucket" class="mt-1 rounded border border-ink/30 bg-page px-2 py-1 font-normal">
          <option value="all">Any number</option>
          <option v-for="b in buckets" :key="b" :value="b">{{ BUCKET_LABELS[b] ?? b }}</option>
        </select>
      </label>
      <p class="pb-1 text-sm" role="status" data-testid="glyph-count">{{ shown.length }} of {{ rows.length }} signs</p>
    </div>

    <ul class="mt-3 flex flex-wrap gap-1" aria-label="Accuracy per sign" data-testid="glyph-grid" @mouseleave="active = null">
      <li v-for="s in shown" :key="s.sign">
        <button
          type="button"
          :data-sign="s.sign"
          :title="describe(s)"
          :aria-label="describe(s)"
          class="glyph-tile flex h-14 w-14 cursor-default flex-col items-center justify-center rounded border border-ink/25 leading-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          :class="{ 'border-dashed': s.rate == null, 'no-motion': reduceMotion }"
          :style="tileStyle(s)"
          @mouseenter="active = s"
          @focus="active = s"
          @blur="active = null"
        >
          <span v-if="s.glyph" class="linear-a text-2xl" aria-hidden="true">{{ s.glyph }}</span>
          <span class="text-[0.65rem] font-semibold" :class="{ 'mt-1': s.glyph }" aria-hidden="true">{{ s.sign }}</span>
        </button>
      </li>
    </ul>
    <p v-if="!shown.length" class="mt-3">No signs match these filters.</p>
    <p class="mt-3 min-h-12 rounded bg-card px-3 py-2 text-sm" data-testid="glyph-detail">
      {{ active ? describe(active) : 'Hover or focus a sign for its ID, accuracy, number of examples and top confusions.' }}
    </p>

    <details class="mt-3">
      <summary class="cursor-pointer text-sm font-semibold">Show as a table</summary>
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
@media (prefers-reduced-motion: reduce) { .glyph-tile { transition: none; } }
</style>
