<script setup>
// Below the analysis: the colour key for the boxes (hover a label for its
// definition), the tablet's text in Linear A, then each fraction formula as an
// equation of glyphs and values, ending in its verdict.
import { computed } from 'vue'
import { ROLES, VERDICTS, formulaColor, prefersStill, roleKey } from './colors.js'
import { DEFINITIONS, pretty } from './definitions.js'
import FractionEquation from './FractionEquation.vue'
import HoverTip from './HoverTip.vue'
import TabletText from './TabletText.vue'

const props = defineProps({
  analysis: { type: Object, required: true },
})

const PIECE_MS = 400 // FractionEquation's pace
const STILL = prefersStill()
const MARKERS = computed(() => new Set((props.analysis.formulas ?? []).flatMap((formula) => formula.marker_ids)))
// KU-RO totals first, then fractions found outside any total.
const FORMULAS = computed(() =>
  [...(props.analysis.formulas ?? [])].sort((a, b) => (a.kind === 'group') - (b.kind === 'group')),
)
const COUNTS = computed(() => {
  const counts = {}
  for (const sign of props.analysis.signs ?? []) {
    const key = roleKey(sign, MARKERS.value)
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
})
// Only the colours that appear on this tablet.
const KEY = computed(() => Object.entries(ROLES).filter(([key]) => COUNTS.value[key]))

function title(formula) {
  if (formula.kind === 'group') return `Fractions on line ${formula.lines[0] + 1}`
  const marker = formula.kind === 'grand_total' ? 'PO-TO-KU-RO' : 'KU-RO'
  const first = formula.lines[0] + 1
  const last = formula.lines[formula.lines.length - 1] + 1
  return `${marker} total, lines ${first}–${last}`
}

function markerGlyphs(formula) {
  const byId = new Map(props.analysis.signs.map((sign) => [sign.id, sign]))
  return formula.marker_ids.map((id) => byId.get(id)?.glyph ?? '').join('')
}

function verdictText(formula) {
  if (formula.verdict === 'mismatch') return `${VERDICTS.mismatch.label}: off by ${pretty(formula.difference)}`
  return VERDICTS[formula.verdict].label
}

// The badge rises once the equation is written out, then pulses.
function verdictStyle(formula) {
  const start = (formula.entries.length + formula.total.length + 4) * PIECE_MS
  return { backgroundColor: formulaColor(formula), animationDelay: `${start}ms, ${start + 450}ms` }
}
</script>

<template>
  <section v-if="analysis.signs?.length" class="rounded-3xl bg-card p-6" :class="{ still: STILL }">
    <h2 class="text-2xl font-bold">Fraction check</h2>

    <ul class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm" aria-label="Box colours">
      <li v-for="[key, role] in KEY" :key="key" class="flex items-center gap-2">
        <span class="inline-block h-3.5 w-3.5 rounded-sm border-2" :style="{ borderColor: role.color }" />
        <HoverTip :tip="DEFINITIONS[key]">{{ role.label }}</HoverTip>
        <span class="text-ink/60" data-testid="key-count">({{ COUNTS[key] }})</span>
      </li>
      <li v-if="FORMULAS.length" class="flex items-center gap-2">
        <span class="inline-block h-3.5 w-5 rounded-sm border-2 border-dashed border-ink/60" />
        <HoverTip :tip="DEFINITIONS.formula">Fraction formula</HoverTip>
      </li>
    </ul>

    <h3 class="mt-6 font-bold">The tablet in Linear A</h3>
    <TabletText :analysis="analysis" />

    <p v-if="!FORMULAS.length" class="mt-6 text-ink/70" data-testid="no-formula">
      No fraction signs or KU-RO total were found on this tablet.
    </p>

    <article
      v-for="(formula, index) in FORMULAS"
      :key="index"
      class="mt-6 rounded-2xl border-l-4 bg-page/60 p-4"
      :style="{ borderColor: formulaColor(formula) }"
      data-testid="formula"
    >
      <h3 class="font-bold">{{ title(formula) }}</h3>
      <FractionEquation :formula="formula" :marker-glyphs="markerGlyphs(formula)" />
      <p
        v-if="formula.verdict"
        class="verdict mt-4 inline-block rounded-full px-4 py-1 font-bold text-white"
        :style="verdictStyle(formula)"
        data-testid="verdict"
      >
        {{ verdictText(formula) }}
      </p>
      <details class="mt-3 text-sm">
        <summary class="cursor-pointer text-ink/70">Show the working</summary>
        <ol class="mt-1 space-y-0.5 font-mono" data-testid="steps">
          <li v-for="(step, number) in formula.steps" :key="number">{{ step }}</li>
        </ol>
      </details>
      <p v-if="formula.kind !== 'group'" class="mt-2 text-sm text-ink/70">{{ formula.note }}</p>
    </article>
  </section>
</template>

<style scoped>
.verdict {
  opacity: 0;
  animation:
    rise 0.45s ease-out forwards,
    pulse 0.9s ease-in-out 2;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes pulse {
  50% {
    transform: scale(1.06);
  }
}

.still .verdict {
  animation: none;
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .verdict {
    animation: none;
    opacity: 1;
  }
}
</style>
