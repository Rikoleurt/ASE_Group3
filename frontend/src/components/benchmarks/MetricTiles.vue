<script setup>
import { computed } from 'vue'
import { HEADLINE_TILES, missingNote, pct, readsEndToEnd } from './benchmarkData'

const props = defineProps({ version: { type: Object, required: true } })

const isReference = computed(() => props.version.version === props.version.reference)
const verdictMark = { better: '▲', worse: '▼', tie: '＝' }

const tiles = computed(() =>
  HEADLINE_TILES.map((tile) => {
    // A detector that cannot name signs has a read rate of 0 by construction: not a measurement.
    const value = tile.key === 'read_top1' && !readsEndToEnd(props.version) ? null : props.version.metrics?.[tile.key]
    const ci = props.version.ci95?.[tile.key]
    const vs = props.version.vs_reference?.[tile.key]
    const present = value != null
    const points = vs ? `${vs.diff >= 0 ? '+' : '−'}${Math.abs(vs.diff * 100).toFixed(1)} points` : null
    return {
      ...tile,
      present,
      value: pct(value),
      interval: present && ci?.length === 2 && ci[0] != null ? `95% interval ${pct(ci[0], 0)} to ${pct(ci[1], 0)}` : null,
      vs,
      points,
      mark: vs ? (verdictMark[vs.verdict] ?? '') : '',
      note: present ? null : missingNote(tile, props.version.stages),
    }
  }),
)
</script>

<template>
  <ul class="grid grid-cols-2 gap-2 lg:grid-cols-4" aria-label="Headline results">
    <li v-for="tile in tiles" :key="tile.key" :data-metric="tile.key" class="rounded-lg bg-card px-3 py-1.5" :title="tile.hint">
      <h3 class="text-xs font-semibold">{{ tile.title }}</h3>
      <p class="flex flex-wrap items-baseline gap-x-2">
        <span class="text-xl font-bold tabular-nums">{{ tile.value }}</span>
        <span v-if="tile.interval" class="text-xs text-ink/80">{{ tile.interval }}</span>
        <span v-if="tile.note" class="text-xs text-ink/80">{{ tile.note }}</span>
      </p>
      <p v-if="tile.present && tile.vs" class="text-xs" data-testid="vs">
        <span aria-hidden="true">{{ tile.mark }}</span>
        {{ tile.points }} vs {{ version.reference }}:
        <strong>{{ tile.vs.verdict }}</strong>
        <span class="text-ink/70"> ({{ (tile.vs.lo * 100).toFixed(1) }} to {{ (tile.vs.hi * 100).toFixed(1) }})</span>
      </p>
      <p v-else-if="tile.present && isReference" class="text-xs text-ink/80">This is the reference version.</p>
      <p v-else-if="tile.present" class="text-xs text-ink/80">No comparison with {{ version.reference }}.</p>
    </li>
  </ul>
</template>
