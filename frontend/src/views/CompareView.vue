<script setup>
// Compare versions of a corpus tablet (workbench, story C): the scholars', the model's and
// corrected copies, each in its own colour on the tablet. Their boxes are matched into places;
// each place agrees, has different signs, or is missing from some versions. The versions are in
// the URL (/tablets/HT-13/compare?v=scholar&v=copy:4).
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SignPreview from '../components/signs/SignPreview.vue'
import VersionOverlay from '../components/versions/VersionOverlay.vue'
import { STATUS_LABELS, VERSION_COLOURS, versionName } from '../components/versions/versions'
import { useCatalogue } from '../composables/useCatalogue'
import '../components/analysis/linearA.css'

const route = useRoute()
const router = useRouter()
const CATALOGUE = useCatalogue()
const BY_SIGN = computed(() => Object.fromEntries(CATALOGUE.value.map((sign) => [sign.sign, sign])))
const RESULT = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
const SELECTED = ref(null)
const ONLY_DIFFERENCES = ref(false)
const HIDDEN = ref([])

const KEYS = computed(() => RESULT.value?.versions.map((version) => version.key) ?? [])
const NAMES = computed(() =>
  Object.fromEntries(
    (RESULT.value?.versions ?? []).map((version) => [version.key, versionName(version)]),
  ),
)
const COLOUR = (key) => VERSION_COLOURS[KEYS.value.indexOf(key) % VERSION_COLOURS.length]
const PLACES = computed(() =>
  (RESULT.value?.clusters ?? []).map((place, index) => ({ ...place, index })),
)
const SHOWN = computed(() =>
  PLACES.value.filter(
    (place) => !ONLY_DIFFERENCES.value || place.status !== 'agree' || place.moved,
  ),
)
const MOVED = computed(() => PLACES.value.filter((place) => place.moved).length)
const COUNTS = computed(() =>
  PLACES.value.reduce(
    (counts, place) => ({ ...counts, [place.status]: (counts[place.status] ?? 0) + 1 }),
    {},
  ),
)

