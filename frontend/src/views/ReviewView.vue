<script setup>
// Reviewers decide which sign corrections become training labels (#52). Corrections
// of the same sign are grouped, so conflicting proposals are compared side by side.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'
import '../components/analysis/linearA.css'

const STATUSES = [
  { value: 'pending', label: 'To review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

const router = useRouter()
const STATUS = ref('pending')
const ITEMS = ref([])
const GLYPHS = ref({})
const LOADING = ref(false)
const ERROR = ref('')
const FORBIDDEN = ref(false)
const NOTICE = ref('')
const ITEM_ERRORS = ref({})
const DECIDING = ref(null)
const EXPORTING = ref(false)
const date = (value) => new Date(value).toLocaleString()

// One group per detected sign, in queue order.
const GROUPS = computed(() => {
  const groups = new Map()
  for (const item of ITEMS.value) {
    const key = `${item.analysis_id}-${item.sign_id}`
    if (!groups.has(key)) groups.set(key, { key, first: item, items: [] })
    groups.get(key).items.push(item)
  }
  return [...groups.values()].map((group) => ({
    ...group,
    conflicting: new Set(group.items.map((item) => item.proposed_sign ?? 'uncertain')).size > 1,
  }))
})

function proposal(item) {
  return item.uncertain ? 'Flagged as uncertain' : item.proposed_sign
}

async function loadGlyphs() {
  try {
    const response = await fetch('/api/corrections/catalogue')
    if (response.ok) GLYPHS.value = Object.fromEntries((await response.json()).map((sign) => [sign.sign, sign.glyph]))
  } catch {
    // Glyphs only decorate the sign IDs.
  }
}

async function load() {
  LOADING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/corrections?status=${STATUS.value}&limit=200`)
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: '/review' } })
      return
    }
    if (response.status === 403) {
      FORBIDDEN.value = true
      return
    }
    if (!response.ok) throw new Error('The corrections could not be loaded. Please try again.')
    ITEMS.value = await response.json()
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
  } finally {
    LOADING.value = false
  }
}

function show(status) {
  if (status === STATUS.value) return
  STATUS.value = status
  NOTICE.value = ''
  ITEM_ERRORS.value = {}
  ITEMS.value = []
  load()
}

async function decide(item, decision) {
  if (DECIDING.value) return
  DECIDING.value = item.id
  ITEM_ERRORS.value = { ...ITEM_ERRORS.value, [item.id]: '' }
  try {
    const response = await sessionFetch(`/api/corrections/${item.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    })
    const body = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`)
    }
    ITEMS.value = ITEMS.value.filter((other) => other.id !== item.id)
    NOTICE.value = `${decision === 'approved' ? 'Approved' : 'Rejected'}: ${proposal(item)} for sign ${item.sign_id} of analysis ${item.analysis_id}.`
  } catch (failure) {
    ITEM_ERRORS.value = { ...ITEM_ERRORS.value, [item.id]: failure instanceof TypeError ? 'Couldnt reach the server' : failure.message }
  } finally {
    DECIDING.value = null
  }
}

async function exportApproved() {
  if (EXPORTING.value) return
  EXPORTING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch('/api/corrections/export')
    if (!response.ok) throw new Error('The export failed. Please try again.')
    const url = URL.createObjectURL(new Blob([JSON.stringify(await response.json(), null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'sign-corrections.json'
    link.click()
    URL.revokeObjectURL(url)
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
  } finally {
    EXPORTING.value = false
  }
}

onMounted(() => {
  loadGlyphs()
  load()
})
</script>

<template>
  <main class="mx-auto max-w-4xl px-6 py-10">
    <h1 class="text-3xl font-bold">Sign corrections</h1>

    <p v-if="FORBIDDEN" role="alert" class="mt-6 rounded-2xl bg-card p-6">Only reviewers can see this page.</p>

    <template v-else>
      <p class="mt-2 text-ink/70">
        Approved corrections become training labels. Corrections of the same sign are shown together.
      </p>

      <div class="mt-6 flex flex-wrap items-center justify-between gap-4">
        <nav aria-label="Review status" class="flex gap-2">
          <button
            v-for="option in STATUSES"
            :key="option.value"
            type="button"
            class="cursor-pointer rounded px-4 py-2 hover:bg-bar"
            :class="{ 'bg-bar font-bold': STATUS === option.value }"
            :aria-pressed="STATUS === option.value"
            @click="show(option.value)"
          >
            {{ option.label }}
          </button>
        </nav>
        <button
          type="button"
          class="cursor-pointer rounded border border-ink/30 px-4 py-2 hover:bg-ink/5 disabled:opacity-60"
          :disabled="EXPORTING"
          @click="exportApproved"
        >
          Export approved (JSON)
        </button>
      </div>

      <p v-if="NOTICE" role="status" class="mt-6 rounded-lg bg-accent/10 p-3">{{ NOTICE }}</p>
      <p v-if="ERROR" role="alert" class="mt-6 text-conf-low">{{ ERROR }}</p>
      <p v-if="LOADING" role="status" class="mt-6">Loading corrections…</p>
      <p v-else-if="!ERROR && !GROUPS.length" class="mt-8 rounded-2xl bg-card p-6">Nothing here.</p>

      <ul class="mt-6 flex flex-col gap-4">
        <li v-for="group in GROUPS" :key="group.key" class="rounded-2xl bg-card p-5" data-testid="review-group">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <p class="font-semibold">
              The model read
              <span v-if="GLYPHS[group.first.original_sign]" class="linear-a">{{ GLYPHS[group.first.original_sign] }}</span>
              {{ group.first.original_label }}
              <span class="font-normal text-ink/70">({{ Math.round(group.first.original_confidence) }}%)</span>
            </p>
            <p class="text-sm text-ink/70">Analysis {{ group.first.analysis_id }} · sign {{ group.first.sign_id }}</p>
          </div>
          <p v-if="group.conflicting" class="mt-2 text-sm font-semibold" data-testid="conflict">
            Users disagree on this sign.
          </p>

          <ul class="mt-3 divide-y divide-ink/10">
            <li v-for="item in group.items" :key="item.id" class="flex flex-wrap items-center justify-between gap-3 py-3" data-testid="review-item">
              <div class="min-w-0">
                <p class="text-lg font-bold" data-testid="proposal">
                  <span v-if="!item.uncertain && GLYPHS[item.proposed_sign]" class="linear-a mr-1">{{ GLYPHS[item.proposed_sign] }}</span>{{ proposal(item) }}
                </p>
                <p v-if="item.note" class="text-sm">“{{ item.note }}”</p>
                <p class="text-xs text-ink/70">
                  <time :datetime="item.created_at">{{ date(item.created_at) }}</time> · {{ item.model_version }}
                </p>
                <p v-if="ITEM_ERRORS[item.id]" role="alert" class="mt-1 text-sm text-conf-low">{{ ITEM_ERRORS[item.id] }}</p>
              </div>
              <div v-if="item.status === 'pending'" class="flex gap-2">
                <button
                  type="button"
                  class="cursor-pointer rounded bg-bar px-4 py-1.5 font-medium hover:brightness-95 disabled:opacity-60"
                  :disabled="DECIDING !== null"
                  @click="decide(item, 'approved')"
                >
                  Approve
                </button>
                <button
                  type="button"
                  class="cursor-pointer rounded border border-ink/30 px-4 py-1.5 hover:bg-ink/5 disabled:opacity-60"
                  :disabled="DECIDING !== null"
                  @click="decide(item, 'rejected')"
                >
                  Reject
                </button>
              </div>
              <span v-else class="text-sm font-medium">{{ item.status === 'approved' ? 'Approved' : 'Rejected' }}</span>
            </li>
          </ul>
        </li>
      </ul>
    </template>
  </main>
</template>
