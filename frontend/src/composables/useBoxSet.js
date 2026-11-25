// A corrected copy being edited (#85): the copy as saved, the boxes as the user has them
// now, an undo stack, and saving the difference as one batch (#83's PATCH).
import { computed, ref } from 'vue'
import { sessionFetch } from '../state/session'

const GEOMETRY = ['x', 'y', 'w', 'h']
const TOLERANCE = 1e-9
export const MIN_SIDE = 0.002 // the API's smallest box side, as a fraction of the image

const sameBox = (a, b) => GEOMETRY.every((key) => Math.abs(a[key] - b[key]) <= TOLERANCE)

/** Keep a box inside the image and at least MIN_SIDE on each side. */
export function clampBox({ x, y, w, h }) {
  const width = Math.min(Math.max(w, MIN_SIDE), 1)
  const height = Math.min(Math.max(h, MIN_SIDE), 1)
  return {
    x: Math.min(Math.max(x, 0), 1 - width),
    y: Math.min(Math.max(y, 0), 1 - height),
    w: width,
    h: height,
  }
}

// A box's epigraphic marks (workbench, story F), as the API gives them when none are set.
export const NO_MARKS = Object.freeze({ certainty: 'certain', damage: 'none', alternatives: [], word_end: false, line: null, seq: null })
export const marksOf = (box) => ({ ...NO_MARKS, ...(box?.marks ?? {}), alternatives: [...(box?.marks?.alternatives ?? [])] })
const sameMarks = (a, b) => JSON.stringify(marksOf(a)) === JSON.stringify(marksOf(b))

/**
 * The changes that turn the saved boxes into the working ones, in the API's shape.
 * Boxes the user drew have negative ids until they are saved.
 */
export function diff(saved, working) {
  const now = new Map(working.map((box) => [box.id, box]))
  const changes = []
  for (const before of saved) {
    const after = now.get(before.id)
    if (!after) {
      changes.push({ op: 'delete', box_id: before.id })
      continue
    }
    const change = { op: 'update', box_id: before.id }
    if (!sameBox(before.box, after.box)) change.box = { ...after.box }
    if (before.sign !== after.sign) change.sign = after.sign
    if (!sameMarks(before, after)) change.marks = marksOf(after)
    if ('box' in change || 'sign' in change || 'marks' in change) changes.push(change)
  }
  for (const box of working) {
    if (box.id < 0) changes.push({ op: 'add', box: { ...box.box }, sign: box.sign, ...(sameMarks(box, {}) ? {} : { marks: marksOf(box) }) })
  }
  return changes
}

const copyBoxes = (boxes) => boxes.map((box) => ({ ...box, box: { ...box.box }, marks: marksOf(box) }))
const sameBoxes = (a, b) =>
  a.length === b.length &&
  a.every((box, index) => box.id === b[index].id && box.sign === b[index].sign && sameBox(box.box, b[index].box) && sameMarks(box, b[index]))

/** Open (or make, the first time) your corrected copy of an analysis; resolves to its id. */
export async function openCopy(analysisId) {
  const response = await sessionFetch('/api/box-sets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw Object.assign(new Error(typeof body?.detail === 'string' ? body.detail : 'The boxes could not be opened for editing.'), { status: response.status })
  }
  return (await response.json()).id
}

