<script setup>
// Your corrected copy of a tablet's boxes (#85): move, resize, draw and delete boxes, name
// each box's sign, then save. Saving sends every change as one batch; the reading below
// (lines, transliteration, fraction check) is worked out again from the saved boxes.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import BoxEditor from '../components/boxes/BoxEditor.vue'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import { useBoxSet } from '../composables/useBoxSet'
import '../components/analysis/linearA.css'

const route = useRoute()
const router = useRouter()
const set = useBoxSet()
const { copy, boxes, loading, saving, error, conflict, changes, dirty, history } = set
const SELECTED_ID = ref(null)
const MODE = ref('select')
const CATALOGUE = ref([])
const QUERY = ref('')
const IMAGE_MISSING = ref(false)
const NOTICE = ref('')

const SELECTED = computed(() => boxes.value.find((box) => box.id === SELECTED_ID.value) ?? null)
// The reading's sign for each box whose sign has not changed since the last save; boxes
// drawn or renamed since are shown grey until saved, since their role is not known yet.
const READ = computed(() => {
  const now = new Map(boxes.value.map((box) => [box.id, box]))
  return Object.fromEntries((copy.value?.reading.signs ?? [])
    .filter((sign) => now.get(sign.id)?.sign === sign.sign)
    .map((sign) => [sign.id, sign]))
})
const MARKERS = computed(() => new Set((copy.value?.reading.formulas ?? []).flatMap((formula) => formula.marker_ids)))
const GLYPHS = computed(() => Object.fromEntries(CATALOGUE.value.map((sign) => [sign.sign, sign])))
const MATCHES = computed(() => {
  const query = QUERY.value.trim().toLowerCase()
  if (!query) return []
  return CATALOGUE.value.filter((sign) => sign.sign.toLowerCase().includes(query) || sign.name.toLowerCase().includes(query)).slice(0, 12)
})
const READING = computed(() => copy.value && { ...copy.value.reading, width: copy.value.width, height: copy.value.height, trained: true })
const ORDERED = computed(() => {
  // The box list follows reading order; boxes not read yet (new since the save) come last.
  const order = new Map((copy.value?.reading.signs ?? []).map((sign, index) => [sign.id, index]))
  return [...boxes.value].sort((a, b) => (order.get(a.id) ?? 1e9) - (order.get(b.id) ?? 1e9) || a.id - b.id)
})

const signName = (sign) => (sign ? GLYPHS.value[sign]?.name ?? sign : 'Unnamed')
const glyphOf = (sign) => (sign ? GLYPHS.value[sign]?.glyph ?? '' : '')

async function load() {
  try {
    await set.load(route.params.id)
  } catch (failed) {
    if (failed.status === 401) await router.push({ path: '/login', query: { redirect: route.fullPath } })
  }
  SELECTED_ID.value = null
}

async function loadCatalogue() {
  try {
    const response = await fetch('/api/corrections/catalogue')
    if (response.ok) CATALOGUE.value = await response.json()
  } catch {
    // Without the catalogue the picker offers the model's guesses only.
  }
}

function draw(box) {
  SELECTED_ID.value = set.addBox(box)
  MODE.value = 'select' // name the new box next
}

function remove(id) {
  set.removeBox(id)
  if (SELECTED_ID.value === id) SELECTED_ID.value = null
}

function pick(sign) {
  if (SELECTED.value) set.setSign(SELECTED.value.id, sign)
  QUERY.value = ''
}

async function save() {
  NOTICE.value = ''
  const count = changes.value.length
  if (await set.save()) {
    NOTICE.value = `Saved ${count} change${count === 1 ? '' : 's'}.`
    if (!boxes.value.some((box) => box.id === SELECTED_ID.value)) SELECTED_ID.value = null
  }
}

function discard() {
  if (window.confirm('Throw away your unsaved changes?')) {
    set.discard()
    SELECTED_ID.value = null
  }
}

function onKey(event) {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName)
  if (typing) return
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    set.undo()
  } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    save()
  }
}

