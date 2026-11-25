<script setup>
// Corpus tablets (#82): find a tablet, see its tracing with the scholars' published boxes or
// the reader's own, and start correcting them (#83, #85). The tablet is in the URL
// (/tablets/HT-13), and so is the source (?boxes=model).
import SketchPad from '../components/signs/SketchPad.vue'
import { RECENT_TABLETS, openedTablet } from '../state/preferences'
import { useGlyphActivity } from '../composables/useGlyphActivity'
import EditionsPanel from '../components/versions/EditionsPanel.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import { loadSession, sessionAdmin, sessionFetch, sessionUser } from '../state/session'

const PAGE = 50
const SOURCES = [
  { value: 'scholar', label: "Scholars' boxes" },
  { value: 'model', label: "Model's boxes" },
]

const route = useRoute()
const router = useRouter()
const QUERY = ref('')
const TABLETS = ref([])
const TOTAL = ref(0)
const WITHOUT_DRAWING = ref(0) // tablets hidden because their drawing is not downloaded on this server
const HINT = ref('')
const CORPUS_MISSING = ref(false) // no transcriptions at all: a fresh server
// Admins can download the missing data onto the server from the corpus-v1 release.
const DOWNLOAD = ref(null) // { state, log, error } from /tablets/download
const DOWNLOAD_ERROR = ref('')
const DOWNLOADING = computed(() => DOWNLOAD.value?.state === 'running')
const POLL_MS = 1500
let poll = null
const LISTING = ref(false)
const LIST_ERROR = ref('')
const BOXES = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
const COPY_ID = ref(null) // your corrected copy of this tablet, if you made one
const OPENING = ref(false)
const OPEN_ERROR = ref('')
// The tablet's versions (workbench): the scholars', the model's and the copies you can open.
const VERSIONS = ref([])
const COMPARE = ref([]) // version keys ticked for comparing, 2 to 6
const MAX_COMPARE = 6
const COPIES = computed(() => VERSIONS.value.filter((version) => version.kind === 'copy' || version.kind === 'edition'))
let searched = ''
let request = 0

const SLUG = computed(() => route.params.slug || null)
// Search by sign sequence (workbench, story G): KU-RO, AB81-AB02, ku-*-ro, ku|ka-ro.
const MODE = ref('tablet') // tablet | sequence
const SEQUENCE = ref(null) // the last sequence search's results
const SEQUENCE_SOURCE = ref('scholar') // scholar | edition
const ACROSS_WORDS = ref(false)
const SEQUENCE_ERROR = ref('')
const SEARCHING = ref(false)
const SKETCHING = ref(false)
const HIGHLIGHT = computed(() => String(route.query.hl ?? '').split(',').filter(Boolean).map(Number))

async function searchSequence() {
  const q = QUERY.value.trim()
  SEQUENCE_ERROR.value = ''
  if (!q) return
  SEARCHING.value = true
  try {
    const query = new URLSearchParams({ q, source: SEQUENCE_SOURCE.value, across_words: String(ACROSS_WORDS.value), limit: '100' })
    const response = await fetch(`/api/corpus/search?${query}`)
    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The search failed.')
    SEQUENCE.value = body
  } catch (failure) {
    SEQUENCE.value = null
    SEQUENCE_ERROR.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  } finally {
    SEARCHING.value = false
  }
}

function openHit(item) {
  if (item.release_id) {
    router.push(`/editions/${item.release_id}`)
    return
  }
  const positions = item.hits.flatMap((hit) => hit.positions).filter((position) => position != null)
  router.push({ path: `/tablets/${item.slug}`, query: positions.length ? { hl: positions.join(',') } : {} })
}

// Opened from a sequence search: bring the first highlighted sign into view once the drawing has
// loaded (before that, the boxes are not where they will be).
async function showFound() {
  if (!HIGHLIGHT.value.length) return
  await nextTick()
  document.querySelector('[data-testid="sign-box"].found')?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
}

function addSketched(sign) {
  QUERY.value = QUERY.value.trim() ? `${QUERY.value.trim()}-${sign}` : sign
  SKETCHING.value = false
}
// Bubbles with new activity on the scholars' glyphs (their sign ids are positions); opening one clears it.
const { COUNTS: ACTIVITY, seen } = useGlyphActivity(SLUG)
// Bookmarks (kept on the server) and recently opened tablets (in this browser): workbench, story K.
const BOOKMARKS = ref([])
const BOOKMARKING = ref(false)
const nameOf = (slug) => slug.replaceAll('-', ' ')
watch(SLUG, (slug) => openedTablet(slug), { immediate: true })

