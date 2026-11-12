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
    const delta = vs ? `${vs.diff >= 0 ? '+' : '−'}${Math.abs(vs.diff * 100).toFixed(1)}` : null
    const points = delta ? `${delta} points` : null
    return {
      ...tile,
      present,
      value: pct(value),
      interval: present && ci?.length === 2 && ci[0] != null ? `95% interval ${pct(ci[0], 0)} to ${pct(ci[1], 0)}` : null,
      vs,
      points,
      delta,
      mark: vs ? (verdictMark[vs.verdict] ?? '') : '',
      note: present ? null : missingNote(tile, props.version.stages),
      tooltip: [tile.title, tile.hint, present && ci?.length === 2 && ci[0] != null ? `95% interval ${pct(ci[0], 0)} to ${pct(ci[1], 0)}` : null,
        vs ? `${delta} points vs ${props.version.reference}: ${vs.verdict} (${(vs.lo * 100).toFixed(1)} to ${(vs.hi * 100).toFixed(1)})` : null]
        .filter(Boolean).join('\n'),
    }
  }),
)
</script>

<template>
  <!-- Small squares: the value and its change vs the reference; the full wording (interval,
       verdict) is in the tooltip and read out to screen readers. -->
  <ul class="flex flex-wrap gap-2" aria-label="Headline results">
    <li
      v-for="tile in tiles"
      :key="tile.key"
      :data-metric="tile.key"
      class="flex h-[5.5rem] w-[5.5rem] flex-col justify-between rounded-lg bg-card p-1.5 text-center"
      :title="tile.tooltip"
    >
      <h3 class="text-[11px] leading-tight font-semibold" aria-hidden="true">{{ tile.short }}</h3>
      <p class="text-lg leading-none font-bold tabular-nums" aria-hidden="true">{{ tile.present ? tile.value : '—' }}</p>
      <p class="text-[11px] leading-tight tabular-nums" aria-hidden="true" data-testid="delta">
        <template v-if="tile.present && tile.vs"><span>{{ tile.mark }}</span> {{ tile.delta }} <span class="text-ink/70">{{ tile.vs.verdict }}</span></template>
        <template v-else-if="tile.present && isReference"><span class="text-ink/70">reference</span></template>
        <template v-else-if="!tile.present"><span class="text-ink/70">n/a</span></template>
      </p>
      <div class="sr-only">
        {{ tile.title }}: {{ tile.value }}
        <template v-if="tile.interval">, {{ tile.interval }}</template>
        <template v-if="tile.note">, {{ tile.note }}</template>.
        <span v-if="tile.present && tile.vs" data-testid="vs">{{ tile.points }} vs {{ version.reference }}: {{ tile.vs.verdict }} ({{ (tile.vs.lo * 100).toFixed(1) }} to {{ (tile.vs.hi * 100).toFixed(1) }})</span>
        <span v-else-if="tile.present && isReference">This is the reference version.</span>
        <span v-else-if="tile.present">No comparison with {{ version.reference }}.</span>
      </div>
    </li>
  </ul>
</template>
