<script setup>
// The drawing surface of the box editor (#85): the tablet image with its boxes on top.
// Select mode: click a box to select it, drag it to move, drag a corner to resize.
// Draw mode: drag on the image to draw a new box. Keys: arrows move the selected box
// (Shift+arrows resize it), Delete removes it, Escape deselects or cancels a drawing.
// Coordinates are fractions of the image, as everywhere else in the app.
import { computed, ref } from 'vue'
import { ROLES, roleKey } from '../analysis/colors.js'
import { MIN_SIDE } from '../../composables/useBoxSet'

const props = defineProps({
  imageUrl: { type: String, required: true },
  alt: { type: String, default: 'Tablet' },
  boxes: { type: Array, required: true }, // [{ id, box, sign, ... }]
  roles: { type: Object, default: () => ({}) }, // box id -> sign as read (role), from the last save
  markers: { type: Object, default: () => new Set() }, // KU-RO box ids
  selectedId: { type: Number, default: null },
  mode: { type: String, default: 'select' }, // select | draw
  readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'begin', 'place', 'end', 'draw', 'remove', 'nudge', 'image-error'])

const SURFACE = ref(null)
const DRAFT = ref(null) // the box being drawn
const STEP = 0.002 // one arrow press: about 2 px on a 1000 px tablet
const CORNERS = [
  { key: 'nw', x: 0, y: 0, cursor: 'nwse-resize' },
  { key: 'ne', x: 1, y: 0, cursor: 'nesw-resize' },
  { key: 'sw', x: 0, y: 1, cursor: 'nesw-resize' },
  { key: 'se', x: 1, y: 1, cursor: 'nwse-resize' },
]
let gesture = null

const SELECTED = computed(() => props.boxes.find((box) => box.id === props.selectedId) ?? null)

function colour(box) {
  const sign = props.roles[box.id]
  if (!sign) return ROLES.other.color // drawn or relabelled since the last save
  return ROLES[roleKey(sign, props.markers)].color
}

function describe(box) {
  const sign = props.roles[box.id]
  return `${box.sign ? sign?.label ?? box.sign : 'Unnamed box'}${box.changed ? ', changed' : ''}`
}

function point(event) {
  const rect = SURFACE.value.getBoundingClientRect()
  return {
    x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
    y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1),
  }
}

function capture(event) {
  event.currentTarget?.setPointerCapture?.(event.pointerId)
}

function startMove(event, box) {
  if (props.readOnly || props.mode !== 'select' || event.button !== 0) {
    emit('select', box.id)
    return
  }
  event.stopPropagation()
  emit('select', box.id)
  gesture = { kind: 'move', id: box.id, from: point(event), box: { ...box.box } }
  emit('begin')
  capture(event)
}

function startResize(event, corner) {
  if (props.readOnly || !SELECTED.value || event.button !== 0) return
  event.stopPropagation()
  gesture = { kind: 'resize', id: SELECTED.value.id, corner, box: { ...SELECTED.value.box } }
  emit('begin')
  capture(event)
}

function startDraw(event) {
  if (event.button !== 0) return
  if (props.readOnly || props.mode !== 'draw') {
    emit('select', null)
    return
  }
  const from = point(event)
  gesture = { kind: 'draw', from }
  DRAFT.value = { x: from.x, y: from.y, w: 0, h: 0 }
  capture(event)
}

function onMove(event) {
  if (!gesture) return
  const at = point(event)
  if (gesture.kind === 'move') {
    const { box, from } = gesture
    emit('place', gesture.id, { ...box, x: box.x + at.x - from.x, y: box.y + at.y - from.y })
  } else if (gesture.kind === 'resize') {
    const { box, corner } = gesture
    // The opposite corner stays where it is.
    const left = corner.x === 0 ? Math.min(at.x, box.x + box.w - MIN_SIDE) : box.x
    const top = corner.y === 0 ? Math.min(at.y, box.y + box.h - MIN_SIDE) : box.y
    const right = corner.x === 1 ? Math.max(at.x, box.x + MIN_SIDE) : box.x + box.w
    const bottom = corner.y === 1 ? Math.max(at.y, box.y + MIN_SIDE) : box.y + box.h
    emit('place', gesture.id, { x: left, y: top, w: right - left, h: bottom - top })
  } else if (gesture.kind === 'draw') {
    const { from } = gesture
    DRAFT.value = { x: Math.min(from.x, at.x), y: Math.min(from.y, at.y), w: Math.abs(at.x - from.x), h: Math.abs(at.y - from.y) }
  }
}