async function loadBookmarks() {
  BOOKMARKS.value = []
  if (!sessionUser.value) return
  const response = await fetch('/api/bookmarks').catch(() => null)
  if (response?.ok) BOOKMARKS.value = (await response.json()).tablets
}
watch(() => sessionUser.value?.id, loadBookmarks, { immediate: true })

async function toggleBookmark() {
  BOOKMARKING.value = true
  try {
    const marked = BOOKMARKS.value.includes(SLUG.value)
    const response = await sessionFetch(`/api/bookmarks/${encodeURIComponent(SLUG.value)}`, { method: marked ? 'DELETE' : 'PUT' })
    if (response.ok) BOOKMARKS.value = (await response.json()).tablets
  } finally {
    BOOKMARKING.value = false
  }
}
const SOURCE = computed(() => (route.query.boxes === 'model' ? 'model' : 'scholar'))

let listId = 0
async function list(more = false) {
  const mine = ++listId
  LISTING.value = true
  LIST_ERROR.value = ''
  try {
    const query = new URLSearchParams({ q: searched, limit: PAGE, offset: more ? TABLETS.value.length : 0 })
    const response = await fetch(`/api/tablets?${query}`)
    if (mine === listId) CORPUS_MISSING.value = response.status === 503
    if (!response.ok) throw new Error(response.status === 503 ? 'The corpus is not installed on this server.' : 'The tablets could not be loaded.')
    const page = await response.json()
    if (mine !== listId) return
    TABLETS.value = more ? [...TABLETS.value, ...page.items] : page.items
    TOTAL.value = page.total
    WITHOUT_DRAWING.value = page.without_drawing ?? 0
    HINT.value = page.hint ?? ''
  } catch (failure) {
    if (mine === listId) LIST_ERROR.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  } finally {
    if (mine === listId) LISTING.value = false
  }
}

function search() {
  searched = QUERY.value.trim()
  list()
}

async function show() {
  const mine = ++request
  BOXES.value = null
  ERROR.value = ''
  if (!SLUG.value) return
  LOADING.value = true
  try {
    const response = await fetch(`/api/tablets/${encodeURIComponent(SLUG.value)}/boxes?source=${SOURCE.value}`)
    if (mine !== request) return
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(typeof body?.detail === 'string' ? body.detail : response.status === 404 ? 'Tablet not found.' : 'The boxes could not be loaded.')
    }
    BOXES.value = await response.json()
  } catch (failure) {
    if (mine === request) ERROR.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  } finally {
    if (mine === request) LOADING.value = false
  }
}

// Whether you already have a corrected copy of this tablet; checked again once the session loads.
async function checkCopy() {
  COPY_ID.value = null
  const slug = SLUG.value
  if (!slug || !sessionUser.value) return
  const response = await sessionFetch(`/api/tablets/${encodeURIComponent(slug)}/box-set`).catch(() => null)
  if (slug === SLUG.value && response?.ok) COPY_ID.value = (await response.json()).id
}

function pick(slug) {
  router.push({ path: `/tablets/${slug}`, query: route.query.boxes ? { boxes: route.query.boxes } : {} })
}

function setSource(source) {
  router.replace({ path: route.path, query: source === 'model' ? { boxes: 'model' } : {} })
}

// Open your latest copy, or (`another`, or when you have none) start a new one from the boxes on show.
async function correct(another = false) {
  if (COPY_ID.value && !another) {
    await router.push(`/box-sets/${COPY_ID.value}`)
    return
  }
  OPENING.value = true
  OPEN_ERROR.value = ''
  try {
    const response = await sessionFetch('/api/box-sets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tablet: SLUG.value, start: SOURCE.value, ...(another ? { new: true } : {}) }),
    })
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The boxes could not be opened for editing.')
    await router.push(`/box-sets/${body.id}`)
  } catch (failure) {
    OPEN_ERROR.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  } finally {
    OPENING.value = false
  }
}

function track(status) {
  DOWNLOAD.value = status
  clearTimeout(poll)
  if (status.state === 'running') poll = setTimeout(checkDownload, POLL_MS)
  else if (status.state === 'done') list()
}

async function checkDownload() {
  const response = await sessionFetch('/api/tablets/download').catch(() => null)
  if (response?.ok) track(await response.json())
  else poll = setTimeout(checkDownload, POLL_MS * 2) // a blip: keep watching
}

