<script setup>
import { computed } from 'vue'
import { BAR_FILL, pct } from './benchmarkData'

const props = defineProps({ points: { type: Array, required: true } })
const W = 320, H = 180, L = 36, R = 10, T = 10, B = 28
const pts = computed(() =>
  props.points
    .filter((p) => p.coverage != null && p.id_top1 != null)
    .map((p) => ({ ...p, x: L + p.coverage * (W - L - R), y: T + (1 - p.id_top1) * (H - T - B) })),
)
const path = computed(() => pts.value.map((p) => `${p.x},${p.y}`).join(' '))
const ticks = [0, 0.25, 0.5, 0.75, 1]
const summary = computed(() => pts.value.map((p) => `${pct(p.coverage, 0)} answered: ${pct(p.id_top1, 0)} right`).join('; '))
</script>

<template>
  <figure class="m-0">
    <figcaption class="text-sm font-semibold">Accuracy when answering only the most confident signs</figcaption>
    <svg :viewBox="`0 0 ${W} ${H}`" class="mt-2 w-full max-w-md" role="img" :aria-label="`Accuracy against the share of signs answered. ${summary}`" data-testid="coverage">
      <g stroke="currentColor" stroke-opacity="0.15">
        <line v-for="t in ticks" :key="`y${t}`" :x1="L" :x2="W - R" :y1="T + (1 - t) * (H - T - B)" :y2="T + (1 - t) * (H - T - B)" />
      </g>
      <line :x1="L" :x2="W - R" :y1="H - B" :y2="H - B" stroke="currentColor" stroke-opacity="0.5" />
      <g class="fill-ink text-[10px]">
        <text v-for="t in ticks" :key="`yl${t}`" :x="L - 4" :y="T + (1 - t) * (H - T - B) + 3" text-anchor="end">{{ t * 100 }}%</text>
        <text v-for="t in ticks" :key="`xl${t}`" :x="L + t * (W - L - R)" :y="H - B + 13" text-anchor="middle">{{ t * 100 }}%</text>
        <text :x="(L + W - R) / 2" :y="H - 2" text-anchor="middle">share of signs answered</text>
      </g>
      <polyline :points="path" fill="none" :stroke="BAR_FILL" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <circle v-for="p in pts" :key="p.coverage" :cx="p.x" :cy="p.y" r="3" :fill="BAR_FILL" stroke="#f9e6a8" stroke-width="2">
        <title>{{ pct(p.coverage, 0) }} answered: {{ pct(p.id_top1, 0) }} right</title>
      </circle>
    </svg>
  </figure>
</template>
