<script setup>
// Corpus tablets (#82): find a tablet, see its tracing with the scholars' published boxes or
// the reader's own, and start correcting them (#83, #85). The tablet is in the URL
// (/tablets/HT-13), and so is the source (?boxes=model).
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import { loadSession, sessionFetch, sessionUser } from '../state/session'

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
const LISTING = ref(false)
const LIST_ERROR = ref('')
const BOXES = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
const COPY_ID = ref(null) // your corrected copy of this tablet, if you made one
const OPENING = ref(false)
const OPEN_ERROR = ref('')
let searched = ''
let request = 0

const SLUG = computed(() => route.params.slug || null)
const SOURCE = computed(() => (route.query.boxes === 'model' ? 'model' : 'scholar'))

let listId = 0
async function list(more = false) {
  const mine = ++listId
  LISTING.value = true
  LIST_ERROR.value = ''
  try {
    const query = new URLSearchParams({ q: searched, limit: PAGE, offset: more ? TABLETS.value.length : 0 })
    const response = await fetch(`/api/tablets?${query}`)
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

async function correct() {
  if (COPY_ID.value) {
    await router.push(`/box-sets/${COPY_ID.value}`)
    return
  }
  OPENING.value = true
  OPEN_ERROR.value = ''
  try {
    const response = await sessionFetch('/api/box-sets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tablet: SLUG.value, start: SOURCE.value }),
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

onMounted(async () => {
  await loadSession().catch(() => {}) // logged-out visitors can look; correcting needs a login
  list()
})
watch([SLUG, SOURCE], show, { immediate: true })
watch([SLUG, () => sessionUser.value?.id], checkCopy, { immediate: true })
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <h1 class="text-3xl font-bold">Tablets</h1>
    <p class="mt-1 text-ink/70">Every corpus tablet with the scholars' sign boxes. Compare them with the model's boxes, and correct either.</p>

    <div class="mt-6 flex flex-col gap-8 md:flex-row">
      <nav class="md:w-64 md:shrink-0" aria-label="Tablets">
        <form role="search" class="flex gap-2" @submit.prevent="search">
          <label class="sr-only" for="tablet-search">Find a tablet</label>
          <input id="tablet-search" v-model="QUERY" type="search" placeholder="HT 13" class="min-w-0 flex-1 rounded border border-ink/30 bg-white px-3 py-1.5" />
          <button type="submit" class="cursor-pointer rounded bg-bar px-3 py-1.5 font-semibold hover:brightness-95">Search</button>
        </form>
        <p v-if="LIST_ERROR" role="alert" class="mt-3 text-confidence-low">{{ LIST_ERROR }}</p>
        <p class="mt-3 text-sm text-ink/70" role="status">{{ LISTING ? 'Loading…' : `${TOTAL} tablet${TOTAL === 1 ? '' : 's'}` }}</p>
        <p v-if="WITHOUT_DRAWING" class="mt-2 rounded-lg bg-card p-2 text-xs text-ink/80" data-testid="missing-drawings">
          {{ WITHOUT_DRAWING }} more tablet{{ WITHOUT_DRAWING === 1 ? ' is' : 's are' }} hidden: {{ WITHOUT_DRAWING === 1 ? 'its drawing is' : 'their drawings are' }} not downloaded on this server.
          {{ HINT }}
        </p>
        <ul class="mt-2 max-h-[60vh] overflow-auto" data-testid="tablet-list">
          <li v-for="tablet in TABLETS" :key="tablet.slug">
            <button
              type="button"
              class="flex w-full cursor-pointer justify-between rounded px-2 py-1 text-left hover:bg-bar"
              :class="{ 'bg-bar font-semibold': tablet.slug === SLUG }"
              :aria-current="tablet.slug === SLUG ? 'page' : undefined"
              @click="pick(tablet.slug)"
            >
              <span>{{ tablet.tablet }}</span><span class="text-sm text-ink/60">{{ tablet.signs }} sign{{ tablet.signs === 1 ? '' : 's' }}</span>
            </button>
          </li>
        </ul>
        <button v-if="TABLETS.length < TOTAL" type="button" class="mt-2 cursor-pointer underline" :disabled="LISTING" @click="list(true)">More tablets</button>
      </nav>

      <section class="min-w-0 flex-1" aria-live="polite">
        <p v-if="!SLUG" class="rounded-2xl bg-card p-6">Pick a tablet to see its boxes.</p>
        <template v-else>
          <div class="flex flex-wrap items-center gap-3">
            <h2 class="text-2xl font-bold">{{ BOXES?.tablet || SLUG.replaceAll('-', ' ') }}</h2>
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
                @click="correct"
              >{{ COPY_ID ? 'Open your corrected copy' : OPENING ? 'Opening…' : `Correct the ${SOURCE === 'model' ? "model's" : "scholars'"} boxes` }}</button>
              <RouterLink v-else :to="{ path: '/login', query: { redirect: route.fullPath } }" class="underline">Log in to correct the boxes</RouterLink>
              <p v-if="OPEN_ERROR" role="alert" class="text-confidence-low">{{ OPEN_ERROR }}</p>
            </div>
            <div class="mt-4 lg:w-3/4">
              <TabletOverlay :signs="BOXES.signs" :formulas="BOXES.formulas">
                <img :src="`/api${BOXES.image_url}`" :alt="`${BOXES.tablet} tracing`" class="w-full rounded-lg bg-white" />
              </TabletOverlay>
            </div>
            <p class="mt-4">{{ BOXES.summary }}</p>
            <p class="mt-1"><span class="text-ink/70">Transliteration:</span> {{ BOXES.symbol_interpretation }}</p>
            <FractionCheck :analysis="{ ...BOXES, trained: true }" class="mt-6" />
            <p class="mt-6 text-sm text-ink/70" data-testid="credit">
              {{ BOXES.credit.text }} <a :href="BOXES.credit.url" class="underline" rel="noopener" target="_blank">{{ BOXES.credit.licence }}</a>
            </p>
          </template>
        </template>
      </section>
    </div>
  </main>
</template>
