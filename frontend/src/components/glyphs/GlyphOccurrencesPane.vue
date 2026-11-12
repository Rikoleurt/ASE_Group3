<script setup>
// Every corpus tablet that has the selected sign, in a strip you scroll sideways.
// "Same sign" means the same SigLA sign ID. The reader can be wrong, so there is one
// tab for each of its top three guesses. Cards are ordered by how much each corpus
// glyph looks like the one you picked, and ones far from their sign's usual look are
// flagged. Tick occurrences and write one comment that is saved against all of them.
//
// `selection`: { sign, candidates?: [{ sign, label, probability }], crop?: PNG data URL,
// reference?: { tablet, position } }. Nothing is fetched until a selection arrives.
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { loadSession, sessionFetch, sessionUser } from '../../state/session'
import '../analysis/linearA.css'

const props = defineProps({
  selection: { type: Object, default: null },
})

const PAGE = 30
const MAX_COMMENT = 2000

const tabs = computed(() => {
  const sel = props.selection
  if (!sel?.sign) return []
  const seen = new Set()
  const list = []
  const given = sel.candidates ?? []
  // The sign the reader chose always comes first, with its own probability when it has one.
  const chosen = given.find((candidate) => candidate.sign === sel.sign) ?? { sign: sel.sign }
  for (const candidate of [chosen, ...given]) {
    if (!candidate.sign || seen.has(candidate.sign) || list.length === 3) continue
    seen.add(candidate.sign)
    // The reader's label is often already "AB45 (de)"; only add the sign ID when it is missing.
    const name = candidate.label && candidate.label !== candidate.sign ? candidate.label : ''
    const label = !name ? candidate.sign : name.startsWith(candidate.sign) ? name : `${candidate.sign} (${name})`
    list.push({ sign: candidate.sign, label, probability: candidate.probability })
  }
  return list
})

// Probabilities are percentages; a small one is not zero, so say so.
function percent(value) {
  if (value > 0 && value < 0.5) return '<1%'
  return `${Math.round(value)}%`
}

const active = ref('')
// Sign ID -> its Unicode Linear A character (null where Unicode has none). Sign IDs only:
// nothing that names a tablet gets a character. A failed lookup just leaves them off.
const characters = ref({})
const activeTab = computed(() => tabs.value.find((tab) => tab.sign === active.value) ?? null)
const activeCharacter = computed(() => characters.value[active.value] ?? null)
const charactersKnown = computed(() => active.value in characters.value)
// What was clicked: the crop of the box, or, for a corpus reference, that glyph's own drawing.
const clickedImage = computed(() => {
  const sel = props.selection
  if (sel?.crop?.startsWith?.('data:')) return sel.crop
  return sel?.reference ? `/api/tablets/${sel.reference.tablet}/signs/${sel.reference.position}.png` : null
})

async function loadCharacters(selection) {
  characters.value = {}
  const signs = tabs.value.map((tab) => tab.sign)
  if (!signs.length) return
  try {
    const response = await fetch(`/api/glyphs/characters?signs=${signs.join(',')}`)
    if (!response.ok) return
    const data = await response.json()
    if (props.selection === selection) characters.value = data
  } catch {
    // The characters are decoration: no banner.
  }
}
const items = ref([])
const total = ref(0)
const rankedBy = ref('none')
const credit = ref(null)
const loading = ref(false)
const loadError = ref('')
const missing = ref(false)
const ticked = ref(new Set())
const body = ref('')
const posting = ref(false)
const postError = ref('')
const notice = ref('')
const comments = ref([])
const commentsError = ref('')
const commentsMore = ref(null)
let generation = 0
let commentsGeneration = 0
const root = ref(null)

// The page the reader is on, so logging in brings them back to it.
const loginTarget = computed(() => ({ path: '/login', query: { redirect: `${window.location.pathname}${window.location.search}` } }))
const key = (item) => `${item.tablet}#${item.position}`
const trimmed = computed(() => body.value.trim())
const tickedItems = computed(() => items.value.filter((item) => ticked.value.has(key(item))))
const canSubmit = computed(() => tickedItems.value.length > 0 && trimmed.value.length > 0 && trimmed.value.length <= MAX_COMMENT && !posting.value)

