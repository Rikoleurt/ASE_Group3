<script setup>
// Lets the user correct the sign selected on the tablet: pick the right sign from
// the catalogue, or flag the reading as uncertain. A reviewer checks every
// submission before it becomes training data; the saved analysis is not changed.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { sessionFetch } from '../../state/session'
import SignPreview from '../signs/SignPreview.vue'
import { searchSigns } from '../signs/signSearch'
import './linearA.css'

const props = defineProps({
  sign: { type: Object, required: true },
  analysisId: { type: Number, required: true },
  catalogue: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])

const PROPOSED = ref('')
const NOTE = ref('')
const PENDING = ref(false)
const ERROR = ref('')
const SAVED = ref(null)
const ROOT = ref(null)

// The form opens below the tablet: bring it into view for the sign just clicked.
function reveal() {
  nextTick(() => ROOT.value?.scrollIntoView?.({ block: 'nearest' }))
}

onMounted(reveal)
watch(() => props.sign.id, () => {
  PROPOSED.value = ''
  NOTE.value = ''
  ERROR.value = ''
  SAVED.value = null
  reveal()
})

const MATCH = computed(() => {
  const wanted = PROPOSED.value.trim().toLowerCase()
  return props.catalogue.find((entry) => entry.sign.toLowerCase() === wanted) ?? null
})
// Suggestions while typing a reading, number or name; hidden once a sign is chosen exactly.
const SUGGESTIONS = computed(() => (MATCH.value ? [] : searchSigns(props.catalogue, PROPOSED.value, 8)))

async function submit(uncertain) {
  if (PENDING.value) return
  if (!uncertain && !MATCH.value) {
    ERROR.value = 'Choose a sign from the list.'
    return
  }
  PENDING.value = true
  ERROR.value = ''
  const signId = props.sign.id // the reply is for this sign, even if another is picked meanwhile
  try {
    const payload = { sign_id: signId, note: NOTE.value.trim() || null }
    if (uncertain) payload.uncertain = true
    else payload.proposed_sign = MATCH.value.sign
    const response = await sessionFetch(`/api/analysis/${props.analysisId}/corrections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const body = await response.json().catch(() => null)
    if (signId !== props.sign.id) return
    if (!response.ok) {
      throw new Error(typeof body?.detail === 'string' ? body.detail : 'Something went wrong on the server. Please try again.')
    }
    SAVED.value = body
  } catch (error) {
    if (signId !== props.sign.id) return
    ERROR.value = error instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : error.message
  } finally {
    PENDING.value = false
  }
}
</script>

<template>
  <section ref="ROOT" class="rounded-3xl bg-card p-6" aria-labelledby="correction-title" data-testid="sign-correction">
    <div class="flex items-start justify-between gap-4">
      <h3 id="correction-title" class="text-xl font-bold">Correct this sign</h3>
      <button type="button" class="cursor-pointer text-sm underline" @click="emit('close')">Close</button>
    </div>

    <div class="mt-4 flex items-center gap-4">
      <img
        v-if="sign.crop"
        :src="sign.crop"
        alt="The selected region of the tablet"
        class="h-20 w-20 rounded-lg bg-white object-contain"
        data-testid="correction-crop"
      />
      <div>
        <p class="text-ink/80">The model read</p>
        <p class="text-lg font-bold" data-testid="correction-original">
          <span v-if="sign.glyph" class="linear-a mr-1">{{ sign.glyph }}</span>{{ sign.label }}
        </p>
        <p class="text-sm text-ink/80">{{ Math.round(sign.confidence) }}% confident</p>
      </div>
    </div>

    <p v-if="SAVED" role="status" class="mt-6 rounded-lg bg-accent/10 p-3" data-testid="correction-saved">
      Thank you, your {{ SAVED.uncertain ? 'flag' : 'correction' }} was saved. A reviewer will check it before it is
      used to train the model.
    </p>

    <form v-else class="mt-6 flex flex-col gap-3" @submit.prevent="submit(false)">
      <label for="proposed-sign" class="font-semibold">Correct sign</label>
      <div class="flex items-center gap-3">
        <input
          id="proposed-sign"
          v-model="PROPOSED"
          autocomplete="off"
          placeholder="AB81, ku, VIN…"
          class="min-w-0 flex-1 rounded border border-ink/30 bg-page px-3 py-1.5"
          @keydown.enter.prevent="SUGGESTIONS.length === 1 ? (PROPOSED = SUGGESTIONS[0].sign) : submit(false)"
        />
        <span v-if="MATCH" class="flex items-center gap-2" data-testid="correction-choice">
          <SignPreview :sign="MATCH.sign" :glyph="MATCH.glyph" :preview-url="MATCH.preview_url" :size="40" />
          <span><span class="font-semibold">{{ MATCH.sign }}</span> <span v-if="MATCH.reading" class="text-ink/80">{{ MATCH.reading }}</span></span>
        </span>
      </div>
      <ul v-if="SUGGESTIONS.length" class="max-h-56 overflow-auto rounded border border-ink/15 bg-white" data-testid="correction-suggestions">
        <li v-for="entry in SUGGESTIONS" :key="entry.sign">
          <button type="button" class="flex w-full cursor-pointer items-center gap-3 px-2 py-1 text-left hover:bg-bar" @click="PROPOSED = entry.sign">
            <SignPreview :sign="entry.sign" :glyph="entry.glyph" :preview-url="entry.preview_url" :size="36" />
            <span v-if="entry.preview_url" class="linear-a text-xl" aria-hidden="true">{{ entry.glyph }}</span>
            <span><span class="font-semibold">{{ entry.sign }}</span> <span v-if="entry.reading" class="text-ink/80">{{ entry.reading }}</span></span>
          </button>
        </li>
      </ul>

      <label for="correction-note" class="font-semibold">Note <span class="font-normal text-ink/80">(optional)</span></label>
      <textarea
        id="correction-note"
        v-model="NOTE"
        maxlength="500"
        rows="2"
        class="rounded border border-ink/30 bg-page px-3 py-1.5"
      />

      <p v-if="ERROR" role="alert" class="text-conf-low">{{ ERROR }}</p>

      <div class="flex flex-wrap gap-3">
        <button type="submit" :disabled="PENDING" class="cursor-pointer rounded bg-bar px-6 py-1.5 font-medium hover:brightness-95 disabled:opacity-60">
          Submit correction
        </button>
        <button type="button" :disabled="PENDING" class="cursor-pointer rounded border border-ink/30 px-6 py-1.5 hover:bg-ink/5 disabled:opacity-60" @click="submit(true)">
          Not sure: flag as uncertain
        </button>
      </div>
    </form>
  </section>
</template>
