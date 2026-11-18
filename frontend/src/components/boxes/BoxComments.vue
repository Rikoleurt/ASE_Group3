<script setup>
// Comments on a corrected copy (#86): the selected box's thread, or the copy's general
// thread when no box is selected. Comment access or higher can write; authors delete their
// own, and the owner and managers can delete any.
import { computed, ref, watch } from 'vue'
import { sessionFetch } from '../../state/session'

const props = defineProps({
  setId: { type: Number, required: true },
  boxId: { type: Number, default: null }, // null: the whole copy; negative (unsaved) boxes have no thread yet
  boxName: { type: String, default: '' },
  canComment: { type: Boolean, default: false },
})

const COMMENTS = ref([])
const DRAFT = ref('')
const LOADING = ref(false)
const POSTING = ref(false)
const ERROR = ref('')
const MAX = 2000

const UNSAVED = computed(() => props.boxId !== null && props.boxId < 0)
const THREAD = computed(() => COMMENTS.value.filter((comment) => comment.box_id === props.boxId))
const COUNTS = computed(() => COMMENTS.value.reduce((counts, comment) => {
  counts[comment.box_id ?? 'copy'] = (counts[comment.box_id ?? 'copy'] ?? 0) + 1
  return counts
}, {}))
const TITLE = computed(() => (props.boxId === null ? 'Comments on this copy' : `Comments on ${props.boxName || 'this box'}`))

defineExpose({ COUNTS })

async function failure(response, fallback) {
  const body = await response.json().catch(() => null)
  return typeof body?.detail === 'string' ? body.detail : Array.isArray(body?.detail) ? body.detail[0]?.msg ?? fallback : fallback
}

async function load() {
  LOADING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/box-sets/${props.setId}/comments`)
    if (!response.ok) throw new Error('The comments could not be loaded.')
    COMMENTS.value = await response.json()
  } catch (error) {
    ERROR.value = error instanceof TypeError ? 'Couldnt reach the server' : error.message
  } finally {
    LOADING.value = false
  }
}

async function post() {
  const body = DRAFT.value.trim()
  if (!body || POSTING.value) return
  POSTING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/box-sets/${props.setId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ box_id: props.boxId, body }),
    })
    if (!response.ok) throw new Error(await failure(response, 'Your comment could not be posted.'))
    COMMENTS.value = [...COMMENTS.value, await response.json()]
    DRAFT.value = ''
  } catch (error) {
    ERROR.value = error instanceof TypeError ? 'Couldnt reach the server' : error.message
  } finally {
    POSTING.value = false
  }
}

async function remove(comment) {
  if (!window.confirm('Delete this comment?')) return
  ERROR.value = ''
  const response = await sessionFetch(`/api/box-sets/${props.setId}/comments/${comment.id}`, { method: 'DELETE' }).catch(() => null)
  if (response?.ok) COMMENTS.value = COMMENTS.value.filter((item) => item.id !== comment.id)
  else ERROR.value = response ? await failure(response, 'The comment could not be deleted.') : 'Couldnt reach the server'
}

watch(() => props.setId, load, { immediate: true })
</script>

<template>
  <section class="rounded-3xl bg-card p-5" aria-labelledby="comments-h" data-testid="comments">
    <h2 id="comments-h" class="text-xl font-bold">{{ TITLE }}</h2>
    <p v-if="ERROR" role="alert" class="mt-2 text-confidence-low">{{ ERROR }}</p>
    <p v-if="UNSAVED" class="mt-2 text-ink/70">Save the new box before commenting on it.</p>
    <template v-else>
      <p v-if="!LOADING && !THREAD.length" class="mt-2 text-ink/70">No comments yet.</p>
      <ol class="mt-2 max-h-72 overflow-auto">
        <li v-for="comment in THREAD" :key="comment.id" class="border-t border-ink/10 py-2 first:border-0" data-testid="comment">
          <p class="text-sm text-ink/70">
            {{ comment.author.username ?? 'Deleted account' }} · <time :datetime="comment.created_at">{{ new Date(comment.created_at).toLocaleString() }}</time>
            <button v-if="comment.can_delete" type="button" class="ml-2 cursor-pointer underline" data-testid="comment-delete" @click="remove(comment)">Delete</button>
          </p>
          <p class="whitespace-pre-wrap break-words">{{ comment.body }}</p>
        </li>
      </ol>
      <form v-if="canComment" class="mt-3" @submit.prevent="post">
        <label class="sr-only" for="comment-body">Your comment</label>
        <textarea id="comment-body" v-model="DRAFT" rows="3" :maxlength="MAX" class="w-full rounded border border-ink/30 bg-white px-3 py-2" placeholder="Why is this box right or wrong?" />
        <div class="flex items-center justify-between text-sm">
          <span class="text-ink/60">{{ DRAFT.length }} / {{ MAX }}</span>
          <button type="submit" class="cursor-pointer rounded bg-bar px-4 py-1 font-semibold hover:brightness-95 disabled:opacity-50" :disabled="!DRAFT.trim() || POSTING" data-testid="comment-post">
            {{ POSTING ? 'Posting…' : 'Comment' }}
          </button>
        </div>
      </form>
      <p v-else class="mt-2 text-sm text-ink/70">You can read comments on this copy but not write them.</p>
    </template>
  </section>
</template>