async function download() {
  DOWNLOAD_ERROR.value = ''
  try {
    const response = await sessionFetch('/api/tablets/download', { method: 'POST' })
    const body = await response.json().catch(() => null)
    if (response.status === 409) return checkDownload() // already running (another admin, or another tab)
    if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The download could not be started.')
    track(body)
  } catch (failure) {
    DOWNLOAD_ERROR.value = failure instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : failure.message
  }
}

onBeforeUnmount(() => clearTimeout(poll))

onMounted(async () => {
  await loadSession().catch(() => {}) // logged-out visitors can look; correcting needs a login
  list()
})
watch([SLUG, SOURCE], show, { immediate: true })
watch([SLUG, () => sessionUser.value?.id], checkCopy, { immediate: true })

let versionsId = 0
async function loadVersions() {
  const mine = ++versionsId
  VERSIONS.value = []
  COMPARE.value = []
  if (!SLUG.value) return
  const response = await fetch(`/api/tablets/${encodeURIComponent(SLUG.value)}/versions`).catch(() => null)
  if (mine === versionsId && response?.ok) VERSIONS.value = (await response.json()).items
}
watch([SLUG, () => sessionUser.value?.id], loadVersions, { immediate: true })

function versionName(version) {
  if (version.kind === 'scholar') return "Scholars' boxes"
  if (version.kind === 'model') return "Model's boxes"
  const whose = version.mine ? 'Your' : `${version.owner}'s`
  const what = version.kind === 'edition' ? 'edition' : 'copy'
  return version.title ? `${whose} ${what}: ${version.title}` : `${whose} ${what}`
}

function mergeVersions() {
  router.push({ path: `/tablets/${SLUG.value}/merge`, query: { v: COMPARE.value } })
}