function onUp() {
  if (!gesture) return
  if (gesture.kind === 'draw') {
    // A click without a drag draws nothing.
    if (DRAFT.value && DRAFT.value.w >= MIN_SIDE * 2 && DRAFT.value.h >= MIN_SIDE * 2) emit('draw', { ...DRAFT.value })
    DRAFT.value = null
  } else {
    emit('end')
  }
  gesture = null
}

function onKey(event) {
  if (event.key === 'Escape') {
    if (gesture?.kind === 'draw') {
      gesture = null
      DRAFT.value = null
    } else {
      emit('select', null)
    }
    return
  }
  if (props.readOnly || !SELECTED.value) return
  if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    emit('remove', SELECTED.value.id)
    return
  }
  const moves = { ArrowLeft: [-STEP, 0], ArrowRight: [STEP, 0], ArrowUp: [0, -STEP], ArrowDown: [0, STEP] }
  const delta = moves[event.key]
  if (!delta) return
  event.preventDefault()
  const box = SELECTED.value.box
  const next = event.shiftKey
    ? { ...box, w: box.w + delta[0], h: box.h + delta[1] }
    : { ...box, x: box.x + delta[0], y: box.y + delta[1] }
  emit('nudge', SELECTED.value.id, next)
}

const pct = (value) => value * 100
</script>

<template>
  <div
    ref="SURFACE"
    class="editor relative select-none outline-none focus-visible:ring-2 focus-visible:ring-accent"
    :class="{ drawing: mode === 'draw' && !readOnly }"
    tabindex="0"
    role="application"
    :aria-label="readOnly ? 'Tablet with its boxes (read only)' : 'Box editor. Select a box by clicking it or from the list of boxes; then arrows move it, Shift and arrows resize it, Delete removes it.'"
    data-testid="box-editor"
    @pointerdown="startDraw"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointercancel="onUp"
    @keydown="onKey"
  >
    <img :src="imageUrl" :alt="alt" class="block w-full rounded-lg bg-white" draggable="false" @error="emit('image-error')" />
    <svg class="absolute inset-0 h-full w-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
      <rect
        v-for="box in boxes"
        :key="box.id"
        class="box"
        data-testid="edit-box"
        :data-id="box.id"
        :class="{ selected: box.id === selectedId, changed: box.changed || box.id < 0, unnamed: !box.sign }"
        :x="pct(box.box.x)"
        :y="pct(box.box.y)"
        :width="pct(box.box.w)"
        :height="pct(box.box.h)"
        :stroke="colour(box)"
        :aria-label="describe(box)"
        :aria-pressed="box.id === selectedId"
        role="button"
        tabindex="-1"
        fill="transparent"
        @pointerdown="startMove($event, box)"
      />
      <rect
        v-if="DRAFT"
        class="draft"
        data-testid="draft-box"
        :x="pct(DRAFT.x)"
        :y="pct(DRAFT.y)"
        :width="pct(DRAFT.w)"
        :height="pct(DRAFT.h)"
        fill="none"
      />
    </svg>
    <template v-if="SELECTED && !readOnly && mode === 'select'">
      <span
        v-for="corner in CORNERS"
        :key="corner.key"
        class="handle"
        :data-testid="`handle-${corner.key}`"
        :style="{
          left: `${pct(SELECTED.box.x + corner.x * SELECTED.box.w)}%`,
          top: `${pct(SELECTED.box.y + corner.y * SELECTED.box.h)}%`,
          cursor: corner.cursor,
        }"
        @pointerdown="startResize($event, corner)"
      />
    </template>
  </div>
</template>

<style scoped>
rect {
  vector-effect: non-scaling-stroke;
}

.editor {
  touch-action: none; /* dragging a box must not scroll the page on touch screens */
}

.editor.drawing {
  cursor: crosshair;
}

.box {
  stroke-width: 2.5;
  cursor: move;
}

.drawing .box {
  cursor: crosshair;
}

/* Changed since the copy was made: dashed, so changes stand out from the model's boxes. */
.box.changed {
  stroke-dasharray: 6 3;
}

.box.unnamed {
  stroke: #7a7a7a;
}

.box.selected {
  stroke-width: 4;
  fill: rgba(204, 111, 0, 0.15);
}

.draft {
  stroke: #cc6f00;
  stroke-width: 2;
  stroke-dasharray: 4 2;
}

.handle {
  position: absolute;
  width: 12px;
  height: 12px;
  margin: -6px 0 0 -6px;
  border: 2px solid #cc6f00;
  border-radius: 2px;
  background: white;
  touch-action: none;
}
</style>
