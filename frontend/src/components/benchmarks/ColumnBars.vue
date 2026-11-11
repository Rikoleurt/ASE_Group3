<script setup>
import { BAR_FILL, pct } from './benchmarkData'

// bars: [{ key, label, value (0..1 or null), count (number of signs, optional) }]
defineProps({
  title: { type: String, required: true },
  bars: { type: Array, required: true },
  countLabel: { type: String, default: 'signs' },
  reduceMotion: { type: Boolean, default: false },
  empty: { type: String, default: 'Not available for this version.' },
})
const label = (b, countLabel) => `${b.label}: ${pct(b.value, 0)}${b.count != null ? `, ${b.count} ${countLabel}` : ''}`
</script>

<template>
  <figure class="m-0">
    <figcaption class="text-sm font-semibold">{{ title }}</figcaption>
    <p v-if="!bars.length" class="mt-2 text-sm text-ink/80">— {{ empty }}</p>
    <ul v-else class="mt-2 flex items-end gap-2" :aria-label="title">
      <li v-for="b in bars" :key="b.key" class="flex min-w-0 flex-1 flex-col items-center" :data-bar="b.key">
        <span class="text-sm font-semibold tabular-nums">{{ pct(b.value, 0) }}</span>
        <div class="flex h-28 w-full items-end border-b border-ink/40" role="img" :aria-label="label(b, countLabel)" :title="label(b, countLabel)">
          <div class="bar w-full rounded-t" :class="{ 'no-motion': reduceMotion }" :style="{ height: `${Math.max(0, (b.value ?? 0) * 100)}%`, backgroundColor: BAR_FILL }" data-testid="bar-fill" />
        </div>
        <span class="mt-1 text-center text-xs leading-tight">{{ b.label }}</span>
        <span v-if="b.count != null" class="text-center text-xs text-ink/70">n = {{ b.count }}</span>
      </li>
    </ul>
  </figure>
</template>

<style scoped>
.bar { transition: height 0.6s ease; }
.bar.no-motion { transition: none; }
@media (prefers-reduced-motion: reduce) { .bar { transition: none; } }
</style>
