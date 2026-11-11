<script setup>
import { BAR_FILL, pct } from './benchmarkData'

// bars: [{ key, label, value (0..1 or null), count (number of signs, optional) }]
// One horizontal bar chart: categories down the left, every bar from the same
// zero line on a shared 0-100% scale with gridlines, the value at the bar's end.
defineProps({
  title: { type: String, required: true },
  bars: { type: Array, required: true },
  countLabel: { type: String, default: 'signs' },
  reduceMotion: { type: Boolean, default: false },
  empty: { type: String, default: 'Not available for this version.' },
})
const TICKS = [0, 25, 50, 75, 100]
const label = (b, countLabel) => `${b.label}: ${pct(b.value, 0)}${b.count != null ? `, ${b.count} ${countLabel}` : ''}`
const share = (v) => Math.max(0, Math.min(1, v ?? 0)) * 100
</script>

<template>
  <figure class="m-0">
    <figcaption class="text-sm font-semibold">{{ title }}</figcaption>
    <p v-if="!bars.length" class="mt-2 text-sm text-ink/80">— {{ empty }}</p>
    <div v-else class="chart mt-2 text-xs">
      <ul class="m-0 list-none p-0" :aria-label="title">
        <li v-for="b in bars" :key="b.key" class="row" :data-bar="b.key">
          <span class="cat">
            <span class="leading-tight">{{ b.label }}</span>
            <span v-if="b.count != null" class="text-ink/70 tabular-nums">n = {{ b.count }}</span>
          </span>
          <span class="plot" role="img" :aria-label="label(b, countLabel)" :title="label(b, countLabel)">
            <span
              v-if="b.value != null"
              class="bar"
              :class="{ 'no-motion': reduceMotion }"
              :style="{ width: `${share(b.value)}%`, backgroundColor: BAR_FILL }"
              data-testid="bar-fill"
            />
            <span class="value font-semibold tabular-nums" :class="{ 'no-motion': reduceMotion }" :style="{ left: `${share(b.value)}%` }">
              {{ pct(b.value, 0) }}
            </span>
          </span>
        </li>
      </ul>
      <div class="row axis" aria-hidden="true">
        <span />
        <span class="plot ticks">
          <span v-for="t in TICKS" :key="t" class="tick tabular-nums" :style="{ left: `${t}%` }">{{ t }}%</span>
        </span>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.chart { --label: 8.5rem; }
.row {
  display: grid;
  grid-template-columns: var(--label) minmax(0, 1fr);
  align-items: center;
  column-gap: 0.5rem;
  min-height: 1.75rem;
}
.cat { display: flex; flex-direction: column; text-align: right; }
.plot {
  position: relative;
  height: 1.75rem;
  margin-right: 2.5rem; /* room for a value label at 100% */
  /* Gridlines at 0/25/50/75/100%, recessive; the zero line a little stronger. */
  background-image:
    linear-gradient(to right, rgb(0 0 0 / 0.35) 1px, transparent 1px),
    linear-gradient(to right, transparent calc(25% - 0.5px), rgb(0 0 0 / 0.1) calc(25% - 0.5px) calc(25% + 0.5px), transparent calc(25% + 0.5px)),
    linear-gradient(to right, transparent calc(50% - 0.5px), rgb(0 0 0 / 0.1) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px)),
    linear-gradient(to right, transparent calc(75% - 0.5px), rgb(0 0 0 / 0.1) calc(75% - 0.5px) calc(75% + 0.5px), transparent calc(75% + 0.5px)),
    linear-gradient(to left, rgb(0 0 0 / 0.1) 1px, transparent 1px);
}
.bar {
  position: absolute;
  left: 0;
  top: 0.375rem;
  height: 1rem;
  border-radius: 0 4px 4px 0; /* rounded at the data end, square on the zero line */
  transition: width 0.6s ease;
}
.value {
  position: absolute;
  top: 50%;
  transform: translate(0.3rem, -50%);
  white-space: nowrap;
  transition: left 0.6s ease;
}
.axis { min-height: 1rem; }
.ticks { height: 1rem; background: none; }
.tick { position: absolute; transform: translateX(-50%); color: rgb(0 0 0 / 0.65); }
.no-motion { transition: none; }
@media (prefers-reduced-motion: reduce) { .bar, .value { transition: none; } }
</style>
