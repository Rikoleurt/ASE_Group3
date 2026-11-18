<script setup>
// The change history of a corrected copy (#86): every saved change, newest first, grouped
// by save. Selecting a change shows its box on the tablet (where it is now, and where it
// was before, as a ghost); people who can edit can undo it.
import { computed, ref, watch } from 'vue'
import { sessionFetch } from '../../state/session'

const props = defineProps({
  setId: { type: Number, required: true },
  version: { type: Number, required: true }, // reloads when the copy changes
  canRevert: { type: Boolean, default: false },
  unsaved: { type: Boolean, default: false }, // undo saves at once, so unsaved edits must go first
  selectedBoxId: { type: Number, default: null },
  name: { type: Function, default: (sign) => sign ?? 'an unnamed box' },
})
const emit = defineEmits(['select', 'reverted'])

const PAGE = 50
const CHANGES = ref([])
const NEXT = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
const ACTIVE = ref(null)
const AUTHOR = ref('') // filter: '' for everyone
const ONLY_BOX = ref(false)
const BUSY = ref(false)

const AUTHORS = computed(() => [...new Map(CHANGES.value.map((c) => [c.author.id, c.author.username ?? 'Deleted account'])).entries()])
const SHOWN = computed(() => CHANGES.value.filter((change) =>
  (!AUTHOR.value || String(change.author.id) === AUTHOR.value) &&
  (!ONLY_BOX.value || change.box_id === props.selectedBoxId)))
// One group per save (a version), newest first.
const SAVES = computed(() => {
  const groups = []
  for (const change of SHOWN.value) {
    const last = groups[groups.length - 1]
    if (last && last.version === change.version) last.changes.push(change)
    else groups.push({ version: change.version, author: change.author, created_at: change.created_at, changes: [change] })
  }
  return groups
})

const moved = (a, b) => Math.abs(a.x - b.x) > 1e-9 || Math.abs(a.y - b.y) > 1e-9
const resized = (a, b) => Math.abs(a.w - b.w) > 1e-9 || Math.abs(a.h - b.h) > 1e-9

/** One line describing a change, e.g. "Renamed AB81 (ku) to AB02 (ro) and moved it". */
function describe(change) {
  const { before, after } = change
  if (change.action === 'add') return `Drew a box${after.sign ? ` named ${props.name(after.sign)}` : ''}`
  if (change.action === 'delete') return `Deleted ${props.name(before.sign)}`
  if (change.action === 'revert') return `Undid change ${change.reverts}${after.deleted ? ', removing the box' : before?.deleted ? ', bringing the box back' : ''}`
  const parts = []
  if (before.sign !== after.sign) parts.push(after.sign ? `Renamed ${props.name(before.sign)} to ${props.name(after.sign)}` : `Cleared the sign of ${props.name(before.sign)}`)
  const geometry = [moved(before.box, after.box) && 'moved', resized(before.box, after.box) && 'resized'].filter(Boolean).join(' and ')
  if (geometry) parts.push(parts.length ? `${geometry} it` : `${geometry[0].toUpperCase()}${geometry.slice(1)} ${props.name(after.sign)}`)
  return parts.join(' and ')
}

const when = (stamp) => new Date(stamp).toLocaleString()

async function load(more = false) {
  LOADING.value = true
  ERROR.value = ''
  try {
    const query = new URLSearchParams({ limit: PAGE, ...(more && NEXT.value ? { before: NEXT.value } : {}) })
    const response = await sessionFetch(`/api/box-sets/${props.setId}/changes?${query}`)
    if (!response.ok) throw new Error('The history could not be loaded.')
    const page = await response.json()
    CHANGES.value = more ? [...CHANGES.value, ...page.items] : page.items
    NEXT.value = page.next_before
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
  } finally {
    LOADING.value = false
  }
}

function select(change) {
  ACTIVE.value = ACTIVE.value === change.id ? null : change.id
  emit('select', ACTIVE.value ? change : null)
}

async function revert(change) {
  BUSY.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/box-sets/${props.setId}/changes/${change.id}/revert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: props.version }),
    })
    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The change could not be undone.')
    ACTIVE.value = null
    emit('select', null)
    emit('reverted', body)
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
  } finally {
    BUSY.value = false
  }
}

watch(() => [props.setId, props.version], () => load(), { immediate: true })
</script>

<template>
  <section class="rounded-3xl bg-card p-5" aria-labelledby="history-h" data-testid="history-panel">
    <h2 id="history-h" class="text-xl font-bold">History</h2>
    <div class="mt-2 flex flex-wrap items-center gap-3 text-sm">
      <label>Who
        <select v-model="AUTHOR" class="ml-1 rounded border border-ink/30 px-1" data-testid="history-author">
          <option value="">Everyone</option>
          <option v-for="[id, username] in AUTHORS" :key="id" :value="String(id)">{{ username }}</option>
        </select>
      </label>
      <label><input v-model="ONLY_BOX" type="checkbox" :disabled="selectedBoxId === null" data-testid="history-only-box" /> Only the selected box</label>
    </div>
    <p v-if="ERROR" role="alert" class="mt-2 text-confidence-low">{{ ERROR }}</p>
    <p v-if="unsaved && canRevert" class="mt-2 text-sm text-ink/70">Save or discard your changes to undo saved ones.</p>
    <p v-if="!LOADING && !SAVES.length" class="mt-2 text-ink/70">{{ CHANGES.length ? 'No changes match.' : 'No changes saved yet.' }}</p>
    <ol class="mt-2 max-h-96 overflow-auto">
      <li v-for="save in SAVES" :key="save.version" class="border-t border-ink/10 py-2 first:border-0" data-testid="history-save">
        <p class="text-sm text-ink/70">{{ save.author.username ?? 'Deleted account' }} · <time :datetime="save.created_at">{{ when(save.created_at) }}</time></p>
        <ul>
          <li v-for="change in save.changes" :key="change.id" class="flex items-center gap-2">
            <button
              type="button"
              class="flex-1 cursor-pointer rounded px-1 text-left hover:bg-bar"
              :class="{ 'bg-bar font-semibold': ACTIVE === change.id, 'text-ink/50 line-through': change.reverted_by }"
              :aria-pressed="ACTIVE === change.id"
              data-testid="history-change"
              @click="select(change)"
            >{{ describe(change) }}</button>
            <button
              v-if="canRevert && !change.reverted_by"
              type="button"
              class="cursor-pointer text-sm underline disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="BUSY || unsaved"
              data-testid="history-undo"
              @click="revert(change)"
            >Undo</button>
          </li>
        </ul>
      </li>
    </ol>
    <button v-if="NEXT" type="button" class="mt-2 cursor-pointer underline" :disabled="LOADING" @click="load(true)">Older changes</button>
  </section>
</template>
