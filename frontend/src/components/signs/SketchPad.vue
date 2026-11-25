<script setup>
// Sketch to search (workbench, story B): draw a sign with a mouse, finger or pen, and the signs
// that look most like it are suggested, with their typical drawings. Strokes are kept as point
// lists (for undo); the drawing is sent as a transparent PNG 400 ms after the last stroke, and
// only the latest answer is shown. Picking a suggestion emits `pick` with the sign ID.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import SignPreview from './SignPreview.vue'

const props = defineProps({
  limit: { type: Number, default: 8 },
})
const emit = defineEmits(['pick'])

const SIDE = 256 // the exported image, in pixels
const DEBOUNCE_MS = 400
const CANVAS = ref(null)
const STROKES = ref([]) // [{ width, points: [[x, y], ...] }] in canvas pixels
const WIDTH = ref(8)
const RESULTS = ref([])
const STATUS = ref('idle') // idle | searching | done | error
const ERROR = ref('')
let current = null
let timer = null
let request = 0

function context() {
  return CANVAS.value?.getContext?.('2d') ?? null
}

function redraw() {
  const ctx = context()
  if (!ctx) return
  ctx.clearRect(0, 0, SIDE, SIDE)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = '#000'
  for (const stroke of STROKES.value) {
    ctx.lineWidth = stroke.width
    ctx.beginPath()
    stroke.points.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
    if (stroke.points.length === 1) ctx.lineTo(stroke.points[0][0] + 0.1, stroke.points[0][1])
    ctx.stroke()
  }
}

function point(event) {
  const rect = CANVAS.value.getBoundingClientRect()
  const scale = SIDE / (rect.width || SIDE)
  return [(event.clientX - rect.left) * scale, (event.clientY - rect.top) * scale]
}

function down(event) {
  event.preventDefault()
  CANVAS.value.setPointerCapture?.(event.pointerId)
  current = { width: WIDTH.value, points: [point(event)] }
  STROKES.value = [...STROKES.value, current]
  clearTimeout(timer)
  redraw()
}

function move(event) {
  if (!current) return
  current.points.push(point(event))
  redraw()
}

function up() {
  if (!current) return
  current = null
  STROKES.value = [...STROKES.value] // a new array: the watcher below schedules the search
}

function undo() {
  STROKES.value = STROKES.value.slice(0, -1)
}

function clear() {
  STROKES.value = []
}

watch(STROKES, () => {
  redraw()
  clearTimeout(timer)
  if (!STROKES.value.length) {
    request++
    RESULTS.value = []
    STATUS.value = 'idle'
    return
  }
  if (!current) timer = setTimeout(search, DEBOUNCE_MS)
})

function blob() {
  return new Promise((resolve) => {
    if (!CANVAS.value?.toBlob) return resolve(null)
    CANVAS.value.toBlob(resolve, 'image/png')
  })
}

async function search() {
  const mine = ++request
  STATUS.value = 'searching'
  ERROR.value = ''
  try {
    const image = await blob()
    if (!image) throw new Error('This browser cannot send the drawing.')
    const form = new FormData()
    form.append('file', image, 'sketch.png')
    form.append('limit', String(props.limit))
    const response = await fetch('/api/glyphs/sketch', { method: 'POST', body: form })
    const body = await response.json().catch(() => null)
    if (mine !== request) return
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The sketch could not be searched.',
      )
    RESULTS.value = body.items
    STATUS.value = 'done'
  } catch (failure) {
    if (mine !== request) return
    ERROR.value =
      failure instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : failure.message
    STATUS.value = 'error'
  }
}

onMounted(redraw)
onBeforeUnmount(() => clearTimeout(timer))
defineExpose({ search })
</script>

<template>
  <div class="flex flex-col gap-3 sm:flex-row" data-testid="sketch-pad">
    <div>
      <canvas
        ref="CANVAS"
        :width="SIDE"
        :height="SIDE"
        class="block aspect-square w-64 max-w-full cursor-crosshair touch-none rounded-lg border-2 border-dashed border-ink/30 bg-white"
        role="img"
        aria-label="Drawing area: draw a sign with the mouse, a finger or a pen"
        data-testid="sketch-canvas"
        @pointerdown="down"
        @pointermove="move"
        @pointerup="up"
        @pointercancel="up"
        @pointerleave="up"
      />
      <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
        <button
          type="button"
          class="cursor-pointer rounded border border-ink/30 px-2 py-0.5 hover:bg-bar disabled:opacity-50"
          :disabled="!STROKES.length"
          data-testid="sketch-undo"
          @click="undo"
        >
          Undo
        </button>
        <button
          type="button"
          class="cursor-pointer rounded border border-ink/30 px-2 py-0.5 hover:bg-bar disabled:opacity-50"
          :disabled="!STROKES.length"
          data-testid="sketch-clear"
          @click="clear"
        >
          Clear
        </button>
        <label class="flex items-center gap-1">
          Pen
          <input
            v-model.number="WIDTH"
            type="range"
            min="3"
            max="20"
            class="w-20"
            aria-label="Pen width"
          />
        </label>
      </div>
    </div>
    <div class="min-w-0 flex-1" aria-live="polite">
      <p v-if="STATUS === 'idle'" class="text-sm text-ink/80">
        Draw a sign: the most similar ones appear here.
      </p>
      <p v-else-if="STATUS === 'searching' && !RESULTS.length" role="status" class="text-sm">
        Looking…
      </p>
      <p v-else-if="STATUS === 'error'" role="alert" class="text-sm text-confidence-low">
        {{ ERROR }}
      </p>
      <ul
        v-if="RESULTS.length"
        class="grid grid-cols-2 gap-1"
        :class="{ 'opacity-60': STATUS === 'searching' }"
        data-testid="sketch-results"
      >
        <li v-for="sign in RESULTS" :key="sign.sign">
          <button
            type="button"
            class="flex w-full cursor-pointer items-center gap-2 rounded p-1 text-left hover:bg-bar"
            data-testid="sketch-result"
            @click="emit('pick', sign.sign)"
          >
            <SignPreview
              :sign="sign.sign"
              :glyph="sign.glyph ?? ''"
              :preview-url="sign.preview_url"
              :size="36"
            />
            <span class="min-w-0">
              <span class="block font-semibold"
                >{{ sign.sign
                }}<span v-if="sign.reading" class="ml-1 font-normal text-ink/80">{{
                  sign.reading
                }}</span></span
              >
              <span class="block text-xs text-ink/80">{{ Math.round(sign.score) }}% alike</span>
            </span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
