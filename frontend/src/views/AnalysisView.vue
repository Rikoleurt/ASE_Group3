<script setup>
import { computed, ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'
const router = useRouter()
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import ShareAnalysis from '../components/ShareAnalysis.vue'
import GlyphOccurrencesPane from '../components/glyphs/GlyphOccurrencesPane.vue'
import SignCorrection from '../components/analysis/SignCorrection.vue'
import { openCopy } from '../composables/useBoxSet'
import SymbolDiscussionDialog from '../components/SymbolDiscussionDialog.vue'

const ALLOWED_TYPES = ['image/png', 'image/jpeg']
const STATUS = ref('idle')
const ERROR_MESSAGE = ref('')
const FILENAME = ref('')
const PREVIEW_URL = ref('')
const ANALYSIS = ref(null)
const IS_DRAGGING = ref(false)
const SELECTED = ref(null)
// The box the reader clicked: its sign, the reader's other guesses and the crop to compare with the corpus.
const SELECTION = computed(() => SELECTED.value?.sign ? {
    sign: SELECTED.value.sign,
    candidates: SELECTED.value.candidates,
    crop: SELECTED.value.crop || null,
} : null)
const CATALOGUE = ref([])
const OPENING = ref(false)
const OPEN_ERROR = ref('')

async function correctBoxes() {
    OPENING.value = true
    OPEN_ERROR.value = ''
    try {
        await router.push(`/box-sets/${await openCopy(ANALYSIS.value.analysis_id)}`)
    } catch (error) {
        OPEN_ERROR.value = error instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : error.message
    } finally {
        OPENING.value = false
    }
}

const SELECTED_SYMBOL = ref(null)

function openSymbolDiscussion(symbol) {
    SELECTED_SYMBOL.value = symbol
}

// ROUTE

async function analyze(file) {
    STATUS.value = 'processing'
    try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await sessionFetch('/api/analysis', { method: 'POST', body: formData })

        if (response.status === 401) {
            await router.push({ path: '/login', query: { redirect: '/analysis' } })
            return
        }
        if (!response.ok) {
            const body = await response.json().catch(() => null)
            throw new Error(
                typeof body?.detail === 'string' ? body.detail : 'Something went wrong on the server. Please try again.',
            )
        }

        ANALYSIS.value = await response.json()
        STATUS.value = 'result'
    } catch (error) {
        if (error.status === 401) {
            await router.push({ path: '/login', query: { redirect: '/analysis' } })
        }
        STATUS.value = 'idle'
        ERROR_MESSAGE.value =
        error instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : error.message
    }
}

async function loadCatalogue() {
    if (CATALOGUE.value.length) return
    try {
        const response = await fetch('/api/corrections/catalogue')
        if (response.ok) CATALOGUE.value = await response.json()
    } catch {
        // The form still explains that a sign must come from the list.
    }
}

function selectSign(sign) {
    SELECTED.value = sign
    loadCatalogue()
}

// COMPONENT LOGIC

function handleFile(file) {

    if (!file) return

    if (!ALLOWED_TYPES.includes(file.type)) {
        ERROR_MESSAGE.value = 'Only PNG or JPEG images can be analysed.'
        return
    }

    ERROR_MESSAGE.value = ''
    revokePreview()
    FILENAME.value = file.name
    PREVIEW_URL.value = URL.createObjectURL(file)
    analyze(file)
}

function onDrop(event) {
  IS_DRAGGING.value = false
  handleFile(event.dataTransfer.files[0])
}

function onDragLeave(event) {
  if (event.currentTarget.contains(event.relatedTarget)) return
  IS_DRAGGING.value = false
}

function onInputChange(event) {
    handleFile(event.target.files[0])
    event.target.value = ''
}

function reset() {
    SELECTED_SYMBOL.value = null
    revokePreview()
    ANALYSIS.value = null
    SELECTED.value = null
    FILENAME.value = ''
    ERROR_MESSAGE.value = ''
    STATUS.value = 'idle'
}

function revokePreview() {
    if (PREVIEW_URL.value) {
        URL.revokeObjectURL(PREVIEW_URL.value)
        PREVIEW_URL.value = ''
    }
}

function round(value, decimals) {
    return Number(Math.round(value+'e'+decimals)+'e-'+decimals);
}

onBeforeUnmount(revokePreview)
</script>

