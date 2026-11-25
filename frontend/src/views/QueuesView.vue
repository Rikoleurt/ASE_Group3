<script setup>
// Work queues (workbench, story J): where a scholar's attention is most useful. Each row links to
// the action it needs: compare, correct, review, merge or vote.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { sessionFetch, sessionReviewer } from '../state/session'

const PAGE = 25
const TABS = computed(() => [
  { key: 'disagreement', label: 'Most disagreement' },
  { key: 'low-confidence', label: 'Low-confidence signs' },
  ...(sessionReviewer.value ? [{ key: 'review', label: 'Awaiting review' }] : []),
  { key: 'no-edition', label: 'No edition yet' },
  { key: 'close-votes', label: 'Close votes' },
])
const INTRO = {
  disagreement:
    'Tablets where two readings differ most: the places where a scholar can settle a question.',
  'low-confidence':
    "The model's least confident signs across the corpus: a quick check or correction each.",
  review: 'Sign corrections waiting for a reviewer, oldest first.',
  'no-edition':
    'Tablets nobody has released an edition of yet, most signs first: merge their versions into one.',
  'close-votes': 'Tablets where one more vote decides the community edition.',
}

const route = useRoute()
const router = useRouter()
const TAB = computed(() =>
  TABS.value.some((tab) => tab.key === route.query.tab) ? route.query.tab : 'disagreement',
)
const AGAINST = computed(() => (route.query.against === 'edition' ? 'edition' : 'model'))
const ITEMS = ref([])
const TOTAL = ref(0)
const META = ref({})
const LOADING = ref(false)
const ERROR = ref('')
let request = 0

const percent = (value) => `${Math.round(value * 100)}%`
const builtAt = computed(() =>
  META.value.built_at ? new Date(META.value.built_at).toLocaleString() : '',
)

function show(tab, against) {
  const query = { tab }
  if (tab === 'disagreement' && against === 'edition') query.against = 'edition'
  router.replace({ path: '/queues', query })
}

function moveTab(event, index) {
  const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key]
  if (!step) return
  const next = TABS.value[(index + step + TABS.value.length) % TABS.value.length]
  show(next.key)
  document.getElementById(`queue-tab-${next.key}`)?.focus()
}

function url(more) {
  const offset = more ? ITEMS.value.length : 0
  if (TAB.value === 'review') return '/api/corrections?status=pending&limit=200'
  const query = new URLSearchParams({ offset: String(offset), limit: String(PAGE) })
  if (TAB.value === 'disagreement') query.set('against', AGAINST.value)
  return `/api/queues/${TAB.value}?${query}`
}

async function load(more = false) {
  const mine = ++request
  LOADING.value = true
  ERROR.value = ''
  if (!more) {
    ITEMS.value = []
    TOTAL.value = 0
    META.value = {}
  }
  try {
    const response = await sessionFetch(url(more))
    if (mine !== request) return
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    if (!response.ok) throw new Error('This queue could not be loaded. Please try again.')
    const body = await response.json()
    if (mine !== request) return
    if (Array.isArray(body)) {
      ITEMS.value = body // the review queue: corrections
      TOTAL.value = body.length
    } else {
      const { items, total, ...meta } = body
      ITEMS.value = more ? [...ITEMS.value, ...items] : items
      TOTAL.value = total
      META.value = meta
    }
  } catch (failure) {
    if (mine !== request) return
    ERROR.value =
      failure instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : failure.message
  } finally {
    if (mine === request) LOADING.value = false
  }
}

watch([TAB, AGAINST], () => load(), { immediate: true })

