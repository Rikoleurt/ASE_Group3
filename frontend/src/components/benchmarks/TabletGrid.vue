<script setup>
import { computed } from 'vue'
import { accuracyColor, pct, tabletRate } from './benchmarkData'

const props = defineProps({
  tablets: { type: Array, required: true },
  mode: { type: String, default: 'id' },
  reduceMotion: { type: Boolean, default: false },
})
const cells = computed(() => props.tablets.map((t) => ({ ...t, ...tabletRate(t, props.mode) })))
const text = (c) =>
  c.n
    ? `${c.tablet}: ${c.correct} of ${c.n} signs ${c.what} (${pct(c.rate, 0)}); ${c.truths} signs on the tablet, ${c.found} found`
    : `${c.tablet}: nothing to score; ${c.truths} signs on the tablet, ${c.found} found`
</script>

<template>
  <div>
    <ul class="flex flex-wrap gap-0.5" aria-label="Result per tablet" data-testid="tablet-grid">
      <li v-for="c in cells" :key="c.tablet">
        <button
          type="button"
          :title="text(c)"
          :aria-label="text(c)"
          class="tablet-cell h-3.5 w-3.5 cursor-default rounded-[2px] border border-ink/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          :class="{ 'border-dashed': c.rate == null, 'no-motion': reduceMotion }"
          :style="{ backgroundColor: accuracyColor(c.rate).bg }"
        />
      </li>
    </ul>
    <details class="mt-1.5">
      <summary class="cursor-pointer text-xs font-semibold">Show as a table</summary>
      <div class="mt-2 max-h-72 overflow-auto">
        <table class="w-full text-left text-sm">
          <caption class="sr-only">Result per tablet</caption>
          <thead><tr><th scope="col">Tablet</th><th scope="col">Signs</th><th scope="col">Found</th><th scope="col">Correct</th><th scope="col">Of</th><th scope="col">Rate</th></tr></thead>
          <tbody>
            <tr v-for="c in cells" :key="c.tablet"><th scope="row" class="font-semibold">{{ c.tablet }}</th><td>{{ c.truths }}</td><td>{{ c.found }}</td><td>{{ c.correct }}</td><td>{{ c.n }}</td><td>{{ pct(c.rate, 0) }}</td></tr>
          </tbody>
        </table>
      </div>
    </details>
  </div>
</template>

<style scoped>
.tablet-cell { transition: background-color 0.6s ease; }
.tablet-cell.no-motion { transition: none; }
@media (prefers-reduced-motion: reduce) { .tablet-cell { transition: none; } }
</style>