function compareVersions() {
  router.push({ path: `/tablets/${SLUG.value}/compare`, query: { v: COMPARE.value } })
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <h1 class="text-3xl font-bold">Tablets</h1>
    <p class="mt-1 text-ink/80">Every corpus tablet with the scholars' sign boxes. Compare them with the model's boxes, and correct either.</p>

    <div class="mt-6 flex flex-col gap-8 md:flex-row">
      <nav class="md:w-64 md:shrink-0" aria-label="Tablets">
        <div class="mb-2 flex gap-1 text-sm" role="group" aria-label="Search by">
          <button
            v-for="option in [{ value: 'tablet', label: 'Tablet' }, { value: 'sequence', label: 'Sign sequence' }]"
            :key="option.value"
            type="button"
            class="cursor-pointer rounded px-2 py-0.5 hover:bg-bar"
            :class="{ 'bg-bar font-semibold': MODE === option.value }"
            :aria-pressed="MODE === option.value"
            :data-testid="`search-${option.value}`"
            @click="MODE = option.value"
          >{{ option.label }}</button>
        </div>
        <form role="search" class="flex gap-2" @submit.prevent="MODE === 'sequence' ? searchSequence() : search()">
          <label class="sr-only" for="tablet-search">{{ MODE === 'sequence' ? 'Find a sign sequence' : 'Find a tablet' }}</label>
          <input id="tablet-search" v-model="QUERY" type="search" :placeholder="MODE === 'sequence' ? 'KU-RO, ku-*-ro, AB81' : 'HT 13'" class="min-w-0 flex-1 rounded border border-ink/30 bg-white px-3 py-1.5" />
          <button type="submit" class="cursor-pointer rounded bg-bar px-3 py-1.5 font-semibold hover:brightness-95">Search</button>
        </form>
        <div v-if="MODE === 'sequence'" class="mt-2 text-sm" data-testid="sequence-options">
          <label class="flex items-center gap-1"><input v-model="ACROSS_WORDS" type="checkbox" data-testid="across-words" /> Across word breaks</label>
          <label class="mt-1 flex items-center gap-1">In
            <select v-model="SEQUENCE_SOURCE" class="rounded border border-ink/30 bg-white px-1" data-testid="sequence-source">
              <option value="scholar">the scholars' transcriptions</option>
              <option value="edition">the community editions</option>
            </select>
          </label>
          <button type="button" class="mt-1 cursor-pointer underline" :aria-expanded="SKETCHING" data-testid="sequence-sketch" @click="SKETCHING = !SKETCHING">✎ Draw a sign to add</button>
          <SketchPad v-if="SKETCHING" class="mt-2 rounded-lg bg-card p-2" :limit="6" @pick="addSketched" />
          <p class="mt-1 text-xs text-ink/80">Signs by number or reading, joined by - ; * for any sign, | for either.</p>
        </div>
        <p v-if="LIST_ERROR" role="alert" class="mt-3 text-confidence-low">{{ LIST_ERROR }}</p>
        <p v-if="MODE === 'tablet'" class="mt-3 text-sm text-ink/80" role="status">{{ LISTING ? 'Loading…' : `${TOTAL} tablet${TOTAL === 1 ? '' : 's'}` }}</p>
        <div v-if="WITHOUT_DRAWING || CORPUS_MISSING || DOWNLOAD" class="mt-2 rounded-lg bg-card p-2 text-xs text-ink/80" data-testid="missing-drawings">
          <p v-if="WITHOUT_DRAWING">
            {{ WITHOUT_DRAWING }} more tablet{{ WITHOUT_DRAWING === 1 ? ' is' : 's are' }} hidden: {{ WITHOUT_DRAWING === 1 ? 'its drawing is' : 'their drawings are' }} not downloaded on this server.
          </p>
          <template v-if="sessionAdmin">
            <button
              v-if="WITHOUT_DRAWING || CORPUS_MISSING || DOWNLOADING"
              type="button"
              class="mt-2 w-full cursor-pointer rounded bg-bar px-3 py-1.5 text-sm font-semibold hover:brightness-95 disabled:cursor-wait disabled:opacity-60"
              :disabled="DOWNLOADING"
              data-testid="download-corpus"
              @click="download"
            >{{ DOWNLOADING ? 'Downloading…' : 'Download the drawings (33 MB)' }}</button>
            <p v-if="DOWNLOADING && DOWNLOAD.log.length" class="mt-1 font-mono" role="status" data-testid="download-progress">{{ DOWNLOAD.log.at(-1) }}</p>
            <p v-else-if="DOWNLOAD?.state === 'done'" class="mt-1" role="status">Downloaded. The tablets are listed now.</p>
            <p v-if="DOWNLOAD?.state === 'failed' || DOWNLOAD_ERROR" role="alert" class="mt-1 text-confidence-low">{{ DOWNLOAD_ERROR || DOWNLOAD.error }}</p>
            <p v-if="WITHOUT_DRAWING || CORPUS_MISSING" class="mt-1 text-ink/80">From the corpus-v1 release on GitHub (CC BY-NC-SA 4.0). Or on the server: python scripts/fetch_corpus.py</p>
          </template>
          <p v-else-if="WITHOUT_DRAWING || CORPUS_MISSING" class="mt-1">An admin can download them from this page. {{ HINT || 'Download them with: python scripts/fetch_corpus.py' }}</p>
        </div>
        <div v-if="MODE === 'tablet' && !QUERY.trim() && (BOOKMARKS.length || RECENT_TABLETS.length)" class="mt-3 text-sm" data-testid="quick-tablets">
          <template v-for="group in [{ name: 'Bookmarked', slugs: BOOKMARKS, id: 'bookmarked' }, { name: 'Recently opened', slugs: RECENT_TABLETS.filter((slug) => !BOOKMARKS.includes(slug)).slice(0, 5), id: 'recent' }]" :key="group.id">
            <template v-if="group.slugs.length">
              <h2 class="mt-2 font-semibold text-ink/80">{{ group.name }}</h2>
              <ul :data-testid="`${group.id}-tablets`">
                <li v-for="slug in group.slugs" :key="slug">
                  <button type="button" class="w-full cursor-pointer rounded px-2 py-0.5 text-left hover:bg-bar" :class="{ 'bg-bar font-semibold': slug === SLUG }" @click="pick(slug)">{{ nameOf(slug) }}</button>
                </li>
              </ul>
            </template>
          </template>
          <h2 class="mt-2 font-semibold text-ink/80">All tablets</h2>
        </div>
        <template v-if="MODE === 'sequence'">
          <p v-if="SEQUENCE_ERROR" role="alert" class="mt-3 text-confidence-low">{{ SEQUENCE_ERROR }}</p>
          <p v-else-if="SEARCHING" role="status" class="mt-3 text-sm">Searching…</p>
          <template v-else-if="SEQUENCE">
            <p class="mt-3 text-sm text-ink/80" role="status" data-testid="sequence-count">
              {{ SEQUENCE.total_hits }} match{{ SEQUENCE.total_hits === 1 ? '' : 'es' }} on {{ SEQUENCE.total_tablets }} tablet{{ SEQUENCE.total_tablets === 1 ? '' : 's' }}
            </p>
            <ul class="mt-2 max-h-[60vh] overflow-auto" data-testid="sequence-results">
              <li v-for="item in SEQUENCE.items" :key="item.slug">
                <button type="button" class="w-full cursor-pointer rounded px-2 py-1 text-left hover:bg-bar" :class="{ 'bg-bar font-semibold': item.slug === SLUG }" @click="openHit(item)">
                  <span class="flex justify-between"><span>{{ item.tablet }}</span><span class="text-sm text-ink/80">{{ item.hits.length }}×</span></span>
                  <span class="block text-xs text-ink/80">{{ [...new Set(item.hits.map((hit) => hit.text))].join(', ') }}<template v-if="item.release_id"> · in the community edition</template></span>
                </button>
              </li>
            </ul>
          </template>
        </template>
        <ul v-else class="mt-2 max-h-[60vh] overflow-auto" data-testid="tablet-list">
          <li v-for="tablet in TABLETS" :key="tablet.slug">
            <button
              type="button"
              class="flex w-full cursor-pointer justify-between rounded px-2 py-1 text-left hover:bg-bar"
              :class="{ 'bg-bar font-semibold': tablet.slug === SLUG }"
              :aria-current="tablet.slug === SLUG ? 'page' : undefined"
              @click="pick(tablet.slug)"
            >
              <span>{{ tablet.tablet }}</span><span class="text-sm text-ink/80">{{ tablet.signs }} sign{{ tablet.signs === 1 ? '' : 's' }}</span>
            </button>
          </li>
        </ul>
        <button v-if="MODE === 'tablet' && TABLETS.length < TOTAL" type="button" class="mt-2 cursor-pointer underline" :disabled="LISTING" @click="list(true)">More tablets</button>
      </nav>

      <section class="min-w-0 flex-1" aria-live="polite">
        <p v-if="!SLUG" class="rounded-2xl bg-card p-6">Pick a tablet to see its boxes.</p>
        <template v-else>
          <div class="flex flex-wrap items-center gap-3">
            <h2 class="text-2xl font-bold">{{ BOXES?.tablet || SLUG.replaceAll('-', ' ') }}</h2>
            <button
              v-if="sessionUser"
              type="button"
              class="cursor-pointer rounded px-2 py-0.5 text-xl leading-none hover:bg-bar disabled:opacity-50"
              :aria-pressed="BOOKMARKS.includes(SLUG)"
              :aria-label="BOOKMARKS.includes(SLUG) ? 'Remove the bookmark' : 'Bookmark this tablet'"
              :title="BOOKMARKS.includes(SLUG) ? 'Bookmarked: click to remove' : 'Bookmark this tablet'"
              :disabled="BOOKMARKING"
              data-testid="bookmark"
              @click="toggleBookmark"
            >{{ BOOKMARKS.includes(SLUG) ? '★' : '☆' }}</button>
            <div class="flex gap-1" role="group" aria-label="Which boxes">
              <button
                v-for="option in SOURCES"
                :key="option.value"
                type="button"
                class="cursor-pointer rounded px-3 py-1 text-sm hover:bg-bar"
                :class="{ 'bg-bar font-semibold': SOURCE === option.value }"
                :aria-pressed="SOURCE === option.value"
                :data-testid="`source-${option.value}`"
                @click="setSource(option.value)"
              >{{ option.label }}</button>
            </div>
          </div>

          <p v-if="LOADING" role="status" class="mt-4">
            {{ SOURCE === 'model' ? 'The model is reading this tablet… the first reading can take half a minute.' : 'Loading…' }}
          </p>
          <p v-else-if="ERROR" role="alert" class="mt-4 text-confidence-low">{{ ERROR }}</p>

          <template v-if="BOXES">
            <div class="mt-4 flex flex-wrap items-center gap-3">
              <button
                v-if="sessionUser"
                type="button"
                class="cursor-pointer rounded bg-bar px-5 py-1.5 font-semibold hover:brightness-95 disabled:opacity-60"
                :disabled="OPENING"
                data-testid="correct-boxes"
                @click="correct()"
              >{{ COPY_ID ? 'Open your corrected copy' : OPENING ? 'Opening…' : `Correct the ${SOURCE === 'model' ? "model's" : "scholars'"} boxes` }}</button>
              <button
                v-if="sessionUser && COPY_ID"
                type="button"
                class="cursor-pointer rounded px-3 py-1.5 underline hover:bg-bar disabled:opacity-60"
                :disabled="OPENING"
                data-testid="new-copy"
                @click="correct(true)"
              >New copy from the {{ SOURCE === 'model' ? "model's" : "scholars'" }} boxes</button>
              <RouterLink v-else-if="!sessionUser" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="underline">Log in to correct the boxes</RouterLink>
              <p v-if="OPEN_ERROR" role="alert" class="text-confidence-low">{{ OPEN_ERROR }}</p>
            </div>

            <!-- The drawing first; beside it on wide screens, below it on narrow ones: the versions and editions. -->
            <div class="mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(18rem,2fr)]">
              <div class="min-w-0">
                <TabletOverlay
                  :signs="BOXES.signs"
                  :formulas="BOXES.formulas"
                  :badges="SOURCE === 'scholar' ? ACTIVITY : {}"
                  :highlight="SOURCE === 'scholar' ? HIGHLIGHT : []"
                  @select="(sign) => SOURCE === 'scholar' && seen(sign.id)"
                >
                  <img :src="`/api${BOXES.image_url}`" @load="showFound" :alt="`${BOXES.tablet} tracing`" class="w-full rounded-lg bg-white" />
                </TabletOverlay>
              </div>
              <div class="flex min-w-0 flex-col gap-4">
                <section v-if="sessionUser && VERSIONS.length" class="rounded-2xl bg-card p-4" aria-labelledby="versions-h" data-testid="versions">
                  <div class="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 id="versions-h" class="font-bold">Versions of this tablet</h3>
                    <button
                      type="button"
                      class="cursor-pointer rounded bg-bar px-3 py-1 text-sm font-semibold hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="COMPARE.length < 2"
                      data-testid="compare-versions"
                      @click="compareVersions"
                    >Compare {{ COMPARE.length >= 2 ? COMPARE.length : '' }} versions</button>
                    <button
                      type="button"
                      class="cursor-pointer rounded bg-bar px-3 py-1 text-sm font-semibold hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="COMPARE.length < 2"
                      data-testid="merge-versions"
                      @click="mergeVersions"
                    >Merge into an edition</button>
                  </div>
                  <p class="text-sm text-ink/80">Tick two to {{ MAX_COMPARE }} to see where they agree and differ, or to merge them into an edition of your own.</p>
                  <ul class="mt-2">
                    <li v-for="version in VERSIONS" :key="version.key" class="flex items-center gap-3 py-1" data-testid="version">
                      <input
                        :id="`compare-${version.key}`"
                        v-model="COMPARE"
                        type="checkbox"
                        :value="version.key"
                        :disabled="!COMPARE.includes(version.key) && COMPARE.length >= MAX_COMPARE"
                        class="h-4 w-4"
                      />
                      <label :for="`compare-${version.key}`" class="flex-1">
                        {{ versionName(version) }}
                        <span v-if="version.box_count != null" class="ml-1 text-sm text-ink/80">· {{ version.box_count }} box{{ version.box_count === 1 ? '' : 'es' }}</span>
                        <span v-if="version.permission && !version.mine" class="ml-1 text-sm text-ink/80">· you can {{ version.permission === 'manage' ? 'manage' : version.permission }}</span>
                      </label>
                      <RouterLink v-if="version.key.startsWith('copy:')" :to="`/box-sets/${version.key.slice(5)}`" class="inline-flex min-h-10 items-center px-1 text-sm underline">Open</RouterLink>
                    </li>
                  </ul>
                  <p v-if="!COPIES.length" class="mt-1 text-sm text-ink/80">No corrected copies yet: yours, and those shared with you, will be listed here.</p>
                </section>
                <EditionsPanel :slug="SLUG" />
              </div>
            </div>
            <p class="mt-4">{{ BOXES.summary }}</p>
            <p class="mt-1"><span class="text-ink/80">Transliteration:</span> {{ BOXES.symbol_interpretation }}</p>
            <FractionCheck :analysis="{ ...BOXES, trained: true }" class="mt-6" />
            <p class="mt-6 text-sm text-ink/80" data-testid="credit">
              {{ BOXES.credit.text }} <a :href="BOXES.credit.url" class="underline" rel="noopener" target="_blank">{{ BOXES.credit.licence }}</a>
            </p>
          </template>
        </template>
      </section>
    </div>
  </main>
</template>