function compareLink(row) {
  const other = AGAINST.value === 'edition' ? `copy:${row.edition_id}` : 'model'
  return { path: `/tablets/${row.slug}/compare`, query: { v: ['scholar', other] } }
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <h1 class="text-3xl font-bold">Work queues</h1>
    <p class="mt-1 text-ink/80">
      Where your attention is most useful, with a link to the action each item needs.
    </p>

    <div
      role="tablist"
      aria-label="Queues"
      class="mt-6 flex flex-wrap gap-1 border-b border-ink/20"
    >
      <button
        v-for="(tab, index) in TABS"
        :id="`queue-tab-${tab.key}`"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="TAB === tab.key"
        :aria-controls="'queue-panel'"
        :tabindex="TAB === tab.key ? 0 : -1"
        :data-testid="`queue-tab-${tab.key}`"
        class="-mb-px min-h-10 rounded-t border px-3 py-2 text-sm"
        :class="
          TAB === tab.key
            ? 'border-ink/20 border-b-page bg-page font-semibold'
            : 'border-transparent text-ink/80 hover:text-ink'
        "
        @click="show(tab.key)"
        @keydown="moveTab($event, index)"
      >
        {{ tab.label }}
      </button>
    </div>

    <section id="queue-panel" role="tabpanel" :aria-labelledby="`queue-tab-${TAB}`" class="pt-4">
      <p class="text-ink/80">{{ INTRO[TAB] }}</p>

      <div
        v-if="TAB === 'disagreement'"
        class="mt-3 flex flex-wrap items-center gap-2 text-sm"
        role="group"
        aria-label="Compare the scholars with"
      >
        <span class="font-semibold">Scholars against:</span>
        <button
          v-for="option in [
            { key: 'model', label: 'the model' },
            { key: 'edition', label: 'the community edition' },
          ]"
          :key="option.key"
          type="button"
          :aria-pressed="AGAINST === option.key"
          :data-testid="`against-${option.key}`"
          class="min-h-10 rounded border px-3 py-1"
          :class="
            AGAINST === option.key ? 'border-ink bg-ink text-page' : 'border-ink/30 hover:bg-ink/5'
          "
          @click="show('disagreement', option.key)"
        >
          {{ option.label }}
        </button>
      </div>

      <p
        v-if="META.missing_hint"
        class="mt-4 rounded border border-amber-600/40 bg-amber-50 p-3 text-sm"
        data-testid="queue-missing"
      >
        The model has not read the corpus for the queues yet. {{ META.missing_hint }}
      </p>
      <p v-else-if="builtAt" class="mt-3 text-xs break-all text-ink/80" data-testid="queue-built">
        Model readings from {{ builtAt
        }}<template v-if="META.model_version"> (model {{ META.model_version }})</template>.
      </p>

      <p v-if="ERROR" class="mt-4 text-red-700" role="alert">{{ ERROR }}</p>
      <p class="mt-3 text-sm text-ink/80" role="status" data-testid="queue-count">
        <template v-if="LOADING && !ITEMS.length">Loading…</template>
        <template v-else-if="!ERROR">{{ TOTAL }} item{{ TOTAL === 1 ? '' : 's' }}</template>
      </p>

      <ol
        v-if="ITEMS.length"
        class="mt-2 divide-y divide-ink/10 rounded border border-ink/15 bg-white"
        data-testid="queue-items"
      >
        <template v-if="TAB === 'disagreement'">
          <li
            v-for="row in ITEMS"
            :key="row.slug"
            class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
            data-testid="queue-row"
          >
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 w-28 items-center font-semibold underline"
              >{{ row.tablet }}</RouterLink
            >
            <span class="w-40 tabular-nums" :title="`${percent(row.score)} of the places differ`">
              <strong>{{ row.differs + row.missing }} of {{ row.total }}</strong> places differ
            </span>
            <span class="grow text-sm text-ink/80">
              {{ row.differs }} different sign{{ row.differs === 1 ? '' : 's' }},
              {{ row.missing }} box{{ row.missing === 1 ? '' : 'es' }} in one only,
              {{ row.agree }} agree
            </span>
            <RouterLink
              :to="compareLink(row)"
              class="inline-flex min-h-10 items-center rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5"
              data-testid="queue-action"
              >Compare</RouterLink
            >
          </li>
        </template>

        <template v-else-if="TAB === 'low-confidence'">
          <li
            v-for="row in ITEMS"
            :key="`${row.slug}-${row.id}`"
            class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
            data-testid="queue-row"
          >
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 w-28 items-center font-semibold underline"
              >{{ row.tablet }}</RouterLink
            >
            <span class="w-40">
              <img
                v-if="row.sign && row.sign !== 'unidentified'"
                :src="`/api/glyphs/${encodeURIComponent(row.sign)}/preview.png`"
                alt=""
                class="mr-1 inline h-6 w-6 object-contain align-middle"
                loading="lazy"
              />
              {{ row.label }}
            </span>
            <span class="w-20 tabular-nums"
              ><strong>{{ Math.round(row.confidence) }}%</strong> sure</span
            >
            <span class="grow text-sm text-ink/80">
              <template v-if="row.candidates.length > 1"
                >or
                {{
                  row.candidates
                    .slice(1)
                    .map((c) => c.label)
                    .join(', ')
                }}</template
              >
            </span>
            <RouterLink
              :to="{ path: `/tablets/${row.slug}`, query: { boxes: 'model' } }"
              class="inline-flex min-h-10 items-center rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5"
              data-testid="queue-action"
              >Check</RouterLink
            >
          </li>
        </template>

        <template v-else-if="TAB === 'review'">
          <li
            v-for="row in ITEMS"
            :key="row.id"
            class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
            data-testid="queue-row"
          >
            <span class="w-56">
              {{ row.original_label }} →
              <strong>{{ row.uncertain ? 'flagged as uncertain' : row.proposed_sign }}</strong>
            </span>
            <span class="grow text-sm text-ink/80"
              >analysis {{ row.analysis_id }}, sign {{ row.sign_id }}, proposed
              {{ new Date(row.created_at).toLocaleDateString() }}</span
            >
            <RouterLink
              to="/review"
              class="inline-flex min-h-10 items-center rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5"
              data-testid="queue-action"
              >Review</RouterLink
            >
          </li>
        </template>

        <template v-else-if="TAB === 'no-edition'">
          <li
            v-for="row in ITEMS"
            :key="row.slug"
            class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
            data-testid="queue-row"
          >
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 w-28 items-center font-semibold underline"
              >{{ row.tablet }}</RouterLink
            >
            <span class="grow text-sm text-ink/80"
              >{{ row.signs }} sign{{ row.signs === 1 ? '' : 's' }}</span
            >
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 items-center rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5"
              data-testid="queue-action"
              >Start an edition</RouterLink
            >
          </li>
        </template>

        <template v-else>
          <li
            v-for="row in ITEMS"
            :key="row.slug"
            class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
            data-testid="queue-row"
          >
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 w-28 items-center font-semibold underline"
              >{{ row.tablet }}</RouterLink
            >
            <span class="w-28 tabular-nums">
              <strong>{{ row.gap === 0 ? 'Tied' : `${row.gap} vote apart` }}</strong>
            </span>
            <span class="grow text-sm text-ink/80">
              <template v-for="(release, index) in row.releases" :key="release.id">
                <template v-if="index">, </template>
                <RouterLink :to="`/editions/${release.id}`" class="underline">{{
                  release.title ?? `${release.owner}'s edition`
                }}</RouterLink>
                ({{ release.votes }})
              </template>
            </span>
            <RouterLink
              :to="`/tablets/${row.slug}`"
              class="inline-flex min-h-10 items-center rounded border border-ink/30 px-3 py-1.5 text-sm hover:bg-ink/5"
              data-testid="queue-action"
              >Vote</RouterLink
            >
          </li>
        </template>
      </ol>

      <p
        v-else-if="!LOADING && !ERROR && !META.missing_hint"
        class="mt-4 rounded border border-ink/15 bg-white p-4 text-ink/80"
        data-testid="queue-empty"
      >
        Nothing here right now.
      </p>

      <button
        v-if="TAB !== 'review' && ITEMS.length < TOTAL"
        type="button"
        class="mt-4 min-h-10 rounded border border-ink/30 px-4 py-2 hover:bg-ink/5"
        :disabled="LOADING"
        data-testid="queue-more"
        @click="load(true)"
      >
        {{ LOADING ? 'Loading…' : `Show more (${TOTAL - ITEMS.length} left)` }}
      </button>
    </section>
  </main>
</template>
