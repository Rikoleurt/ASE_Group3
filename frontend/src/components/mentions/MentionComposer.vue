<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { communityApi } from '../../composables/communityApi'
import LoadingIndicator from '../LoadingIndicator.vue'
import { decodeDraft, encodeDraft, updateRanges } from './mentionSyntax'

const props = defineProps({
  modelValue: { type: String, default: '' },
  discussionId: { type: Number, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const input = ref(null)
const text = ref('')
const ranges = ref([])
const selection = ref({ start: 0, end: 0 })
const kind = ref('symbol')
const trigger = ref(null)
const items = ref([])
const nextAfter = ref(null)
const active = ref(0)
const loading = ref(false)
const error = ref('')
const inputError = ref('')
const open = computed(() => trigger.value !== null && !props.disabled)
let generation = 0
let timer
let request

watch(() => props.modelValue, (body) => {
  if (body !== encodeDraft(text.value, ranges.value)) {
    const decoded = decodeDraft(body)
    text.value = decoded.text
    ranges.value = decoded.ranges
    selection.value = { start: text.value.length, end: text.value.length }
    trigger.value = null
  }
}, { immediate: true })

function trackSelection() {
  selection.value = { start: input.value.selectionStart, end: input.value.selectionEnd }
}

function detectTrigger() {
  const caret = selection.value.start
  if (selection.value.end !== caret || ranges.value.some((range) => caret > range.start && caret <= range.end)) {
    trigger.value = null
    return
  }
  const match = /(?:^|[\s(])@([^\s@]{0,255})$/.exec(text.value.slice(0, caret))
  trigger.value = match ? { start: caret - match[1].length - 1, end: caret, q: match[1] } : null
}

function onInput(event) {
  const next = event.target.value
  const updated = updateRanges(text.value, next, ranges.value)
  const body = encodeDraft(next, updated)
  if (body.length > 2000) {
    event.target.value = text.value
    inputError.value = 'The comment is too long. Shorten it before adding more text.'
    return
  }
  inputError.value = ''
  text.value = next
  ranges.value = updated
  trackSelection()
  emit('update:modelValue', body)
  detectTrigger()
}

async function insertMention(target, start = selection.value.start, end = selection.value.end) {
  if (props.disabled) return
  const prefix = text.value.slice(0, start)
  const leading = prefix && !/\s$/.test(prefix) ? ' ' : ''
  const inserted = `${leading}@${target.label} `
  const next = prefix + inserted + text.value.slice(end)
  const shift = inserted.length - (end - start)
  const updated = ranges.value.flatMap((range) => {
    if (range.end <= start) return [range]
    if (range.start >= end) return [{ ...range, start: range.start + shift, end: range.end + shift }]
    return []
  })
  updated.push({ start: start + leading.length, end: start + inserted.length - 1, target })
  updated.sort((a, b) => a.start - b.start)
  const body = encodeDraft(next, updated)
  if (body.length > 2000 || updated.length > 20) {
    inputError.value = 'Keep the comment within 2000 characters and 20 mentions.'
    return
  }
  inputError.value = ''
  text.value = next
  ranges.value = updated
  trigger.value = null
  const caret = start + inserted.length
  selection.value = { start: caret, end: caret }
  emit('update:modelValue', body)
  await nextTick()
  input.value.focus()
  input.value.setSelectionRange(caret, caret)
}

function choose(target) {
  if (trigger.value) insertMention(target, trigger.value.start, trigger.value.end)
}

function onKeydown(event) {
  if (!open.value) return
  if (event.key === 'Escape') { event.preventDefault(); trigger.value = null }
  else if (['ArrowDown', 'ArrowUp'].includes(event.key) && items.value.length) {
    event.preventDefault()
    active.value = (active.value + (event.key === 'ArrowDown' ? 1 : -1) + items.value.length) % items.value.length
    nextTick(() => document.getElementById(`mention-option-${active.value}`)?.scrollIntoView?.({ block: 'nearest' }))
  } else if (event.key === 'Enter' && items.value[active.value]) {
    event.preventDefault()
    choose(items.value[active.value])
  }
}

async function loadSuggestions(append = false) {
  if (!open.value || loading.value || (append && nextAfter.value === null)) return
  const current = generation
  const controller = new AbortController()
  request = controller
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ type: kind.value, q: trigger.value.q, limit: '10' })
  if (append) params.set('after', nextAfter.value)
  try {
    const page = await communityApi(`/discussions/${props.discussionId}/mentions?${params}`, { signal: controller.signal })
    if (current !== generation) return
    items.value = append ? [...items.value, ...page.items] : page.items
    nextAfter.value = page.next_after
  } catch (failure) {
    if (current === generation && !controller.signal.aborted) error.value = failure.message
  } finally {
    if (current === generation) loading.value = false
  }
}

watch([() => trigger.value?.q, kind, () => props.discussionId, () => props.disabled], () => {
  generation++
  request?.abort()
  clearTimeout(timer)
  items.value = []
  nextAfter.value = null
  active.value = 0
  error.value = ''
  loading.value = false
  if (open.value) timer = setTimeout(() => loadSuggestions(), trigger.value.q ? 200 : 0)
})
onBeforeUnmount(() => { generation++; clearTimeout(timer); request?.abort() })
defineExpose({ insertMention })
</script>

<template>
  <div>
    <textarea id="community-comment" ref="input" :value="text" :disabled="disabled" maxlength="2000" required rows="4"
      aria-describedby="mention-help" aria-autocomplete="list" :aria-expanded="open" :aria-controls="open ? 'mention-options' : undefined"
      :aria-activedescendant="open && items.length ? `mention-option-${active}` : undefined"
      class="mt-2 w-full rounded border border-ink/30 bg-white px-3 py-2"
      @input="onInput" @select="trackSelection" @click="trackSelection(); detectTrigger()"
      @keyup="trackSelection" @keydown="onKeydown" />
    <p id="mention-help" class="mt-1 text-sm text-ink/70">Type @ to mention a user or a symbol from this tablet.</p>
    <p v-if="inputError" role="alert" class="mt-2 text-conf-low">{{ inputError }}</p>
    <div v-if="open" class="mt-2 rounded-xl border border-ink/20 bg-page p-3 shadow-lg">
      <div role="group" aria-label="Mention type" class="flex gap-2">
        <button v-for="option in ['symbol', 'user']" :key="option" type="button" :aria-pressed="kind === option"
          class="rounded px-3 py-1 font-semibold hover:bg-bar" :class="kind === option ? 'bg-bar' : 'bg-card'" @click="kind = option">
          {{ option === 'symbol' ? 'Symbols of this tablet' : 'Users' }}
        </button>
      </div>
      <div role="region" aria-label="Mention results" :aria-busy="loading"
        class="mt-2 h-64 overflow-y-auto overscroll-contain [scrollbar-gutter:stable]">
        <LoadingIndicator v-if="loading" class="mt-3" label="Loading suggestions…" />
        <p v-if="error" role="alert" class="mt-3 text-conf-low">{{ error }}</p>
        <button v-if="error" type="button" class="mt-2 hover:underline" @click="loadSuggestions(items.length > 0)">Try again</button>
        <p v-else-if="!loading && !items.length" class="mt-3 text-sm">No matching suggestions.</p>
        <ul id="mention-options" role="listbox" aria-label="Mention suggestions" class="mt-2">
          <li v-for="(item, index) in items" :key="item.key" role="presentation">
            <button :id="`mention-option-${index}`" type="button" role="option" :aria-selected="active === index" tabindex="-1"
              class="flex w-full items-center gap-3 rounded p-2 text-left hover:bg-bar" :class="active === index ? 'bg-bar' : ''"
              @mousedown.prevent @click="choose(item)">
              <img v-if="item.image_url" :src="item.image_url" alt="" loading="lazy" class="h-14 w-14 rounded bg-white object-contain" />
              <span><strong>@{{ item.label }}</strong><span v-if="item.kind === 'symbol'" class="block text-xs">Occurrence {{ item.sign_id }} · {{ item.tablet_filename }}</span></span>
            </button>
          </li>
        </ul>
        <button v-if="nextAfter !== null" type="button" :disabled="loading" class="mt-2 rounded bg-bar px-3 py-1" @click="loadSuggestions(true)">More suggestions</button>
      </div>
    </div>
  </div>
</template>
