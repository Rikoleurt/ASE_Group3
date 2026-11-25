<script setup>
// Zoom, pan and image filters around a tablet editor (workbench, story K). The content is made
// wider inside a scrolling frame instead of being transformed, so everything drawn in
// percentages (boxes, handles, badges) scales with it and pointer positions stay exact.
// Zoom: the buttons, Ctrl + wheel (a trackpad pinch arrives as this), or + - 0 in the editor.
// Pan: scroll, or drag with the space bar held or the middle button.
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const MIN = 1
const MAX = 8
const STEP = 1.25

const FRAME = ref(null)
const ZOOM = ref(1)
const INVERT = ref(false)
const CONTRAST = ref(false)
let space = false
let panning = null

async function zoomTo(value, around = null) {
  const frame = FRAME.value
  const next = Math.min(MAX, Math.max(MIN, Math.round(value * 100) / 100))
  if (!frame || next === ZOOM.value) return
  // Keep the point under the cursor (or the middle of the view) where it is.
  const rect = frame.getBoundingClientRect()
  const cx = around ? around.x - rect.left : frame.clientWidth / 2
  const cy = around ? around.y - rect.top : frame.clientHeight / 2
  const fx = (frame.scrollLeft + cx) / (frame.scrollWidth || 1)
  const fy = (frame.scrollTop + cy) / (frame.scrollHeight || 1)
  ZOOM.value = next
  await nextTick()
  frame.scrollLeft = fx * frame.scrollWidth - cx
  frame.scrollTop = fy * frame.scrollHeight - cy
}

const zoomIn = () => zoomTo(ZOOM.value * STEP)
const zoomOut = () => zoomTo(ZOOM.value / STEP)
const fit = () => zoomTo(1)

function wheel(event) {
  if (!event.ctrlKey) return // a plain wheel scrolls the page and the frame as usual
  event.preventDefault()
  zoomTo(ZOOM.value * Math.exp(-event.deltaY * 0.002), { x: event.clientX, y: event.clientY })
}

function startPan(event) {
  if (!(space || event.button === 1)) return
  event.preventDefault()
  event.stopPropagation() // the editor below must not start a drag or a box
  panning = {
    x: event.clientX,
    y: event.clientY,
    left: FRAME.value.scrollLeft,
    top: FRAME.value.scrollTop,
  }
  FRAME.value.setPointerCapture?.(event.pointerId)
}

function pan(event) {
  if (!panning) return
  FRAME.value.scrollLeft = panning.left - (event.clientX - panning.x)
  FRAME.value.scrollTop = panning.top - (event.clientY - panning.y)
}

function endPan() {
  panning = null
}

function key(event) {
  if (
    event.key === ' ' &&
    !['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(event.target?.tagName)
  ) {
    if (event.type === 'keydown' && FRAME.value?.matches(':hover')) event.preventDefault() // no page scroll
    space = event.type === 'keydown'
  }
}

onMounted(() => {
  window.addEventListener('keydown', key)
  window.addEventListener('keyup', key)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', key)
  window.removeEventListener('keyup', key)
})
defineExpose({ zoomIn, zoomOut, fit, ZOOM })
</script>

<template>
  <div>
    <div class="mb-2 flex flex-wrap items-center gap-1 text-sm" role="group" aria-label="View">
      <button
        type="button"
        class="cursor-pointer rounded border border-ink/30 px-2 hover:bg-bar disabled:opacity-40"
        :disabled="ZOOM <= MIN"
        aria-label="Zoom out (-)"
        data-testid="zoom-out"
        @click="zoomOut"
      >
        −
      </button>
      <span class="w-12 text-center tabular-nums" data-testid="zoom-level"
        >{{ Math.round(ZOOM * 100) }}%</span
      >
      <button
        type="button"
        class="cursor-pointer rounded border border-ink/30 px-2 hover:bg-bar disabled:opacity-40"
        :disabled="ZOOM >= MAX"
        aria-label="Zoom in (+)"
        data-testid="zoom-in"
        @click="zoomIn"
      >
        +
      </button>
      <button
        type="button"
        class="cursor-pointer rounded px-2 hover:bg-bar disabled:opacity-40"
        :disabled="ZOOM === 1"
        data-testid="zoom-fit"
        @click="fit"
      >
        Fit
      </button>
      <span class="mx-1 h-4 w-px bg-ink/20" aria-hidden="true" />
      <label class="flex cursor-pointer items-center gap-1"
        ><input v-model="INVERT" type="checkbox" data-testid="invert" /> Invert</label
      >
      <label class="flex cursor-pointer items-center gap-1"
        ><input v-model="CONTRAST" type="checkbox" data-testid="contrast" /> More contrast</label
      >
      <span class="ml-auto text-xs text-ink/80">Ctrl + wheel to zoom · space + drag to pan</span>
    </div>
    <div
      ref="FRAME"
      class="max-h-[80vh] overflow-auto rounded-lg"
      data-testid="zoom-frame"
      @wheel="wheel"
      @pointerdown.capture="startPan"
      @pointermove="pan"
      @pointerup="endPan"
      @pointercancel="endPan"
    >
      <div
        :style="{ width: `${ZOOM * 100}%` }"
        :class="{ '[&_img]:invert': INVERT, '[&_img]:contrast-200': CONTRAST }"
        data-testid="zoom-content"
      >
        <slot />
      </div>
    </div>
  </div>
</template>
