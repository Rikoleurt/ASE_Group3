<script setup>
// Your corrected copy of a tablet's boxes (#85): move, resize, draw and delete boxes, name
// each box's sign, then save. Saving sends every change as one batch; the reading below
// (lines, transliteration, fraction check) is worked out again from the saved boxes.
import DiscussionLinks from '../components/DiscussionLinks.vue'
import { useGlyphActivity } from '../composables/useGlyphActivity'
import ReleasePanel from '../components/versions/ReleasePanel.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import BoxEditor from '../components/boxes/BoxEditor.vue'
import ShareDialog from '../components/boxes/ShareDialog.vue'
import HistoryPanel from '../components/boxes/HistoryPanel.vue'
import BoxComments from '../components/boxes/BoxComments.vue'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import SignPicker from '../components/signs/SignPicker.vue'
import SignPreview from '../components/signs/SignPreview.vue'
import { marksOf, useBoxSet } from '../composables/useBoxSet'
import MarksPanel from '../components/boxes/MarksPanel.vue'
import ShortcutHelp from '../components/boxes/ShortcutHelp.vue'
import ZoomFrame from '../components/boxes/ZoomFrame.vue'
import { useCatalogue } from '../composables/useCatalogue'
import '../components/analysis/linearA.css'

const route = useRoute()
const router = useRouter()
const set = useBoxSet()
const { copy, boxes, loading, saving, error, conflict, changes, dirty, history } = set
const SELECTED_ID = ref(null)
const ZOOMER = ref(null)
const HELP = ref(false) // the shortcut list (?)
// Setting the reading order by hand (workbench, story F): lines of box ids, clicked in order.
const ORDERING = ref(null)
const ORDER_BADGES = computed(() => Object.fromEntries((ORDERING.value ?? []).flatMap((ids, line) => ids.map((id, seq) => [id, `${line + 1}·${seq + 1}`]))))

function startOrdering() {
  SELECTED_ID.value = null
  ORDERING.value = [[]]
}

function chooseBox(id) {
  if (!ORDERING.value) {
    SELECTED_ID.value = id
    return
  }
  if (id == null || ORDERING.value.some((ids) => ids.includes(id))) return
  const lines = ORDERING.value.map((ids) => [...ids])
  lines[lines.length - 1].push(id)
  ORDERING.value = lines
}

function newLine() {
  if (ORDERING.value.at(-1).length) ORDERING.value = [...ORDERING.value, []]
}

function finishOrdering(apply) {
  if (apply) set.setOrder(ORDERING.value.filter((ids) => ids.length))
  ORDERING.value = null
}
// Bubbles with new activity on boxes that started as a scholars' sign (workbench, story I).
const TABLET = computed(() => copy.value?.source.tablet ?? null)
const { COUNTS: ACTIVITY, seen } = useGlyphActivity(TABLET)
const positionOf = (box) => (box?.source?.kind === 'scholar' ? box.source.box_id : null)
const BADGES = computed(() => Object.fromEntries(boxes.value.filter((box) => ACTIVITY.value[positionOf(box)]).map((box) => [box.id, ACTIVITY.value[positionOf(box)]])))
watch(SELECTED_ID, (id) => seen(positionOf(boxes.value.find((box) => box.id === id))))
const MODE = ref('select')
const CATALOGUE = useCatalogue()
const IMAGE_MISSING = ref(false)
const NOTICE = ref('')
const SHARING = ref(false)
const RANK = { view: 1, comment: 2, edit: 3, manage: 4, owner: 5 }
// What you may do with this copy (#84): below edit, the page is read only.
const CAN_EDIT = computed(() => RANK[copy.value?.permission] >= RANK.edit)
const CAN_SHARE = computed(() => RANK[copy.value?.permission] >= RANK.manage)
const CAN_COMMENT = computed(() => RANK[copy.value?.permission] >= RANK.comment)
const GHOST = ref(null) // the box as it was before the change picked in the history
const EDITOR = ref(null)
const HISTORY_BUSY = ref(false) // an undo from the history is on its way
// Editing pauses while a save or an undo is in flight: their reply replaces the boxes, and
// anything changed meanwhile would be silently lost (#98).
const LOCKED = computed(() => !CAN_EDIT.value || saving.value || HISTORY_BUSY.value)
const EVERYONE_TEXT = { view: 'view', comment: 'comment', edit: 'edit' }

