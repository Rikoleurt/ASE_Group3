<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'

const props = defineProps({
  analysisId: { type: Number, required: true },
  currentUserId: { type: Number, default: null },
})

const route = useRoute()
const router = useRouter()
const comments = ref([])
const draft = ref('')
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const MAX_LENGTH = 2000

async function api(path, options = {}) {
  const response = await sessionFetch(path, options)
  if (response.status === 401) {
    await router.push({ path: '/login', query: { redirect: route.fullPath } })
    throw new Error('Please log in again.')
  }
  if (!response.ok) {
    const messages = {
      404: 'Analysis or comment not found.',
      422: 'Please check your comment (1 to 2000 characters).',
    }
    throw new Error(messages[response.status] || 'The service is unavailable. Please try again later.')
  }
  return response.status === 204 ? null : response.json()
}

async function loadComments() {
  loading.value = true
  error.value = ''
  try {
    comments.value = await api(`/api/users/me/analyses/${props.analysisId}/comments`)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function submit() {
  const text = draft.value.trim()
  if (!text || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const created = await api(`/api/users/me/analyses/${props.analysisId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: text }),
    })
    comments.value.push(created)
    draft.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

async function remove(comment) {
  error.value = ''
  try {
    await api(`/api/users/me/comments/${comment.id}`, { method: 'DELETE' })
    comments.value = comments.value.filter((c) => c.id !== comment.id)
  } catch (e) {
    error.value = e.message
  }
}

watch(() => props.analysisId, loadComments, { immediate: true })
</script>

<template>
  <section class="mt-6 rounded-3xl bg-card p-6" aria-labelledby="comments-title">
    <h2 id="comments-title" class="text-xl font-bold">Comments</h2>

    <p v-if="loading" role="status" class="mt-4">Loading comments…</p>
    <p v-else-if="!comments.length && !error" class="mt-4 text-ink/70">No comments yet.</p>

    <ul v-else-if="comments.length" class="mt-4 divide-y divide-ink/10">
      <li v-for="c in comments" :key="c.id" class="py-3">
        <div class="flex items-center justify-between gap-4 text-sm text-ink/70">
          <time :datetime="c.created_at">{{ new Date(c.created_at).toLocaleString() }}</time>
          <button
            v-if="currentUserId === null || c.author_id === currentUserId"
            type="button"
            class="cursor-pointer underline"
            @click="remove(c)"
          >
            Delete
          </button>
        </div>
        <p class="mt-1 whitespace-pre-wrap break-words">{{ c.body }}</p>
      </li>
    </ul>

    <p v-if="error" role="alert" class="mt-4 rounded-lg border border-red-800/30 bg-red-50 p-3 text-sm text-red-900">
      {{ error }}
    </p>

    <div class="mt-6">
      <label for="comment-draft" class="mb-2 block font-semibold">Add a comment</label>
      <textarea
        id="comment-draft"
        v-model="draft"
        :maxlength="MAX_LENGTH"
        :disabled="submitting"
        rows="3"
        class="w-full rounded-lg border border-ink/30 bg-white px-3 py-2.5 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
        @keydown.ctrl.enter="submit"
        @keydown.meta.enter="submit"
      />
      <div class="mt-2 flex items-center justify-between">
        <small class="text-ink/70">{{ draft.length }}/{{ MAX_LENGTH }}</small>
        <button
          type="button"
          :disabled="!draft.trim() || submitting"
          class="cursor-pointer rounded bg-bar px-6 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          @click="submit"
        >
          {{ submitting ? 'Posting…' : 'Post comment' }}
        </button>
      </div>
    </div>
  </section>
</template>