export function useBoxSet() {
  const copy = ref(null) // the copy as the server last returned it
  const boxes = ref([]) // the boxes as the user has them now
  const history = ref([]) // earlier states of `boxes`, for undo
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const conflict = ref(null) // the newer copy the server sent with a 409
  let nextId = -1

  const changes = computed(() => (copy.value ? diff(copy.value.boxes, boxes.value) : []))
  const dirty = computed(() => changes.value.length > 0)

  function accept(body) {
    copy.value = body
    boxes.value = copyBoxes(body.boxes)
    history.value = []
    conflict.value = null
  }

  async function failure(response, fallback) {
    const body = await response.json().catch(() => null)
    return typeof body?.detail === 'string' ? body.detail : fallback
  }

  async function load(id) {
    loading.value = true
    error.value = ''
    try {
      const response = await sessionFetch(`/api/box-sets/${encodeURIComponent(id)}`)
      if (!response.ok) {
        const message = response.status === 404 ? 'This corrected copy was not found.' : 'The copy could not be loaded. Please try again.'
        throw Object.assign(new Error(message), { status: response.status })
      }
      accept(await response.json())
    } catch (failed) {
      error.value = failed instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failed.message
      if (failed.status === 401) throw failed
    } finally {
      loading.value = false
    }
  }

  /** Change the working boxes; `edit` gets a copy to change and the undo stack keeps the old one. */
  function change(edit) {
    history.value = [...history.value, copyBoxes(boxes.value)].slice(-100)
    const next = copyBoxes(boxes.value)
    edit(next)
    boxes.value = next
  }

  // A drag is one undo step: snapshot when it starts, move freely, forget the snapshot if nothing moved.
  function beginGesture() {
    history.value = [...history.value, copyBoxes(boxes.value)].slice(-100)
  }

  function place(id, box) {
    const found = boxes.value.find((item) => item.id === id)
    if (found) found.box = clampBox(box)
  }

  function endGesture() {
    const before = history.value[history.value.length - 1]
    if (before && sameBoxes(before, boxes.value)) history.value = history.value.slice(0, -1)
  }

  function undo() {
    if (!history.value.length) return
    boxes.value = history.value[history.value.length - 1]
    history.value = history.value.slice(0, -1)
  }

  function discard() {
    if (copy.value) accept(copy.value)
  }

  function addBox(box, sign = null) {
    const id = nextId--
    change((next) => next.push({ id, box: clampBox(box), sign, origin: 'user', model_sign: null, model_confidence: null, candidates: [], changed: true }))
    return id
  }

  function setBox(id, box) {
    change((next) => {
      const found = next.find((item) => item.id === id)
      if (found) found.box = clampBox(box)
    })
  }

  function setSign(id, sign) {
    change((next) => {
      const found = next.find((item) => item.id === id)
      if (found) found.sign = sign
    })
  }

  // Change some of a box's marks; `marks` holds only the fields to change.
  function setMarks(id, marks) {
    change((next) => {
      const found = next.find((item) => item.id === id)
      if (found) found.marks = { ...marksOf(found), ...marks }
    })
  }

  // The reading order set by hand: `lines` is a list of lines, each a list of box ids in order.
  // Boxes left out go back to the automatic order.
  function setOrder(lines) {
    change((next) => {
      const place = new Map(lines.flatMap((ids, line) => ids.map((id, seq) => [id, { line, seq }])))
      for (const box of next) box.marks = { ...marksOf(box), line: null, seq: null, ...(place.get(box.id) ?? {}) }
    })
  }

  function removeBox(id) {
    change((next) => {
      const index = next.findIndex((item) => item.id === id)
      if (index >= 0) next.splice(index, 1)
    })
  }

  async function save() {
    if (!dirty.value || saving.value) return false
    saving.value = true
    error.value = ''
    try {
      const response = await sessionFetch(`/api/box-sets/${copy.value.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: copy.value.version, changes: changes.value }),
      })
      if (response.status === 409) {
        const body = await response.json()
        conflict.value = body.current
        error.value = body.detail
        return false
      }
      if (!response.ok) throw new Error(await failure(response, 'Your changes could not be saved. Please try again.'))
      accept(await response.json())
      return true
    } catch (failed) {
      error.value = failed instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failed.message
      return false
    } finally {
      saving.value = false
    }
  }

  /** A 409 from elsewhere (the history's undo): offer the newer copy it carries. */
  function showConflict(body) {
    conflict.value = body.current
    error.value = body.detail
  }

  /** After a 409: drop this tab's unsaved changes and take the newer copy. */
  function takeNewer() {
    if (conflict.value) accept(conflict.value)
    error.value = ''
  }

  return { copy, boxes, history, loading, saving, error, conflict, changes, dirty, load, accept, addBox, setBox, setSign, removeBox, beginGesture, place, endGesture, undo, discard, save, takeNewer, showConflict, setMarks, setOrder }
}