// A change picked in the history: select its box if it is still there, and outline where it was.
function showChange(change) {
  if (!change) {
    GHOST.value = null
    return
  }
  const now = boxes.value.find((box) => box.id === change.box_id)
  SELECTED_ID.value = now ? now.id : null
  const before = change.before && !change.before.deleted ? change.before.box : null
  const moved = before && (!now || ['x', 'y', 'w', 'h'].some((key) => Math.abs(before[key] - now.box[key]) > 1e-9))
  GHOST.value = moved ? before : null
}

function reverted(newer) {
  set.accept(newer)
  GHOST.value = null
  if (!boxes.value.some((box) => box.id === SELECTED_ID.value)) SELECTED_ID.value = null
  NOTICE.value = 'The change was reverted.'
}
const LEVEL_TEXT = { view: 'can view', comment: 'can view and comment', edit: 'can edit', manage: 'can manage' }

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
const READING = computed(() => copy.value && { ...copy.value.reading, width: copy.value.width, height: copy.value.height, trained: true })
const ORDERED = computed(() => {
  // The box list follows reading order; boxes not read yet (new since the save) come last.
  const order = new Map((copy.value?.reading.signs ?? []).map((sign, index) => [sign.id, index]))
  return [...boxes.value].sort((a, b) => (order.get(a.id) ?? 1e9) - (order.get(b.id) ?? 1e9) || a.id - b.id)
})

// How an edition names one of the versions it was merged from.
function mergedName(source) {
  if (source.kind === 'scholar') return "the scholars' boxes"
  if (source.kind === 'model') return "the model's boxes"
  const what = `${source.owner}'s ${source.kind === 'edition' ? 'edition' : 'copy'}`
  return source.title ? `${what} “${source.title}”` : what
}

// "No sign yet" in lists and headings; HistoryPanel and the screen-reader labels use it too.
const signName = (sign) => (sign ? GLYPHS.value[sign]?.name ?? sign : 'No sign yet')
const glyphOf = (sign) => (sign ? GLYPHS.value[sign]?.glyph ?? '' : '')

let loadId = 0
async function load() {
  const mine = ++loadId
  // A different copy (or a reload) starts clean (#98).
  SELECTED_ID.value = null
  GHOST.value = null
  NOTICE.value = ''
  SHARING.value = false
  IMAGE_MISSING.value = false
  MODE.value = 'select'
  try {
    await set.load(route.params.id)
  } catch (failed) {
    if (mine === loadId && failed.status === 401) await router.push({ path: '/login', query: { redirect: route.fullPath } })
  }
}

function draw(box) {
  NOTICE.value = ''
  SELECTED_ID.value = set.addBox(box)
  MODE.value = 'select' // name the new box next
}

function remove(id) {
  NOTICE.value = ''
  set.removeBox(id)
  if (SELECTED_ID.value === id) SELECTED_ID.value = null
}

function pick(sign) {
  NOTICE.value = ''
  if (SELECTED.value) set.setSign(SELECTED.value.id, sign)
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
    NOTICE.value = ''
  }
}

// Editor shortcuts (workbench, story K); ? lists them. Returns whether the key was one.
function shortcut(event) {
  const key = event.key
  if (key === '?') {
    HELP.value = !HELP.value
    return true
  }
  if (key === 'Escape' && HELP.value) {
    HELP.value = false
    return true
  }
  const zoom = { '+': 'zoomIn', '=': 'zoomIn', '-': 'zoomOut', '0': 'fit' }[key]
  if (zoom) {
    ZOOMER.value?.[zoom]()
    return true
  }
  const lower = key.toLowerCase()
  if (lower === 'n' || lower === 'p') {
    const order = ORDERED.value
    if (!order.length) return true
    const at = order.findIndex((box) => box.id === SELECTED_ID.value)
    const step = lower === 'n' ? 1 : -1
    SELECTED_ID.value = order[at < 0 ? (step > 0 ? 0 : order.length - 1) : (at + step + order.length) % order.length].id
    return true
  }
  if (!CAN_EDIT.value) return false
  if (lower === 'v' || lower === 'd') {
    MODE.value = lower === 'v' ? 'select' : 'draw'
    return true
  }
  if (/^[1-5]$/.test(key) && SELECTED.value?.candidates?.[Number(key) - 1]) {
    pick(SELECTED.value.candidates[Number(key) - 1].sign)
    return true
  }
  return false
}