let request = 0
async function load() {
  const mine = ++request
  const wanted = [].concat(route.query.v ?? [])
  RESULT.value = null
  SELECTED.value = null
  ERROR.value = ''
  LOADING.value = true
  try {
    const query = new URLSearchParams(wanted.map((key) => ['v', key]))
    const response = await fetch(
      `/api/tablets/${encodeURIComponent(route.params.slug)}/compare?${query}`,
    )
    if (mine !== request) return
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    const body = await response.json().catch(() => null)
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The versions could not be compared.',
      )
    RESULT.value = body
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
watch(() => route.fullPath, load, { immediate: true })

function percent(pair) {
  return pair.total ? `${Math.round((pair.same / pair.total) * 100)}%` : '—'
}

function missingFrom(place) {
  return KEYS.value
    .filter((key) => !place.members[key])
    .map((key) => NAMES.value[key])
    .join(', ')
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <RouterLink :to="`/tablets/${route.params.slug}`" class="underline"
      >← {{ RESULT?.tablet ?? route.params.slug.replaceAll('-', ' ') }}</RouterLink
    >
    <h1 class="mt-2 text-3xl font-bold">
      Compare versions{{ RESULT ? ` of ${RESULT.tablet}` : '' }}
    </h1>

    <p v-if="LOADING" role="status" class="mt-6">
      Matching the versions' boxes… the model's first reading of a tablet can take half a minute.
    </p>
    <p v-else-if="ERROR" role="alert" class="mt-6 text-confidence-low">{{ ERROR }}</p>

    <template v-if="RESULT">
      <section class="mt-6 rounded-2xl bg-card p-4" aria-labelledby="legend-h">
        <h2 id="legend-h" class="sr-only">Versions</h2>
        <ul class="flex flex-wrap gap-x-6 gap-y-2">
          <li
            v-for="version in RESULT.versions"
            :key="version.key"
            class="flex items-center gap-2"
            data-testid="legend"
          >
            <input
              :id="`show-${version.key}`"
              v-model="HIDDEN"
              type="checkbox"
              :value="version.key"
              class="peer sr-only"
            />
            <label
              :for="`show-${version.key}`"
              class="flex cursor-pointer items-center gap-2"
              :class="{ 'opacity-40': HIDDEN.includes(version.key) }"
            >
              <span
                class="inline-block h-3.5 w-6 rounded-sm border-[3px]"
                :style="{ borderColor: COLOUR(version.key) }"
                aria-hidden="true"
              />
              {{ NAMES[version.key] }}
              <span class="text-sm text-ink/60">({{ version.box_count }})</span>
              <span class="sr-only">{{
                HIDDEN.includes(version.key)
                  ? '(hidden; select to show)'
                  : '(shown; select to hide)'
              }}</span>
            </label>
          </li>
        </ul>
        <table class="mt-3 text-sm" data-testid="agreement">
          <caption class="text-left font-semibold">
            How often they agree
          </caption>
          <tbody>
            <tr v-for="pair in RESULT.agreement" :key="`${pair.a}|${pair.b}`">
              <td class="pr-3">{{ NAMES[pair.a] }} and {{ NAMES[pair.b] }}</td>
              <td class="pr-2 text-right font-semibold">{{ percent(pair) }}</td>
              <td class="text-ink/60">{{ pair.same }} of {{ pair.total }} places</td>
            </tr>
          </tbody>
        </table>
      </section>

      <div class="mt-6 flex flex-col gap-6 lg:flex-row">
        <div class="lg:w-3/5">
          <VersionOverlay
            :clusters="RESULT.clusters"
            :keys="KEYS"
            :hidden="HIDDEN"
            :selected="SELECTED"
            @select="SELECTED = $event"
          >
            <img
              :src="`/api${RESULT.image_url}`"
              :alt="`${RESULT.tablet} tracing`"
              class="w-full rounded-lg bg-white"
            />
          </VersionOverlay>
        </div>

        <section class="min-w-0 flex-1" aria-labelledby="places-h">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="places-h" class="text-xl font-bold">Places ({{ PLACES.length }})</h2>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="ONLY_DIFFERENCES" type="checkbox" data-testid="only-differences" />
              Only where they differ
            </label>
          </div>
          <p class="text-sm text-ink/70" data-testid="counts">
            {{ COUNTS.agree ?? 0 }} agree · {{ COUNTS.differs ?? 0 }} with different signs ·
            {{ COUNTS.missing ?? 0 }} missing from some<template v-if="MOVED">
              · {{ MOVED }} with boxes in different places</template
            >
          </p>
          <ol class="mt-2 max-h-[70vh] overflow-auto">
            <li v-for="place in SHOWN" :key="place.index">
              <button
                type="button"
                class="w-full cursor-pointer rounded-lg px-2 py-2 text-left hover:bg-bar"
                :class="{ 'bg-bar': SELECTED === place.index }"
                :aria-pressed="SELECTED === place.index"
                data-testid="place-row"
                @click="SELECTED = place.index"
              >
                <span class="flex items-center gap-2 text-sm">
                  <span class="font-semibold">{{ place.index + 1 }}.</span>
                  <span
                    class="rounded px-1.5 text-xs font-semibold"
                    :class="
                      place.status === 'agree'
                        ? 'bg-confidence-high/20'
                        : place.status === 'differs'
                          ? 'bg-confidence-low/20'
                          : 'bg-ink/10'
                    "
                    data-testid="place-status"
                    >{{ STATUS_LABELS[place.status] }}</span
                  >
                  <span v-if="place.moved" class="text-xs text-ink/60">boxes differ in place</span>
                </span>
                <span class="mt-1 flex flex-wrap gap-2">
                  <span
                    v-for="key in KEYS"
                    :key="key"
                    class="flex items-center gap-1 rounded border-l-4 bg-white/60 py-0.5 pr-2 pl-1 text-sm"
                    :style="{ borderColor: COLOUR(key) }"
                  >
                    <template v-if="place.members[key]">
                      <SignPreview
                        v-if="place.members[key].sign"
                        :sign="place.members[key].sign"
                        :glyph="BY_SIGN[place.members[key].sign]?.glyph ?? ''"
                        :preview-url="
                          BY_SIGN[place.members[key].sign]?.preview_url ??
                          `/glyphs/${place.members[key].sign}/preview.png`
                        "
                        :size="24"
                      />
                      {{ place.members[key].label ?? 'No sign' }}
                    </template>
                    <span v-else class="text-ink/50">none</span>
                  </span>
                </span>
                <span v-if="place.status === 'missing'" class="mt-1 block text-xs text-ink/60"
                  >Not in: {{ missingFrom(place) }}</span
                >
              </button>
            </li>
          </ol>
          <p v-if="!SHOWN.length" class="mt-2 text-sm">
            {{ PLACES.length ? 'The versions agree everywhere.' : 'No boxes in these versions.' }}
          </p>
        </section>
      </div>
    </template>
  </main>
</template>
