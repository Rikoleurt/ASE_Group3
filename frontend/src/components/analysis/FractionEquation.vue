<script setup>
// One formula's fraction arithmetic as an equation of glyphs and values:
//   Entries  𐝆 + 𐝆 = ½ + ½ = 1
//   Total    𐘂𐘁 𐝆 = ½
//   Check    1 ≠ ½: off by ½
// Each piece appears in turn, STEP_MS apart.
import { computed } from 'vue'
import { ROLES } from './colors.js'
import { pretty } from './definitions.js'
import './linearA.css'

const props = defineProps({
  formula: { type: Object, required: true },
  markerGlyphs: { type: String, default: '' },
})

const STEP_MS = 400
const IS_GROUP = computed(() => props.formula.kind === 'group')
const MARKER = computed(() => (props.formula.kind === 'grand_total' ? 'PO-TO-KU-RO' : 'KU-RO'))
// The order pieces appear in: entry terms, entries' sum, total terms, total, check.
const ENTRY_SUM_AT = computed(() => props.formula.entries.length)
const TOTAL_AT = computed(() => ENTRY_SUM_AT.value + 1)
const TOTAL_SUM_AT = computed(() => TOTAL_AT.value + props.formula.total.length)
const CHECK_AT = computed(() => TOTAL_SUM_AT.value + 1)

const CHECK = computed(() => {
  const { verdict, entries_sum: sum, total_value: total, carried, difference } = props.formula
  if (verdict === 'balances') {
    return carried ? `${pretty(sum)} = ${pretty(total)} + ${carried} whole` : `${pretty(sum)} = ${pretty(total)}`
  }
  if (verdict === 'mismatch') return `${pretty(sum)} ≠ ${pretty(total)}: off by ${pretty(difference)}`
  if (verdict === 'incomplete') return `${pretty(sum)} ? ${pretty(total)}: a sign has no agreed value`
  return null
})

function at(index) {
  return { animationDelay: `${index * STEP_MS}ms` }
}

function sumOf(terms) {
  return terms.map((term) => pretty(term.value)).join(' + ')
}
</script>

<template>
  <div class="mt-3 grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-3" data-testid="equation">
    <span class="text-sm text-ink/70">{{ IS_GROUP ? 'Sum' : 'Entries' }}</span>
    <div class="flex flex-wrap items-center gap-2" data-testid="equation-entries">
      <template v-for="(term, index) in formula.entries" :key="term.id">
        <span v-if="index" class="piece text-xl text-ink/60" :style="at(index)">+</span>
        <span class="piece flex flex-col items-center rounded-lg bg-page px-2 py-1" :style="at(index)" data-testid="term">
          <span class="linear-a text-3xl" :style="{ color: ROLES.fraction.color }">{{ term.glyph ?? '?' }}</span>
          <span class="text-xs">{{ term.label }} = {{ pretty(term.value) }}</span>
        </span>
      </template>
      <span v-if="!formula.entries.length" class="piece text-ink/70">no fractions</span>
      <span class="piece text-xl font-bold" :style="at(ENTRY_SUM_AT)">
        {{ formula.entries.length > 1 ? `= ${sumOf(formula.entries)} ` : '' }}= {{ pretty(formula.entries_sum) }}
      </span>
    </div>

    <template v-if="!IS_GROUP">
      <span class="text-sm text-ink/70">Total</span>
      <div class="flex flex-wrap items-center gap-2" data-testid="equation-total">
        <span class="piece flex flex-col items-center rounded-lg bg-page px-2 py-1" :style="at(TOTAL_AT)">
          <span class="linear-a text-3xl" :style="{ color: ROLES.total.color }">{{ markerGlyphs || '?' }}</span>
          <span class="text-xs">{{ MARKER }}</span>
        </span>
        <span
          v-for="(term, index) in formula.total"
          :key="term.id"
          class="piece flex flex-col items-center rounded-lg bg-page px-2 py-1"
          :style="at(TOTAL_AT + 1 + index)"
          data-testid="term"
        >
          <span class="linear-a text-3xl" :style="{ color: ROLES.fraction.color }">{{ term.glyph ?? '?' }}</span>
          <span class="text-xs">{{ term.label }} = {{ pretty(term.value) }}</span>
        </span>
        <span v-if="!formula.total.length" class="piece text-ink/70" :style="at(TOTAL_AT)">no fraction</span>
        <span class="piece text-xl font-bold" :style="at(TOTAL_SUM_AT)">= {{ pretty(formula.total_value) }}</span>
      </div>

      <template v-if="CHECK">
        <span class="text-sm text-ink/70">Check</span>
        <span class="piece text-xl font-bold" :style="at(CHECK_AT)" data-testid="equation-check">{{ CHECK }}</span>
      </template>
    </template>
  </div>
</template>

<style scoped>
.piece {
  opacity: 0;
  animation: rise 0.4s ease-out forwards;
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

:global(.still) .piece {
  animation: none;
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .piece {
    animation: none;
    opacity: 1;
  }
}
</style>
