<script setup>
// Draws the reader's boxes over whatever image is put in the slot: one box per
// sign, coloured by role and settling on in reading order, then a dashed box
// around each fraction formula, coloured by its verdict. Box coordinates are
// fractions of the image size. Hovering or focusing a box shows its SignCard.
import { computed, ref } from 'vue'
import { ROLES, formulaColor, prefersStill, roleKey } from './colors.js'
import SignCard from './SignCard.vue'

const props = defineProps({
  signs: { type: Array, default: () => [] },
  formulas: { type: Array, default: () => [] },
})

const SHOWN = ref(true)
const STILL = prefersStill()
const MARKERS = computed(() => new Set(props.formulas.flatMap((formula) => formula.marker_ids)))
// Formula boxes appear once every sign's box is on.
const FORMULA_DELAY = computed(() => props.signs.length * 60 + 400)

const ACTIVE = ref(null)
const ACTIVE_SIGN = computed(() => props.signs.find((sign) => sign.id === ACTIVE.value) ?? null)

function percent(value) {
  return value * 100
}

function cssPercent(value) {
  return `${Math.round(percent(value) * 10) / 10}%`
}

// Beside the box, on whichever side has more room; anchored at the bottom for low boxes.
const CARD_STYLE = computed(() => {
  const box = ACTIVE_SIGN.value?.box
  if (!box) return {}
  const horizontal = box.x + box.w / 2 < 0.5 ? { left: cssPercent(box.x + box.w + 0.01) } : { right: cssPercent(1 - box.x + 0.01) }
  const vertical = box.y > 0.6 ? { bottom: cssPercent(1 - box.y - box.h) } : { top: cssPercent(box.y) }
  return { ...horizontal, ...vertical }
})

function describe(sign) {
  const meaning = sign.meaning ? `, means ${sign.meaning}` : ''
  return `${sign.reading ?? sign.label} (${sign.sign ?? 'unidentified'}), ${ROLES[roleKey(sign, MARKERS.value)].label}${meaning}, ${Math.round(sign.confidence)}% confident`
}
</script>

<template>
  <div class="relative">
    <slot />
    <svg
      v-if="SHOWN && (signs.length || formulas.length)"
      class="pointer-events-none absolute inset-0 h-full w-full"
      :class="{ still: STILL }"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      data-testid="tablet-overlay"
    >
      <rect
        v-for="(formula, index) in formulas"
        :key="`formula-${index}`"
        class="formula"
        data-testid="formula-box"
        :x="percent(formula.box.x) - 1"
        :y="percent(formula.box.y) - 1"
        :width="percent(formula.box.w) + 2"
        :height="percent(formula.box.h) + 2"
        :stroke="formulaColor(formula)"
        :style="{ animationDelay: `${FORMULA_DELAY}ms` }"
        fill="none"
        rx="1"
      />
      <rect
        v-for="(sign, index) in signs"
        :key="sign.id"
        class="sign"
        data-testid="sign-box"
        :data-role="roleKey(sign, MARKERS)"
        :x="percent(sign.box.x)"
        :y="percent(sign.box.y)"
        :width="percent(sign.box.w)"
        :height="percent(sign.box.h)"
        :stroke="ROLES[roleKey(sign, MARKERS)].color"
        :class="{ active: ACTIVE === sign.id }"
        :style="{ animationDelay: `${index * 60}ms` }"
        :aria-label="describe(sign)"
        tabindex="0"
        fill="none"
        pointer-events="all"
        @mouseenter="ACTIVE = sign.id"
        @mouseleave="ACTIVE = null"
        @focus="ACTIVE = sign.id"
        @blur="ACTIVE = null"
      />
    </svg>
    <SignCard
      v-if="SHOWN && ACTIVE_SIGN"
      :sign="ACTIVE_SIGN"
      :role-key="roleKey(ACTIVE_SIGN, MARKERS)"
      class="pointer-events-none absolute z-30"
      :style="CARD_STYLE"
    />
    <button
      v-if="signs.length"
      type="button"
      class="absolute bottom-2 left-2 cursor-pointer rounded bg-card/90 px-3 py-1 text-sm font-medium shadow hover:brightness-95"
      :aria-pressed="SHOWN"
      @click="SHOWN = !SHOWN"
    >
      Boxes: {{ SHOWN ? 'on' : 'off' }}
    </button>
  </div>
</template>

<style scoped>
/* An inline image leaves a gap below it, which would shift the boxes. */
:slotted(img) {
  display: block;
}

rect {
  vector-effect: non-scaling-stroke;
}

/* Each sign's box settles onto it in turn. (A dash-offset "drawing" effect
   breaks with non-scaling strokes: the boxes stayed as corner fragments.) */
.sign {
  stroke-width: 2.5;
  opacity: 0;
  cursor: help;
  outline: none;
  animation: settle 0.45s ease-out forwards;
}

.sign.active {
  stroke-width: 5;
}

/* The formula box fades in, dashed, after the signs. */
.formula {
  stroke-width: 3;
  stroke-dasharray: 8 5;
  opacity: 0;
  animation: appear 0.6s ease-out forwards;
}

@keyframes settle {
  from {
    opacity: 0;
    transform: scale(1.35);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes appear {
  from {
    opacity: 0;
    transform: scale(1.03);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.sign,
.formula {
  transform-origin: center;
  transform-box: fill-box;
}

.still .sign,
.still .formula {
  animation: none;
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .sign,
  .formula {
    animation: none;
    opacity: 1;
  }
}
</style>
