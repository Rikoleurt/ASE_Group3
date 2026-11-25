<script setup>
// Merge versions of a corpus tablet into a new edition (workbench, story D). The versions'
// boxes are matched into places (as on the compare page); for each place, choose whose box to
// keep, or leave it out. Defaults follow the majority; places where every version agrees need
// no attention, so only the differences are listed at first. The versions are in the URL
// (/tablets/HT-13/merge?v=scholar&v=copy:4).
import { useGlyphActivity } from '../composables/useGlyphActivity'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SignPreview from '../components/signs/SignPreview.vue'
import BoxCrop from '../components/versions/BoxCrop.vue'
import VersionOverlay from '../components/versions/VersionOverlay.vue'
import { majorityPicks, takeAllFrom } from '../components/versions/mergeDefaults'
import { STATUS_LABELS, VERSION_COLOURS, versionName } from '../components/versions/versions'
import { useCatalogue } from '../composables/useCatalogue'
import { sessionFetch } from '../state/session'
import '../components/analysis/linearA.css'

const route = useRoute()
const router = useRouter()
const CATALOGUE = useCatalogue()
const BY_SIGN = computed(() => Object.fromEntries(CATALOGUE.value.map((sign) => [sign.sign, sign])))
const RESULT = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
const PICKS = ref([])
const SELECTED = ref(null)
// Bubbles with new activity on places the scholars have a sign in (workbench, story I).
const { COUNTS: ACTIVITY, seen } = useGlyphActivity(computed(() => route.params.slug))
const BADGES = computed(() =>
  Object.fromEntries(
    (RESULT.value?.clusters ?? [])
      .map((place, index) => [index, ACTIVITY.value[place.members.scholar?.id]])
      .filter(([, count]) => count),
  ),
)
watch(SELECTED, (index) => seen(RESULT.value?.clusters[index]?.members.scholar?.id))
const ONLY_DIFFERENCES = ref(true)
const TITLE = ref('')
const SAVING = ref(false)
const SAVE_ERROR = ref('')
const TAKE = ref('')

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
const KEPT = computed(() => PICKS.value.filter((pick) => pick !== null).length)
const IMAGE = computed(() => (RESULT.value ? `/api${RESULT.value.image_url}` : ''))