function dataUrlToBlob(url) {
  const unusable = new Error('The selected glyph image cannot be used for the comparison.')
  if (typeof url !== 'string' || !url.startsWith('data:')) throw unusable
  const [head, data] = url.split(',')
  try {
    const bytes = Uint8Array.from(atob(data), (char) => char.charCodeAt(0))
    return new Blob([bytes], { type: /^data:([^;]+)/.exec(head)?.[1] ?? 'image/png' })
  } catch {
    throw unusable
  }
}

async function readError(response) {
  const data = await response.json().catch(() => null)
  return typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}).`
}

async function loadOccurrences(offset = 0) {
  const sign = active.value
  if (!sign) return
  const mine = ++generation
  loading.value = true
  loadError.value = ''
  if (offset === 0) {
    items.value = []
    total.value = 0
    missing.value = false
  }
  try {
    const sel = props.selection
    let response
    // Comparing with a crop costs server inference, so it needs a login; anyone else gets
    // the reference glyph's order, or corpus order.
    if (sel.crop && sessionUser.value) {
      // The crop is embedded on the server; it is not stored.
      const form = new FormData()
      form.append('file', dataUrlToBlob(sel.crop), 'crop.png')
      form.append('limit', String(PAGE))
      form.append('offset', String(offset))
      try {
        response = await sessionFetch(`/api/glyphs/${sign}/occurrences/search`, { method: 'POST', body: form })
      } catch (failure) {
        if (failure.status !== 401) throw failure // an expired session: sessionFetch refreshes it before a write
      }
    }
    if (!response || response.status === 401 || response.status === 403) {
      // Logged out (or the session lapsed): fall back to the reference or corpus order.
      const query = new URLSearchParams({ limit: String(PAGE), offset: String(offset) })
      if (sel.reference) {
        query.set('ref_tablet', sel.reference.tablet)
        query.set('ref_position', String(sel.reference.position))
      }
      response = await fetch(`/api/glyphs/${sign}/occurrences?${query}`)
    }
    if (mine !== generation) return
    if (response.status === 404) {
      missing.value = true
      return
    }
    if (!response.ok) throw new Error(await readError(response))
    const page = await response.json()
    if (mine !== generation) return
    items.value = offset === 0 ? page.items : [...items.value, ...page.items]
    total.value = page.total
    rankedBy.value = page.ranked_by
    credit.value = page.credit
    const next = new Set(offset === 0 ? [] : ticked.value)
    for (const item of page.items) next.add(key(item)) // every occurrence starts ticked
    ticked.value = next
  } catch (failure) {
    if (mine !== generation) return
    loadError.value = failure instanceof TypeError ? 'Unable to reach the server. Check your connection and try again.' : failure.message
  } finally {
    if (mine === generation) loading.value = false
  }
}

async function loadComments(before = null) {
  const sign = active.value
  if (!sign) return
  const mine = ++commentsGeneration
  commentsError.value = ''
  try {
    const response = await fetch(`/api/glyphs/${sign}/annotations${before ? `?before=${before}` : ''}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await readError(response))
    const page = await response.json()
    if (mine !== commentsGeneration) return
    comments.value = before ? [...comments.value, ...page.items] : page.items
    commentsMore.value = page.next_before
  } catch (failure) {
    if (mine !== commentsGeneration) return
    commentsError.value = failure instanceof TypeError ? 'Comments could not be loaded.' : failure.message
  }
}

function openTab(sign) {
  if (sign === active.value) return
  active.value = sign
  notice.value = postError.value = ''
  loadOccurrences()
  comments.value = []
  commentsMore.value = null
  loadComments()
}

function moveTab(event, index) {
  const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!step) return
  event.preventDefault()
  const next = tabs.value[(index + step + tabs.value.length) % tabs.value.length]
  openTab(next.sign)
  document.getElementById(`glyph-tab-${next.sign}`)?.focus()
}