<template>
<main class="mx-auto max-w-5xl px-6 py-10">
    <section v-if="STATUS === 'idle'" class="mx-auto max-w-2xl">
    <div
    class="flex flex-col items-center gap-4 rounded-3xl border-2 border-dashed px-6 py-16 text-center transition-colors"
    :class="IS_DRAGGING ? 'border-accent bg-accent/10' : 'border-ink/60 bg-card'"
    @dragover.prevent="IS_DRAGGING = true"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
    >
        <svg
        class="h-16 w-16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        >
            <path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>

        <h1 class="text-2xl font-bold">Upload File</h1>
        <p class="text-ink/70">Drag an image here, or</p>

        <label
        class="cursor-pointer rounded bg-bar px-8 py-1.5 font-medium hover:brightness-95 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent"
        >
            Browse
            <input type="file" accept="image/png,image/jpeg" class="sr-only" @change="onInputChange" />
        </label>

        <p v-if="ERROR_MESSAGE" role="alert" class="text-conf-low">
            {{ ERROR_MESSAGE }}
        </p>
    </div>
    </section>

    <section
      v-else-if="STATUS === 'processing'"
      class="flex flex-col items-center gap-6 py-24 text-center"
      role="status"
    >
        <div class="h-14 w-14 animate-spin rounded-full border-4 border-ink/20 border-t-accent"/><div>
        <p class="text-xl font-bold">Analyzing your image…</p>
        <p class="mt-1 text-ink/70">{{ FILENAME }}</p>
        </div>
    </section>

    <section v-else-if="STATUS === 'result'" class="flex flex-col gap-8 md:flex-row">
        <div class="md:w-1/2">
            <TabletOverlay :signs="ANALYSIS.signs" :formulas="ANALYSIS.formulas" :selected-id="SELECTED?.id ?? null" :can-discuss="Boolean(ANALYSIS.analysis_id)" @select="selectSign" @discuss="openSymbolDiscussion">
                <img :src="PREVIEW_URL" :alt="FILENAME" class="w-full rounded-lg bg-white" />
            </TabletOverlay>
        </div>

        <div class="rounded-3xl bg-card p-6 md:flex-1">
            <h2 class="text-2xl font-bold">Analysis</h2>
            <p class="mt-1 text-ink/70">{{ FILENAME }}</p>

            <p class="mt-4 leading-relaxed">{{ ANALYSIS.summary }}</p>

            <dl class="mt-6 divide-y divide-ink/10">
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Transliteration</dt>
                    <dd class="font-medium">{{ ANALYSIS.symbol_interpretation }}</dd>
                </div>
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Confidence</dt>
                    <dd class="font-medium">{{ round(ANALYSIS.confidence, 2) }}%</dd>
                </div>
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Processing time</dt>
                    <dd class="font-medium">{{ ANALYSIS.time_taken }} s</dd>
                </div>
            </dl>

            <p v-if="ANALYSIS.trained && ANALYSIS.signs.length" class="mt-6 text-sm text-ink/70">Is a sign misread? Click its box to suggest the right sign to a reviewer.</p>
            <button
            v-if="ANALYSIS.trained && ANALYSIS.analysis_id"
            type="button"
            class="mt-6 block cursor-pointer rounded bg-bar px-5 py-1.5 font-semibold hover:brightness-95 disabled:opacity-60"
            :disabled="OPENING"
            data-testid="correct-boxes"
            @click="correctBoxes"
            >
                {{ OPENING ? 'Opening…' : 'Correct the boxes' }}
            </button>
            <p v-if="OPEN_ERROR" role="alert" class="mt-2 text-confidence-low">{{ OPEN_ERROR }}</p>
            <RouterLink v-if="ANALYSIS.analysis_id" :to="`/profile/history/${ANALYSIS.analysis_id}`" class="mt-6 inline-block underline">Saved in your history →</RouterLink>
            <ShareAnalysis v-if="ANALYSIS.analysis_id" :analysis-id="ANALYSIS.analysis_id" :filename="FILENAME" />
            <button
            type="button"
            class="mx-auto mt-8 block cursor-pointer rounded bg-bar px-6 py-1.5 hover:brightness-95"
            @click="reset"
            >
                Analyze another image
            </button>
        </div>
    </section>

    <SignCorrection
    v-if="STATUS === 'result' && ANALYSIS.trained && SELECTED && ANALYSIS.analysis_id"
    :sign="SELECTED"
    :analysis-id="ANALYSIS.analysis_id"
    :catalogue="CATALOGUE"
    class="mt-8"
    @close="SELECTED = null"
    />

    <FractionCheck v-if="STATUS === 'result'" :analysis="ANALYSIS" class="mt-8" />
    <GlyphOccurrencesPane v-if="STATUS === 'result'" :selection="SELECTION" class="mt-8" />
    <SymbolDiscussionDialog v-if="SELECTED_SYMBOL && ANALYSIS?.analysis_id" :analysis-id="ANALYSIS.analysis_id" :filename="FILENAME" :symbol="SELECTED_SYMBOL" @close="SELECTED_SYMBOL = null" />
</main>
</template>