let request = 0
async function load() {
  const mine = ++request
  RESULT.value = null
  PICKS.value = []
  SELECTED.value = null
  ERROR.value = ''
  SAVE_ERROR.value = ''
  LOADING.value = true
  try {
    const query = new URLSearchParams([].concat(route.query.v ?? []).map((key) => ['v', key]))
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
        typeof body?.detail === 'string' ? body.detail : 'The versions could not be loaded.',
      )
    RESULT.value = body
    PICKS.value = majorityPicks(
      body.clusters,
      body.versions.map((version) => version.key),
    )
    if (!TITLE.value) TITLE.value = `Edition of ${body.tablet}`
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

function pick(index, key) {
  PICKS.value = PICKS.value.map((value, at) => (at === index ? key : value))
  SELECTED.value = index
}

function takeAll() {
  if (TAKE.value) PICKS.value = takeAllFrom(RESULT.value.clusters, PICKS.value, TAKE.value)
}

function majority() {
  PICKS.value = majorityPicks(RESULT.value.clusters, KEYS.value)
}

async function create() {
  SAVING.value = true
  SAVE_ERROR.value = ''
  try {
    const sources = RESULT.value.versions.map((version) =>
      version.key.startsWith('copy:')
        ? { key: version.key, version: version.version }
        : { key: version.key },
    )
    const response = await sessionFetch('/api/box-sets/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tablet: route.params.slug,
        title: TITLE.value.trim() || null,
        sources,
        picks: PICKS.value,
      }),
    })
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    const body = await response.json().catch(() => null)
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The edition could not be created.',
      )
    await router.push(`/box-sets/${body.id}`)
  } catch (failure) {
    SAVE_ERROR.value =
      failure instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : failure.message
  } finally {
    SAVING.value = false
  }
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <RouterLink :to="`/tablets/${route.params.slug}`" class="underline"
      >← {{ RESULT?.tablet ?? route.params.slug.replaceAll('-', ' ') }}</RouterLink
    >
    <h1 class="mt-2 text-3xl font-bold">Merge into an edition</h1>
    <p class="mt-1 text-ink/70">
      Choose, place by place, whose box and sign to keep. The edition is yours to edit, share and
      propose; each box keeps the credit for where it came from.
    </p>

    <p v-if="LOADING" role="status" class="mt-6">
      Matching the versions' boxes… the model's first reading of a tablet can take half a minute.
    </p>
    <p v-else-if="ERROR" role="alert" class="mt-6 text-confidence-low">{{ ERROR }}</p>

    <template v-if="RESULT">
      <section class="mt-6 rounded-2xl bg-card p-4" aria-label="The edition">
        <div class="flex flex-wrap items-end gap-4">
          <label class="flex min-w-64 flex-1 flex-col text-sm font-semibold">
            Title
            <input
              v-model="TITLE"
              maxlength="120"
              class="mt-1 rounded border border-ink/30 bg-white px-3 py-1.5 font-normal"
              data-testid="merge-title"
            />
          </label>
          <p class="text-sm" data-testid="merge-summary">
            {{ KEPT }} of {{ PLACES.length }} places kept
          </p>
          <button
            type="button"
            class="cursor-pointer rounded bg-bar px-5 py-1.5 font-semibold hover:brightness-95 disabled:opacity-60"
            :disabled="SAVING || !KEPT"
            data-testid="create-edition"
            @click="create"
          >
            {{ SAVING ? 'Creating…' : 'Create the edition' }}
          </button>
        </div>
        <p v-if="SAVE_ERROR" role="alert" class="mt-2 text-confidence-low">
          {{ SAVE_ERROR }}
          <button
            v-if="SAVE_ERROR.includes('Reload')"
            type="button"
            class="ml-2 underline"
            @click="load"
          >
            Reload
          </button>
        </p>
        <ul class="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <li v-for="version in RESULT.versions" :key="version.key" class="flex items-center gap-2">
            <span
              class="inline-block h-3.5 w-6 rounded-sm border-[3px]"
              :style="{ borderColor: COLOUR(version.key) }"
              aria-hidden="true"
            />
            {{ NAMES[version.key] }}
          </li>
        </ul>
      </section>

      <div class="mt-6 flex flex-col gap-6 lg:flex-row">
        <div class="lg:w-1/2">
          <VersionOverlay
            :clusters="RESULT.clusters"
            :keys="KEYS"
            :selected="SELECTED"
            :badges="BADGES"
            @select="SELECTED = $event"
          >
            <img
              :src="IMAGE"
              :alt="`${RESULT.tablet} tracing`"
              class="w-full rounded-lg bg-white"
            />
          </VersionOverlay>
        </div>

        <section class="min-w-0 flex-1" aria-labelledby="places-h">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 id="places-h" class="text-xl font-bold">Places ({{ PLACES.length }})</h2>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="ONLY_DIFFERENCES" type="checkbox" data-testid="only-differences" />
              Only where they differ
            </label>
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <button
              type="button"
              class="cursor-pointer rounded border border-ink/30 px-2 py-1 hover:bg-bar"
              data-testid="majority"
              @click="majority"
            >
              Majority everywhere
            </button>
            <label class="sr-only" for="take-all">Take every box from</label>
            <select
              id="take-all"
              v-model="TAKE"
              class="rounded border border-ink/30 bg-white px-2 py-1"
              data-testid="take-from"
            >
              <option value="">Take every box from…</option>
              <option v-for="version in RESULT.versions" :key="version.key" :value="version.key">
                {{ NAMES[version.key] }}
              </option>
            </select>
            <button
              type="button"
              class="cursor-pointer rounded border border-ink/30 px-2 py-1 hover:bg-bar disabled:opacity-50"
              :disabled="!TAKE"
              data-testid="take-all"
              @click="takeAll"
            >
              Apply
            </button>
          </div>
          <p v-if="!SHOWN.length" class="mt-3 text-sm">
            {{
              PLACES.length
                ? 'The versions agree everywhere: every place keeps the shared box.'
                : 'No boxes in these versions.'
            }}
          </p>
          <ol class="mt-2 max-h-[70vh] overflow-auto">
            <li
              v-for="place in SHOWN"
              :key="place.index"
              class="rounded-lg px-2 py-2"
              :class="{ 'bg-bar/60': SELECTED === place.index }"
              data-testid="merge-place"
            >
              <fieldset>
                <legend class="flex items-center gap-2 text-sm">
                  <button
                    type="button"
                    class="cursor-pointer font-semibold underline-offset-2 hover:underline"
                    @click="SELECTED = place.index"
                  >
                    Place {{ place.index + 1 }}
                  </button>
                  <span
                    class="rounded px-1.5 text-xs font-semibold"
                    :class="
                      place.status === 'agree'
                        ? 'bg-confidence-high/20'
                        : place.status === 'differs'
                          ? 'bg-confidence-low/20'
                          : 'bg-ink/10'
                    "
                    >{{ STATUS_LABELS[place.status] }}</span
                  >
                </legend>
                <div class="mt-1 flex flex-wrap gap-2">
                  <label
                    v-for="key in KEYS.filter((k) => place.members[k])"
                    :key="key"
                    class="flex cursor-pointer items-center gap-2 rounded border-2 bg-white/70 p-1 pr-2 text-sm"
                    :class="PICKS[place.index] === key ? 'border-ink' : 'border-transparent'"
                    data-testid="merge-option"
                  >
                    <input
                      type="radio"
                      class="sr-only"
                      :name="`place-${place.index}`"
                      :checked="PICKS[place.index] === key"
                      @change="pick(place.index, key)"
                    />
                    <BoxCrop
                      :image-url="IMAGE"
                      :width="RESULT.width"
                      :height="RESULT.height"
                      :box="place.members[key].box"
                      :colour="COLOUR(key)"
                      :size="56"
                    />
                    <span>
                      <span class="flex items-center gap-1">
                        <SignPreview
                          v-if="place.members[key].sign"
                          :sign="place.members[key].sign"
                          :glyph="BY_SIGN[place.members[key].sign]?.glyph ?? ''"
                          :preview-url="
                            BY_SIGN[place.members[key].sign]?.preview_url ??
                            `/glyphs/${place.members[key].sign}/preview.png`
                          "
                          :size="22"
                        />
                        <span class="font-semibold">{{
                          place.members[key].label ?? 'No sign'
                        }}</span>
                      </span>
                      <span class="block text-xs text-ink/60">{{ NAMES[key] }}</span>
                    </span>
                  </label>
                  <label
                    class="flex cursor-pointer items-center rounded border-2 bg-white/70 px-2 text-sm"
                    :class="PICKS[place.index] === null ? 'border-ink' : 'border-transparent'"
                    data-testid="merge-leave-out"
                  >
                    <input
                      type="radio"
                      class="sr-only"
                      :name="`place-${place.index}`"
                      :checked="PICKS[place.index] === null"
                      @change="pick(place.index, null)"
                    />
                    Leave out
                  </label>
                </div>
              </fieldset>
            </li>
          </ol>
        </section>
      </div>
    </template>
  </main>
</template>