function onKey(event) {
  // Typing in a text field is not a shortcut; a focused checkbox, radio or slider does not count.
  const target = event.target
  const typing = ['TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable ||
    (target?.tagName === 'INPUT' && !['checkbox', 'radio', 'range', 'button'].includes(target.type))
  // Shortcuts wait for a drag, a save or an undo to finish (#98).
  if (typing || LOCKED.value || EDITOR.value?.busy()) return
  const plain = !event.ctrlKey && !event.metaKey && !event.altKey
  if (plain && shortcut(event)) {
    event.preventDefault()
    return
  }
  if (plain && CAN_EDIT.value && SELECTED.value && ['u', 'w'].includes(event.key.toLowerCase())) {
    // U: uncertain reading on or off; W: a word ends after this sign (workbench, story F).
    event.preventDefault()
    const marks = marksOf(SELECTED.value)
    set.setMarks(SELECTED.value.id, event.key.toLowerCase() === 'u'
      ? { certainty: marks.certainty === 'uncertain' ? 'certain' : 'uncertain' }
      : { word_end: !marks.word_end })
    return
  }
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

const leave = () => !dirty.value || window.confirm('You have unsaved changes. Leave without saving?')
onBeforeRouteLeave(leave)
onBeforeRouteUpdate(leave) // another copy at the same page
onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('beforeunload', warnBeforeClosing)
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
      v-if="copy?.source.analysis_id && copy.permission === 'owner'"
      :to="`/profile/history/${copy.source.analysis_id}`"
      class="underline"
    >← Saved analysis</RouterLink>
    <RouterLink v-else-if="copy?.source.analysis_id" to="/shared" class="underline">← Shared with me</RouterLink>
    <RouterLink v-else-if="copy?.source.tablet" :to="`/tablets/${copy.source.tablet}`" class="underline">← {{ copy.source.tablet.replaceAll('-', ' ') }}</RouterLink>
    <div class="mt-4 flex flex-wrap items-center gap-4">
      <h1 class="text-3xl font-bold">{{ copy && !CAN_EDIT ? 'Corrected boxes' : 'Correct the boxes' }}</h1>
      <button v-if="CAN_SHARE" type="button" class="cursor-pointer rounded border border-ink/30 px-4 py-1.5 hover:bg-ink/5" :aria-expanded="SHARING" data-testid="share" @click="SHARING = !SHARING">
        Share<template v-if="copy.everyone !== 'none'"> · everyone logged in can {{ EVERYONE_TEXT[copy.everyone] }}</template>
      </button>
    </div>
    <p v-if="copy" class="mt-1 text-ink/70" data-testid="copy-owner">
      {{ copy.source.filename || copy.source.tablet.replaceAll('-', ' ') }} ·
      <template v-if="copy.title">“{{ copy.title }}” · </template>
      <template v-if="copy.permission === 'owner'">your {{ copy.kind === 'edition' ? 'edition' : 'corrected copy' }}</template>
      <template v-else>{{ copy.owner }}'s {{ copy.kind === 'edition' ? 'edition' : 'corrected copy' }}, shared with you: you {{ LEVEL_TEXT[copy.permission] }}</template><template v-if="copy.source.tablet && copy.kind !== 'edition'">, started from the {{ copy.start === 'scholar' ? "scholars'" : "model's" }} boxes</template>
    </p>
    <ReleasePanel
      v-if="copy?.kind === 'edition' && copy.source.tablet"
      :key="copy.id"
      :set-id="copy.id"
      :can-release="CAN_SHARE"
      :dirty="dirty"
      class="mt-4 max-w-xl"
      @released="copy.everyone = copy.everyone === 'none' ? 'view' : copy.everyone"
    />
    <p v-if="copy?.kind === 'edition' && copy.merged_from.length" class="mt-1 text-sm text-ink/70" data-testid="merged-from">
      Merged from {{ copy.merged_from.map(mergedName).join(', ') }}.
      <template v-if="copy.contributors.length">Contributors: {{ copy.contributors.join(', ') }}.</template>
    </p>
    <ShareDialog v-if="SHARING && copy" :set-id="copy.id" :is-owner="copy.permission === 'owner'" class="mt-4 max-w-xl" @close="SHARING = false" @changed="copy.everyone = $event.everyone" />

    <p v-if="loading" role="status" class="mt-6">Loading…</p>
    <p v-else-if="error && !copy" role="alert" class="mt-6">{{ error }}</p>

    <div v-if="copy" class="mt-6 flex flex-col gap-8 lg:flex-row">
      <section class="lg:w-3/5" aria-label="Tablet">
        <ShortcutHelp v-if="HELP" @close="HELP = false" />
        <div v-if="CAN_EDIT" class="mb-3 flex flex-wrap items-center gap-2" role="toolbar" aria-label="Editing tools">
          <button
            v-for="option in [{ value: 'select', label: 'Select and move' }, { value: 'draw', label: 'Draw a box' }]"
            :key="option.value"
            type="button"
            class="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-bar"
            :class="{ 'bg-bar font-semibold': MODE === option.value }"
            :aria-pressed="MODE === option.value"
            :disabled="LOCKED"
            :data-testid="`mode-${option.value}`"
            @click="MODE = option.value"
          >{{ option.label }}</button>
          <button
            type="button"
            class="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-bar"
            :class="{ 'bg-bar font-semibold': ORDERING }"
            :aria-pressed="Boolean(ORDERING)"
            :disabled="LOCKED"
            data-testid="mode-order"
            @click="ORDERING ? finishOrdering(false) : startOrdering()"
          >Reading order</button>
          <button type="button" class="cursor-pointer rounded px-2 py-1.5 text-sm hover:bg-bar" title="Keyboard shortcuts (?)" data-testid="shortcuts" @click="HELP = true">?</button>
          <button type="button" class="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-bar disabled:opacity-50" :disabled="!history.length || LOCKED" :title="history.length ? 'Undo your last unsaved edit (Ctrl+Z)' : 'Nothing to undo'" data-testid="undo" @click="set.undo()">Undo last edit</button>
          <span class="ml-auto text-sm" :class="dirty ? 'font-semibold' : 'text-ink/70'" role="status" data-testid="save-state">
            {{ dirty ? `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}` : 'All changes saved' }}
          </span>
          <button type="button" class="cursor-pointer rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5 disabled:opacity-50" :disabled="!dirty || saving" data-testid="discard" @click="discard">Discard</button>
          <button type="button" class="cursor-pointer rounded bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:brightness-95 disabled:opacity-50" :disabled="!dirty || saving" data-testid="save" title="Ctrl+S" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>

        <div v-if="ORDERING" class="mb-3 flex flex-wrap items-center gap-2 rounded-lg bg-card p-2 text-sm" role="status" data-testid="ordering">
          <span>Click the boxes in reading order: line {{ ORDERING.length }}, sign {{ ORDERING.at(-1).length + 1 }}.</span>
          <button type="button" class="cursor-pointer rounded border border-ink/30 px-2 py-0.5 hover:bg-bar" data-testid="order-new-line" @click="newLine">New line</button>
          <button type="button" class="cursor-pointer rounded bg-bar px-2 py-0.5 font-semibold" data-testid="order-done" @click="finishOrdering(true)">Done</button>
          <button type="button" class="cursor-pointer underline" data-testid="order-automatic" @click="ORDERING = [[]]; finishOrdering(true)">Use the automatic order</button>
          <button type="button" class="cursor-pointer underline" @click="finishOrdering(false)">Cancel</button>
        </div>
        <p v-if="IMAGE_MISSING" role="alert" class="rounded-lg bg-card p-4">The tablet image could not be loaded.</p>
        <ZoomFrame v-else ref="ZOOMER">
        <BoxEditor
          ref="EDITOR"
          :badges="ORDERING ? ORDER_BADGES : BADGES"
          :image-url="`/api${copy.image_url}`"
          :alt="copy.source.filename || 'Tablet'"
          :boxes="boxes"
          :roles="READ"
          :markers="MARKERS"
          :selected-id="SELECTED_ID"
          :mode="MODE"
          :read-only="LOCKED"
          :ghost="GHOST"
          :name="signName"
          @select="chooseBox"
          @begin="set.beginGesture()"
          @place="set.place"
          @end="set.endGesture()"
          @draw="draw"
          @remove="remove"
          @nudge="set.setBox"
          @image-error="IMAGE_MISSING = true"
        />
        </ZoomFrame>
        <p v-if="!CAN_EDIT" class="mt-2 text-sm text-ink/70" data-testid="read-only">
          You can look at these boxes but not change them. Click a box to see its sign.
        </p>
        <p v-else class="mt-2 text-sm text-ink/70">
          Drag a box to move it and its corners to resize it. In <em>Draw a box</em> mode, drag on the tablet.
          Dashed boxes differ from where this copy started; boxes you drew or renamed stay grey until you save.
          Arrow keys move the selected box, Shift with arrows resizes it, Delete removes it, Ctrl+Z undoes your last edit.
        </p>
      </section>

      <aside class="flex flex-col gap-6 lg:flex-1">
        <div v-if="conflict" role="alert" class="rounded-2xl border border-confidence-low p-4" data-testid="conflict">
          <p>{{ error }}</p>
          <button type="button" class="mt-2 cursor-pointer underline" @click="set.takeNewer(); SELECTED_ID = null">Load the latest saved version (your unsaved changes will be lost)</button>
        </div>
        <p v-else-if="error" role="alert" class="text-confidence-low">{{ error }}</p>
        <p v-if="NOTICE && !dirty" role="status" class="rounded-lg bg-accent/10 p-3">{{ NOTICE }}</p>

        <section class="rounded-3xl bg-card p-5" aria-labelledby="selected-h" data-testid="selected-panel">
          <h2 id="selected-h" class="text-xl font-bold">Selected box</h2>
          <p v-if="!SELECTED" class="mt-2 text-ink/70">Click a box on the tablet, or one in the list below.</p>
          <template v-else>
            <p class="mt-2 text-lg">
              <SignPreview v-if="SELECTED.sign" :sign="SELECTED.sign" :glyph="glyphOf(SELECTED.sign)" :preview-url="GLYPHS[SELECTED.sign]?.preview_url ?? null" :size="48" class="mr-2 align-middle" />
              <span class="linear-a mr-2 text-3xl" aria-hidden="true">{{ glyphOf(SELECTED.sign) }}</span>
              <span class="font-semibold" data-testid="selected-sign">{{ signName(SELECTED.sign) }}</span>
            </p>
            <p v-if="SELECTED.model_sign && SELECTED.model_sign !== SELECTED.sign" class="text-sm text-ink/70">
              The model read {{ signName(SELECTED.model_sign) }}<template v-if="SELECTED.model_confidence"> ({{ Math.round(SELECTED.model_confidence) }}%)</template>.
            </p>
            <p v-else-if="SELECTED.origin === 'user' || SELECTED.id < 0" class="text-sm text-ink/70">Drawn by hand.</p>
            <p v-if="copy.kind === 'edition' && (SELECTED.source?.kind === 'scholar' || SELECTED.source?.kind === 'model')" class="text-sm text-ink/70" data-testid="box-source">
              From the {{ SELECTED.source.kind === 'scholar' ? "scholars'" : "model's" }} boxes.
            </p>
            <p v-else-if="SELECTED.source?.kind === 'copy'" class="text-sm text-ink/70" data-testid="box-source">
              From {{ SELECTED.source.author ?? 'a' }}'s copy<template v-if="SELECTED.source.version != null"> (version {{ SELECTED.source.version }})</template>.
            </p>

            <template v-if="CAN_EDIT">
            <SignPicker :selected="SELECTED.sign" :candidates="SELECTED.candidates ?? []" @pick="pick" />

            <div class="mt-4 flex flex-wrap gap-3">
              <button v-if="SELECTED.sign" type="button" class="cursor-pointer text-sm underline" data-testid="clear-sign" @click="pick(null)">Clear the sign</button>
              <button type="button" class="cursor-pointer text-sm text-confidence-low underline" data-testid="delete-box" @click="remove(SELECTED.id)">Delete this box</button>
            </div>
            </template>
            <MarksPanel :box="SELECTED" :disabled="!CAN_EDIT || LOCKED" @update="(marks) => set.setMarks(SELECTED.id, marks)" />
            <DiscussionLinks
              v-if="copy.source.tablet && positionOf(SELECTED) != null"
              :target="`glyph:${copy.source.tablet}:${positionOf(SELECTED)}`"
              :label="`${copy.source.tablet.replaceAll('-', ' ')} · ${signName(SELECTED.sign)}`"
            />
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
        <BoxComments
          :set-id="copy.id"
          :box-id="SELECTED_ID"
          :box-name="SELECTED ? (SELECTED.sign ? signName(SELECTED.sign) : 'this box with no sign') : ''"
          :can-comment="CAN_COMMENT"
        />
        <HistoryPanel
          :set-id="copy.id"
          :version="copy.version"
          :can-revert="CAN_EDIT"
          :unsaved="dirty || saving"
          :selected-box-id="SELECTED_ID"
          :name="signName"
          @select="showChange"
          @reverted="reverted"
          @conflict="set.showConflict"
          @busy="HISTORY_BUSY = $event"
        />
      </aside>
    </div>

    <section v-if="copy" class="mt-10" aria-labelledby="reading-h">
      <h2 id="reading-h" class="text-2xl font-bold">Reading of the saved boxes</h2>
      <p class="mt-1 text-ink/70">{{ dirty ? 'Save to update the reading with your latest changes.' : copy.reading.summary }}</p>
      <p class="mt-2"><span class="text-ink/70">Transliteration:</span> {{ copy.reading.symbol_interpretation }}</p>
      <FractionCheck :analysis="READING" class="mt-6" />
      <p v-if="CAN_EDIT" class="mt-8 text-sm text-ink/70" data-testid="training-note">
        Corrected boxes may be used to train the sign reader. Admins export them with an account number, not a name.
      </p>
    </section>
  </main>
</template>