function warnBeforeClosing(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => !dirty.value || window.confirm('You have unsaved changes. Leave without saving?'))
onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('beforeunload', warnBeforeClosing)
  loadCatalogue()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('beforeunload', warnBeforeClosing)
})
watch(() => route.params.id, load, { immediate: true })
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <RouterLink
      v-if="copy?.source.analysis_id"
      :to="`/profile/history/${copy.source.analysis_id}`"
      class="underline"
    >← Saved analysis</RouterLink>
    <RouterLink v-else-if="copy?.source.tablet" :to="`/tablets/${copy.source.tablet}`" class="underline">← {{ copy.source.tablet.replaceAll('-', ' ') }}</RouterLink>
    <h1 class="mt-4 text-3xl font-bold">Correct the boxes</h1>
    <p v-if="copy" class="mt-1 text-ink/70">{{ copy.source.filename || copy.source.tablet.replaceAll('-', ' ') }} · your corrected copy<template v-if="copy.source.tablet">, started from the {{ copy.start === 'scholar' ? "scholars'" : "model's" }} boxes</template></p>

    <p v-if="loading" role="status" class="mt-6">Loading…</p>
    <p v-else-if="error && !copy" role="alert" class="mt-6">{{ error }}</p>

    <div v-if="copy" class="mt-6 flex flex-col gap-8 lg:flex-row">
      <section class="lg:w-3/5" aria-label="Tablet">
        <div class="mb-3 flex flex-wrap items-center gap-2" role="toolbar" aria-label="Editing tools">
          <button
            v-for="option in [{ value: 'select', label: 'Select and move' }, { value: 'draw', label: 'Draw a box' }]"
            :key="option.value"
            type="button"
            class="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-bar"
            :class="{ 'bg-bar font-semibold': MODE === option.value }"
            :aria-pressed="MODE === option.value"
            :data-testid="`mode-${option.value}`"
            @click="MODE = option.value"
          >{{ option.label }}</button>
          <button type="button" class="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-bar disabled:opacity-50" :disabled="!history.length" data-testid="undo" title="Ctrl+Z" @click="set.undo()">Undo</button>
          <span class="ml-auto text-sm" :class="dirty ? 'font-semibold' : 'text-ink/70'" role="status" data-testid="save-state">
            {{ dirty ? `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}` : 'All changes saved' }}
          </span>
          <button type="button" class="cursor-pointer rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5 disabled:opacity-50" :disabled="!dirty || saving" data-testid="discard" @click="discard">Discard</button>
          <button type="button" class="cursor-pointer rounded bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:brightness-95 disabled:opacity-50" :disabled="!dirty || saving" data-testid="save" title="Ctrl+S" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>

        <p v-if="IMAGE_MISSING" role="alert" class="rounded-lg bg-card p-4">The tablet image could not be loaded.</p>
        <BoxEditor
          v-else
          :image-url="`/api${copy.image_url}`"
          :alt="copy.source.filename || 'Tablet'"
          :boxes="boxes"
          :roles="READ"
          :markers="MARKERS"
          :selected-id="SELECTED_ID"
          :mode="MODE"
          @select="SELECTED_ID = $event"
          @begin="set.beginGesture()"
          @place="set.place"
          @end="set.endGesture()"
          @draw="draw"
          @remove="remove"
          @nudge="set.setBox"
          @image-error="IMAGE_MISSING = true"
        />
        <p class="mt-2 text-sm text-ink/70">
          Drag a box to move it and its corners to resize it. In <em>Draw a box</em> mode, drag on the tablet.
          Dashed boxes are ones you changed; grey ones have no sign yet. Arrow keys move the selected box,
          Shift with arrows resizes it, Delete removes it, Ctrl+Z undoes.
        </p>
      </section>

      <aside class="flex flex-col gap-6 lg:flex-1">
        <div v-if="conflict" role="alert" class="rounded-2xl border border-confidence-low p-4" data-testid="conflict">
          <p>{{ error }}</p>
          <button type="button" class="mt-2 cursor-pointer underline" @click="set.takeNewer(); SELECTED_ID = null">Load their version (drops your unsaved changes)</button>
        </div>
        <p v-else-if="error" role="alert" class="text-confidence-low">{{ error }}</p>
        <p v-if="NOTICE && !dirty" role="status" class="rounded-lg bg-accent/10 p-3">{{ NOTICE }}</p>

        <section class="rounded-3xl bg-card p-5" aria-labelledby="selected-h" data-testid="selected-panel">
          <h2 id="selected-h" class="text-xl font-bold">Selected box</h2>
          <p v-if="!SELECTED" class="mt-2 text-ink/70">Click a box on the tablet, or one in the list below.</p>
          <template v-else>
            <p class="mt-2 text-lg">
              <span class="linear-a text-3xl" aria-hidden="true">{{ glyphOf(SELECTED.sign) }}</span>
              <span class="font-semibold" data-testid="selected-sign">{{ signName(SELECTED.sign) }}</span>
            </p>
            <p v-if="SELECTED.model_sign && SELECTED.model_sign !== SELECTED.sign" class="text-sm text-ink/70">
              The model read {{ signName(SELECTED.model_sign) }}<template v-if="SELECTED.model_confidence"> ({{ Math.round(SELECTED.model_confidence) }}%)</template>.
            </p>
            <p v-else-if="SELECTED.origin === 'user' || SELECTED.id < 0" class="text-sm text-ink/70">You drew this box.</p>

            <div v-if="SELECTED.candidates?.length" class="mt-4">
              <h3 class="text-sm font-semibold">The model's guesses</h3>
              <div class="mt-1 flex flex-wrap gap-2">
                <button
                  v-for="candidate in SELECTED.candidates"
                  :key="candidate.sign"
                  type="button"
                  class="cursor-pointer rounded border border-ink/20 px-2 py-1 text-sm hover:bg-bar"
                  :class="{ 'bg-bar font-semibold': candidate.sign === SELECTED.sign }"
                  :aria-pressed="candidate.sign === SELECTED.sign"
                  data-testid="candidate"
                  @click="pick(candidate.sign)"
                >
                  <span class="linear-a" aria-hidden="true">{{ glyphOf(candidate.sign) }}</span>
                  {{ candidate.label }} <span class="text-ink/60">{{ Math.round(candidate.probability) }}%</span>
                </button>
              </div>
            </div>

            <label class="mt-4 block text-sm font-semibold" for="sign-search">Find another sign</label>
            <input
              id="sign-search"
              v-model="QUERY"
              type="search"
              placeholder="AB81, ku, VIN…"
              autocomplete="off"
              class="mt-1 w-full rounded border border-ink/30 bg-white px-3 py-1.5"
              @keydown.enter.prevent="MATCHES.length && pick(MATCHES[0].sign)"
            />
            <ul v-if="MATCHES.length" class="mt-1 max-h-48 overflow-auto rounded border border-ink/15 bg-white" data-testid="sign-matches">
              <li v-for="sign in MATCHES" :key="sign.sign">
                <button type="button" class="w-full cursor-pointer px-3 py-1 text-left hover:bg-bar" @click="pick(sign.sign)">
                  <span class="linear-a" aria-hidden="true">{{ sign.glyph }}</span> {{ sign.name }}
                </button>
              </li>
            </ul>
            <p v-else-if="QUERY.trim()" class="mt-1 text-sm text-ink/70">No sign matches.</p>

            <div class="mt-4 flex flex-wrap gap-3">
              <button v-if="SELECTED.sign" type="button" class="cursor-pointer text-sm underline" data-testid="clear-sign" @click="pick(null)">Clear the sign</button>
              <button type="button" class="cursor-pointer text-sm text-confidence-low underline" data-testid="delete-box" @click="remove(SELECTED.id)">Delete this box</button>
            </div>
          </template>
        </section>

        <section class="rounded-3xl bg-card p-5" aria-labelledby="boxes-h">
          <h2 id="boxes-h" class="text-xl font-bold">Boxes ({{ boxes.length }})</h2>
          <ol class="mt-2 max-h-72 overflow-auto">
            <li v-for="box in ORDERED" :key="box.id">
              <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1 text-left hover:bg-bar"
                :class="{ 'bg-bar font-semibold': box.id === SELECTED_ID }"
                :aria-pressed="box.id === SELECTED_ID"
                data-testid="box-row"
                @click="SELECTED_ID = box.id"
              >
                <span class="linear-a w-8 text-xl" aria-hidden="true">{{ glyphOf(box.sign) }}</span>
                <span>{{ signName(box.sign) }}</span>
                <span v-if="box.id < 0" class="ml-auto text-xs text-ink/70">new</span>
                <span v-else-if="box.changed" class="ml-auto text-xs text-ink/70">changed</span>
              </button>
            </li>
          </ol>
        </section>
      </aside>
    </div>

    <section v-if="copy" class="mt-10" aria-labelledby="reading-h">
      <h2 id="reading-h" class="text-2xl font-bold">Reading of the saved boxes</h2>
      <p class="mt-1 text-ink/70">{{ dirty ? 'Save to update the reading with your latest changes.' : copy.reading.summary }}</p>
      <p class="mt-2"><span class="text-ink/70">Transliteration:</span> {{ copy.reading.symbol_interpretation }}</p>
      <FractionCheck :analysis="READING" class="mt-6" />
    </section>
  </main>
</template>
