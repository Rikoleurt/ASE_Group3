<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'
const router = useRouter()
import FractionCheck from '../components/analysis/FractionCheck.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import ShareAnalysis from '../components/ShareAnalysis.vue'

const ALLOWED_TYPES = ['image/png', 'image/jpeg']
const STATUS = ref('idle')
const ERROR_MESSAGE = ref('')
const FILENAME = ref('')
const PREVIEW_URL = ref('')
const ANALYSIS = ref(null)
const IS_DRAGGING = ref(false)

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
                typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`,
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
        error instanceof TypeError ? 'Couldnt reach the server' : error.message
    }
}

// COMPONENT LOGIC

function handleFile(file) {

    if (!file) return

    if (!ALLOWED_TYPES.includes(file.type)) {
        ERROR_MESSAGE.value = 'Only PNG or JPG allowed'
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
    revokePreview()
    ANALYSIS.value = null
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
            <TabletOverlay :signs="ANALYSIS.signs" :formulas="ANALYSIS.formulas">
                <img :src="PREVIEW_URL" :alt="FILENAME" class="w-full rounded-lg bg-white" />
            </TabletOverlay>
        </div>

        <div class="rounded-3xl bg-card p-6 md:flex-1">
            <h2 class="text-2xl font-bold">Analysis</h2>
            <p class="mt-1 text-ink/70">{{ FILENAME }}</p>

            <p class="mt-4 leading-relaxed">{{ ANALYSIS.summary }}</p>

            <dl class="mt-6 divide-y divide-ink/10">
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Interpretation</dt>
                    <dd class="font-medium">{{ ANALYSIS.symbol_interpretation }}</dd>
                </div>
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Confidence</dt>
                    <dd class="font-medium">{{ ANALYSIS.confidence }}%</dd>
                </div>
                <div class="flex justify-between gap-4 py-2">
                    <dt class="text-ink/70">Processing time</dt>
                    <dd class="font-medium">{{ ANALYSIS.time_taken }} s</dd>
                </div>
            </dl>

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

    <FractionCheck v-if="STATUS === 'result'" :analysis="ANALYSIS" class="mt-8" />
</main>
</template>
