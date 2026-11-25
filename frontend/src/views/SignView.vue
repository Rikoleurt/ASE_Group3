<script setup>
// One sign (workbench, story B): its typical drawing, character and reading, and its occurrences
// across the corpus, most typical first, each linking to its tablet.
import DiscussionLinks from '../components/DiscussionLinks.vue'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import SignPreview from '../components/signs/SignPreview.vue'
import { useCatalogue } from '../composables/useCatalogue'
import '../components/analysis/linearA.css'

const route = useRoute()
const CATALOGUE = useCatalogue()
const SIGN = computed(() => String(route.params.sign))
const ENTRY = computed(() => CATALOGUE.value.find((entry) => entry.sign === SIGN.value) ?? null)
const PAGE = ref(null)
const ERROR = ref('')
const LOADING = ref(false)
// Pictures that failed to load: an occurrence falls back from its crop to its tablet's thumbnail,
// then to a placeholder when that tablet's drawing is not on this server either.
const FAILED = ref(new Map())
const LIMIT = 60

let request = 0
async function load() {
  const mine = ++request
  PAGE.value = null
  ERROR.value = ''
  FAILED.value = new Map()
  LOADING.value = true
  try {
    const response = await fetch(
      `/api/glyphs/${encodeURIComponent(SIGN.value)}/occurrences?limit=${LIMIT}`,
    )
    if (mine !== request) return
    const body = await response.json().catch(() => null)
    if (response.status === 404) PAGE.value = { total: 0, items: [] }
    else if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The occurrences could not be loaded.',
      )
    else PAGE.value = body
  } catch (failure) {
    if (mine === request)
      ERROR.value =
        failure instanceof TypeError
          ? "Couldn't reach the server. Check your connection and try again."
          : failure.message
  } finally {
    if (mine === request) LOADING.value = false
  }
}
watch(SIGN, load, { immediate: true })

const TABLETS = computed(() => [
  ...new Map((PAGE.value?.items ?? []).map((item) => [item.tablet, item.title])).entries(),
])
const failures = (item) => (FAILED.value.get(item) ?? 0) + (item.crop_url ? 0 : 1)
const picture = (item) => [item.crop_url, item.thumbnail_url][failures(item)] ?? null
function failed(item) {
  FAILED.value = new Map([...FAILED.value, [item, (FAILED.value.get(item) ?? 0) + 1]])
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <RouterLink to="/signs" class="underline">← Find a sign</RouterLink>
    <div class="mt-3 flex flex-wrap items-center gap-4">
      <SignPreview
        :sign="SIGN"
        :glyph="ENTRY?.glyph ?? ''"
        :preview-url="ENTRY?.preview_url ?? `/glyphs/${SIGN}/preview.png`"
        :size="96"
      />
      <div>
        <h1 class="text-3xl font-bold">
          <span v-if="ENTRY?.glyph" class="linear-a mr-2" aria-hidden="true">{{ ENTRY.glyph }}</span
          >{{ SIGN }}
        </h1>
        <p class="text-lg text-ink/80" data-testid="sign-name">
          <template v-if="ENTRY?.reading">Reading: {{ ENTRY.reading }}</template>
          <template v-else-if="ENTRY && ENTRY.name !== SIGN">{{ ENTRY.name }}</template>
          <template v-else-if="!ENTRY && CATALOGUE.length">Not in the sign catalogue.</template>
        </p>
      </div>
    </div>

    <DiscussionLinks class="max-w-xl" :target="`sign:${SIGN}`" :label="ENTRY?.name ?? SIGN" />
    <p v-if="LOADING" role="status" class="mt-6">Loading the occurrences…</p>
    <p v-else-if="ERROR" role="alert" class="mt-6 text-confidence-low">{{ ERROR }}</p>
    <template v-else-if="PAGE">
      <h2 class="mt-8 text-xl font-bold" data-testid="occurrence-count">
        {{
          PAGE.total
            ? `${PAGE.total} occurrence${PAGE.total === 1 ? '' : 's'} in the corpus`
            : 'No occurrences in the corpus'
        }}
      </h2>
      <p v-if="PAGE.total > PAGE.items.length" class="text-sm text-ink/70">
        The {{ PAGE.items.length }} most typical are shown.
      </p>
      <ul
        class="mt-3 grid grid-cols-[repeat(auto-fill,minmax(7rem,1fr))] gap-2"
        data-testid="occurrences"
      >
        <li v-for="item in PAGE.items" :key="`${item.tablet}-${item.position}`">
          <RouterLink
            :to="`/tablets/${item.tablet}`"
            class="block rounded-lg bg-card p-2 text-center hover:bg-bar"
          >
            <img
              v-if="picture(item)"
              :src="`/api${picture(item)}`"
              :alt="`${SIGN} on ${item.title}`"
              loading="lazy"
              class="mx-auto h-20 w-full rounded bg-white object-contain"
              @error="failed(item)"
            />
            <span
              v-else
              class="flex h-20 items-center justify-center rounded bg-white/60 text-xs text-ink/60"
              data-testid="no-drawing"
              >Drawing not downloaded</span
            >
            <span class="mt-1 block text-sm">{{ item.title }}</span>
            <span v-if="item.outlier" class="block text-xs text-confidence-low">unusual form</span>
          </RouterLink>
        </li>
      </ul>
      <section v-if="TABLETS.length" class="mt-6" aria-labelledby="tablets-h">
        <h2 id="tablets-h" class="font-bold">Tablets</h2>
        <p class="mt-1 flex flex-wrap gap-x-3 gap-y-1">
          <RouterLink
            v-for="[slug, title] in TABLETS"
            :key="slug"
            :to="`/tablets/${slug}`"
            class="underline"
            >{{ title }}</RouterLink
          >
        </p>
      </section>
    </template>
  </main>
</template>
