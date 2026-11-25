<script setup>
// Draws the reader's boxes over whatever image is put in the slot: one box per
// sign, coloured by role and settling on in reading order, then a dashed box
// around each fraction formula, coloured by its verdict. Box coordinates are
// fractions of the image size. Hovering or focusing a box shows its SignCard (with Discuss and
// Mention when allowed); clicking it, or pressing Enter or Space on it, also emits `select`.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ROLES, formulaColor, prefersStill, roleKey } from './colors.js'
import SignCard from './SignCard.vue'

const props = defineProps({
  signs: { type: Array, default: () => [] },
  formulas: { type: Array, default: () => [] },
  selectedId: { type: [Number, String], default: null },
  canDiscuss: { type: Boolean, default: false },
  canMention: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'discuss', 'mention'])
const interactive = computed(() => props.canDiscuss || props.canMention)
const root = ref(null)
let closeTimer

function keepCard() {
  clearTimeout(closeTimer)
}

function showCard(signId) {
  keepCard()
  ACTIVE.value = signId
}

function hideCard() {
  keepCard()
  ACTIVE.value = null
}

function scheduleClose() {
  keepCard()
  if (!interactive.value) return hideCard()
  closeTimer = setTimeout(() => {
    const focused = document.activeElement
    if (root.value?.querySelector('[data-testid="sign-card"]')?.contains(focused)) return
    if (focused?.getAttribute('data-sign-id') === String(ACTIVE.value) && root.value?.contains(focused)) return
    hideCard()
  }, 200)
}

function focusDiscussion(event) {
  if (!interactive.value || event.shiftKey) return
  const button = root.value?.querySelector('[data-testid="sign-card"] button')
  if (button) {
    event.preventDefault()
    button.focus()
  }
}

function focusAdjacentBox(event) {
  const buttons = [...root.value.querySelectorAll('[data-testid="sign-card"] button')]
  const current = buttons.indexOf(event.target)
  if (event.shiftKey ? current > 0 : current < buttons.length - 1) return
  const index = props.signs.findIndex((sign) => sign.id === ACTIVE.value)
  const target = props.signs[event.shiftKey ? index : index + 1]
  if (target) {
    event.preventDefault()
    root.value?.querySelector(`[data-sign-id="${target.id}"]`)?.focus()
  }
}

onBeforeUnmount(keepCard)
watch(() => props.signs, hideCard)


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
  <div ref="root" class="relative" @keydown.esc="hideCard">
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
        :data-sign-id="sign.id"
        :data-role="roleKey(sign, MARKERS)"
        :x="percent(sign.box.x)"
        :y="percent(sign.box.y)"
        :width="percent(sign.box.w)"
        :height="percent(sign.box.h)"
        :stroke="ROLES[roleKey(sign, MARKERS)].color"
        :class="{ active: ACTIVE === sign.id, selected: selectedId === sign.id }"
        :style="{ animationDelay: `${index * 60}ms` }"
        :aria-label="describe(sign)"
        :aria-pressed="selectedId === sign.id"
        role="button"
        tabindex="0"
        fill="none"
        pointer-events="all"
        @mouseenter="showCard(sign.id)"
        @mouseleave="scheduleClose"
        @focus="showCard(sign.id)"
        @blur="scheduleClose"
        @click="showCard(sign.id); emit('select', sign)"
        @keydown.enter.prevent="emit('select', sign)"
        @keydown.space.prevent="emit('select', sign)"
        @keydown.tab="focusDiscussion"
      />
    </svg>
    <SignCard
      v-if="SHOWN && ACTIVE_SIGN"
      :sign="ACTIVE_SIGN"
      :role-key="roleKey(ACTIVE_SIGN, MARKERS)"
      :can-discuss="canDiscuss"
      :can-mention="canMention"
      class="absolute z-30"
      :class="{ 'pointer-events-none': !interactive }"
      :style="CARD_STYLE"
      @mouseenter="keepCard"
      @mouseleave="scheduleClose"
      @focusin="keepCard"
      @focusout="scheduleClose"
      @keydown.tab="focusAdjacentBox"
      @discuss="emit('discuss', $event)"
      @mention="emit('mention', $event)"
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
  cursor: pointer;
  outline: none;
  animation: settle 0.45s ease-out forwards;
}

.sign.active {
  stroke-width: 5;
}

/* The glyph the pane below is showing: a thick outline plus a faint fill. */
.sign.selected {
  stroke-width: 6;
  fill: rgba(204, 111, 0, 0.2);
}

.sign:focus-visible {
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