watch(
  () => props.selection,
  async (selection) => {
    generation++ // answers still on their way belong to the previous selection
    commentsGeneration++
    active.value = ''
    items.value = []
    comments.value = []
    commentsMore.value = null
    loading.value = false
    loadError.value = commentsError.value = ''
    missing.value = false
    notice.value = postError.value = ''
    characters.value = {}
    if (!selection?.sign) return
    loadCharacters(selection)
    // Know whether the reader is logged in before choosing how to order the occurrences.
    if (!sessionUser.value) await loadSession().catch(() => {})
    if (props.selection !== selection) return
    openTab(tabs.value[0].sign)
    nextTick(() => root.value?.scrollIntoView?.({ block: 'nearest' }))
  },
  { immediate: true },
)

function toggle(item) {
  const next = new Set(ticked.value)
  if (!next.delete(key(item))) next.add(key(item))
  ticked.value = next
}

const selectAll = () => (ticked.value = new Set(items.value.map(key)))
const selectNone = () => (ticked.value = new Set())

async function submit() {
  if (!canSubmit.value) return
  posting.value = true
  postError.value = notice.value = ''
  const count = tickedItems.value.length
  const sign = active.value
  try {
    const response = await sessionFetch(`/api/glyphs/${sign}/annotations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        body: trimmed.value,
        targets: tickedItems.value.map((item) => ({ tablet: item.tablet, position: item.position })),
      }),
    })
    if (response.status === 401) {
      postError.value = 'Please log in to comment.'
      return
    }
    if (!response.ok) throw new Error(await readError(response))
    const saved = await response.json()
    body.value = ''
    // Only show it where it belongs: the tabs are locked while posting, but never trust that.
    if (sign === active.value) comments.value = [saved, ...comments.value]
    notice.value = `Saved on ${count} occurrence${count === 1 ? '' : 's'}.`
  } catch (failure) {
    postError.value = failure.status === 401 ? 'Please log in to comment.' : failure instanceof TypeError ? 'Unable to reach the server. Your comment was not saved.' : failure.message
  } finally {
    posting.value = false
  }
}

async function remove(comment) {
  postError.value = notice.value = ''
  try {
    const response = await sessionFetch(`/api/glyphs/annotations/${comment.id}`, { method: 'DELETE' })
    if (!response.ok && response.status !== 404) throw new Error(await readError(response))
    comments.value = comments.value.filter((other) => other.id !== comment.id)
  } catch (failure) {
    postError.value = failure instanceof TypeError ? 'Unable to reach the server. The comment was not deleted.' : failure.message
  }
}

// The selected sign's reading (e.g. "de"), from the reader's label "AB45 (de)".
const reading = computed(() => /\((.+)\)$/.exec(activeTab.value?.label ?? '')?.[1] ?? null)
const apiUrl = (url) => `/api${url}`
const when = (iso) => new Date(iso).toISOString().slice(0, 10)
</script>

<template>
  <section v-if="tabs.length" ref="root" class="rounded-3xl bg-card p-4 sm:p-6" aria-labelledby="glyph-pane-title" data-testid="glyph-pane">
    <h2 id="glyph-pane-title" class="text-xl font-bold">Other tablets with this sign</h2>

    <div
      v-if="active"
      class="mt-3 flex flex-wrap items-center gap-4 rounded-xl bg-page p-3"
      data-testid="glyph-selected"
      aria-labelledby="glyph-selected-title"
    >
      <h3 id="glyph-selected-title" class="sr-only">Selected glyph</h3>
      <div class="flex h-24 w-24 shrink-0 items-center justify-center rounded bg-white">
        <img v-if="clickedImage" :src="clickedImage" :alt="`The glyph you selected, read as ${active}`" class="max-h-full max-w-full" data-testid="glyph-selected-crop" />
        <span v-else class="px-1 text-center text-xs text-ink/70">No image of the glyph</span>
      </div>
      <div
        v-if="activeCharacter"
        class="linear-a flex h-24 w-24 shrink-0 items-center justify-center rounded bg-white text-7xl"
        role="img"
        :aria-label="`Unicode character for ${active}`"
        data-testid="glyph-selected-character"
      >
        {{ activeCharacter }}
      </div>
      <div class="min-w-0">
        <p class="text-lg font-bold" data-testid="glyph-selected-sign">{{ active }}<span v-if="reading" class="font-normal"> ({{ reading }})</span></p>
        <p v-if="activeTab?.probability !== undefined" class="text-sm">The reader's confidence: {{ percent(activeTab.probability) }}</p>
        <p v-if="charactersKnown && !activeCharacter" class="text-sm text-ink/70" data-testid="glyph-selected-no-character">This sign has no Unicode character.</p>
      </div>
    </div>

    <div role="tablist" aria-label="The reader's best guesses for this sign" class="mt-3 flex flex-wrap gap-2">
      <button
        v-for="(tab, index) in tabs"
        :id="`glyph-tab-${tab.sign}`"
        :key="tab.sign"
        type="button"
        role="tab"
        data-testid="glyph-tab"
        :aria-selected="tab.sign === active"
        :aria-label="characters[tab.sign] ? `${tab.label}${tab.probability !== undefined ? `, ${percent(tab.probability)}` : ''}` : undefined"
        :disabled="posting"
        :tabindex="tab.sign === active ? 0 : -1"
        class="cursor-pointer rounded px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        :class="tab.sign === active ? 'bg-ink text-page' : 'bg-bar hover:brightness-95'"
        @click="openTab(tab.sign)"
        @keydown="moveTab($event, index)"
      >
        <span v-if="characters[tab.sign]" class="linear-a mr-1 text-lg align-middle" aria-hidden="true" data-testid="glyph-tab-character">{{ characters[tab.sign] }}</span>{{ tab.label }}<span v-if="tab.probability !== undefined"> · {{ percent(tab.probability) }}</span>
      </button>
    </div>
    <p v-if="tabs.length > 1" class="mt-1 text-sm text-ink/70">The reader can be wrong: check its other guesses too.</p>

    <p v-if="loading && !items.length" role="status" class="mt-4">Loading tablets…</p>
    <div v-if="loadError" role="alert" class="mt-4 text-confidence-low">
      {{ loadError }}
      <button type="button" class="ml-2 cursor-pointer underline" @click="loadOccurrences()">Try again</button>
    </div>
    <p v-else-if="missing" class="mt-4">No corpus tablet has {{ active }}.</p>

    <template v-if="items.length">
      <div class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <p data-testid="glyph-count">
          {{ total }} occurrence{{ total === 1 ? '' : 's' }} of {{ active }},
          {{ rankedBy === 'glyph' ? 'most similar to your glyph first' : rankedBy === 'centre' ? 'most typical first' : 'in corpus order' }}
        </p>
        <button type="button" class="cursor-pointer underline" @click="selectAll">Select all</button>
        <button type="button" class="cursor-pointer underline" @click="selectNone">Select none</button>
      </div>

      <ul
        class="mt-3 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3"
        aria-label="Occurrences, scroll sideways"
        tabindex="0"
        data-testid="glyph-strip"
      >
        <li
          v-for="item in items"
          :key="key(item)"
          class="w-52 shrink-0 snap-start rounded-xl bg-page p-2 text-sm"
          data-testid="glyph-card"
        >
          <label class="flex cursor-pointer items-center gap-2 font-bold">
            <input
              type="checkbox"
              class="h-5 w-5 accent-accent"
              :checked="ticked.has(key(item))"
              :aria-label="`Include ${item.title}, position ${item.position}`"
              @change="toggle(item)"
            />
            {{ item.title }} <span class="font-normal text-ink/70">#{{ item.position }}</span>
          </label>
          <div class="mt-2 flex h-24 items-center justify-center rounded bg-white">
            <img
              v-if="item.crop_url"
              :src="apiUrl(item.crop_url)"
              :alt="`${item.sign} as drawn on ${item.title}`"
              loading="lazy"
              decoding="async"
              class="max-h-full max-w-full"
            />
            <span v-else class="px-2 text-center text-ink/70">No drawing of this sign</span>
          </div>
          <img
            :src="apiUrl(item.thumbnail_url)"
            :alt="`${item.title}, with the sign outlined`"
            loading="lazy"
            decoding="async"
            class="mt-2 h-32 w-full rounded bg-white object-contain"
          />
          <p class="mt-2">
            <span v-if="item.similarity !== null">Similarity {{ item.similarity.toFixed(2) }}</span>
            <span v-else class="text-ink/70">Similarity unavailable</span>
            <span v-if="item.reading" class="text-ink/70"> · {{ item.reading }}</span>
          </p>
          <p
            v-if="item.outlier"
            class="mt-1 inline-block rounded bg-confidence-low px-2 py-0.5 text-xs font-bold text-white"
            data-testid="outlier-badge"
          >
            Possible mislabel
          </p>
        </li>
        <li v-if="items.length < total" class="flex w-40 shrink-0 snap-start items-center justify-center">
          <button type="button" class="cursor-pointer rounded bg-bar px-4 py-2 font-medium hover:brightness-95" :disabled="loading" @click="loadOccurrences(items.length)">
            {{ loading ? 'Loading…' : `Load more (${total - items.length})` }}
          </button>
        </li>
      </ul>

      <form class="mt-4 flex flex-col gap-2" data-testid="glyph-comment-form" @submit.prevent="submit">
        <template v-if="sessionUser">
          <label for="glyph-comment" class="font-bold">Your comment</label>
          <textarea
            id="glyph-comment"
            v-model="body"
            rows="3"
            :maxlength="MAX_COMMENT"
            class="w-full rounded bg-page p-2 focus-visible:outline-2 focus-visible:outline-accent"
            placeholder="What do these occurrences have in common?"
          />
          <div class="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              class="cursor-pointer rounded bg-bar px-4 py-1.5 font-medium hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canSubmit"
            >
              Comment on {{ tickedItems.length }} occurrence{{ tickedItems.length === 1 ? '' : 's' }}
            </button>
            <span class="text-sm text-ink/70">{{ trimmed.length }}/{{ MAX_COMMENT }}</span>
          </div>
        </template>
        <p v-else>
          <RouterLink :to="loginTarget" class="font-bold underline hover:text-accent" data-testid="glyph-login-link">Log in</RouterLink>
          to comment on the occurrences you ticked.
        </p>
        <p v-if="postError" role="alert" class="text-confidence-low">{{ postError }}</p>
        <p v-if="notice" role="status">{{ notice }}</p>
      </form>
    </template>

    <div v-if="active && !missing" class="mt-4" data-testid="glyph-comments">
      <h3 class="font-bold">Comments on {{ active }}</h3>
      <p v-if="commentsError" role="alert" class="text-confidence-low">{{ commentsError }}</p>
      <p v-else-if="!comments.length" class="text-sm text-ink/70">No comments yet.</p>
      <ul class="mt-2 space-y-3">
        <li v-for="comment in comments" :key="comment.id" class="rounded-xl bg-page p-3 text-sm" data-testid="glyph-comment">
          <p class="whitespace-pre-wrap break-words">{{ comment.body }}</p>
          <p class="mt-1 text-ink/70">
            {{ comment.author.username }} · {{ when(comment.created_at) }} · on {{ comment.targets.length }}
            occurrence{{ comment.targets.length === 1 ? '' : 's' }}
            <span class="sr-only">: {{ comment.targets.map((t) => `${t.tablet} ${t.position}`).join(', ') }}</span>
          </p>
          <button
            v-if="sessionUser && sessionUser.id === comment.author.id"
            type="button"
            class="mt-1 cursor-pointer underline hover:text-accent"
            @click="remove(comment)"
          >
            Delete
          </button>
        </li>
      </ul>
      <button v-if="commentsMore" type="button" class="mt-2 cursor-pointer underline" @click="loadComments(commentsMore)">Older comments</button>
    </div>

    <p v-if="credit" class="mt-4 text-xs text-ink/70">
      {{ credit.text }}
      <a :href="credit.url" target="_blank" rel="noopener" class="underline">{{ credit.licence }}</a>.
    </p>
  </section>
</template>
