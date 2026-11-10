<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '../composables/communityApi'
import { sessionUser } from '../state/session'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import FractionCheck from '../components/analysis/FractionCheck.vue'

const route = useRoute()
const router = useRouter()
const discussion = ref(null)
const comments = ref([])
const draft = ref('')
const loading = ref(false)
const pending = ref(false)
const error = ref('')
const commentsError = ref('')
const imageError = ref(false)
let requestId = 0

async function load() {
  const request = ++requestId
  discussion.value = null
  comments.value = []
  draft.value = ''
  error.value = ''
  commentsError.value = ''
  imageError.value = false
  loading.value = true
  pending.value = false
  const id = encodeURIComponent(route.params.id)
  try {
    const detail = await communityApi(`/discussions/${id}`)
    if (request !== requestId) return
    discussion.value = detail
    try {
      const rows = await communityApi(`/discussions/${id}/comments`)
      if (request === requestId) comments.value = rows
    } catch (failure) {
      if (request === requestId) commentsError.value = failure.message
    }
  } catch (failure) {
    if (request === requestId) error.value = failure.message
  } finally {
    if (request === requestId) loading.value = false
  }
}

async function submit() {
  if (!draft.value.trim() || pending.value || loading.value) return
  const request = requestId
  const id = discussion.value.id
  pending.value = true
  commentsError.value = ''
  try {
    const comment = await communityApi(`/discussions/${id}/comments`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: draft.value.trim() }),
    })
    if (request !== requestId) return
    comments.value.push(comment)
    draft.value = ''
  } catch (failure) {
    if (request !== requestId) return
    if (failure.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
    } else commentsError.value = failure.message
  } finally {
    if (request === requestId) pending.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => { requestId++ })
</script>

<template>
  <main class="mx-auto max-w-5xl px-6 py-10">
    <RouterLink to="/community" class="underline">← Community</RouterLink>
    <p v-if="loading" role="status" class="mt-6">Loading discussion…</p>
    <p v-if="error" role="alert" class="mt-6 text-conf-low">{{ error }}</p>
    <button v-if="error" type="button" class="mt-4 rounded bg-bar px-6 py-2" @click="load">Try again</button>
    <template v-if="discussion">
      <h1 class="mt-6 break-words text-3xl font-bold">{{ discussion.title }}</h1>
      <p class="mt-2 text-ink/70">Shared by {{ discussion.author_username }} · <time :datetime="discussion.created_at">{{ new Date(discussion.created_at).toLocaleString() }}</time></p>
      <section class="mt-8 grid items-start gap-6 md:grid-cols-2" aria-label="Shared analysis">
        <div>
          <p v-if="imageError" role="alert">The tablet image could not be loaded.</p>
          <TabletOverlay v-else :signs="discussion.result.signs" :formulas="discussion.result.formulas">
            <img :src="discussion.image_url" :alt="discussion.title" class="w-full rounded-lg bg-white" @error="imageError = true" />
          </TabletOverlay>
        </div>
        <div class="rounded-3xl bg-card p-6">
          <h2 class="text-xl font-bold">Model analysis</h2>
          <p class="mt-4">{{ discussion.result.summary }}</p>
          <dl class="mt-4 divide-y divide-ink/10">
            <div class="flex justify-between gap-4 py-3"><dt>Interpretation</dt><dd class="break-words">{{ discussion.result.symbol_interpretation }}</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Confidence</dt><dd>{{ discussion.result.confidence }}%</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Processing time</dt><dd>{{ discussion.result.time_taken }} s</dd></div>
          </dl>
          <ul class="mt-4 divide-y divide-ink/10" aria-label="Recognized signs">
            <li v-for="sign in discussion.result.signs" :key="sign.id" class="flex justify-between gap-3 py-2">
              <span><span class="linear-a text-xl">{{ sign.glyph }}</span> {{ sign.reading || sign.label }} <span v-if="sign.meaning">— {{ sign.meaning }}</span></span>
              <span>{{ sign.confidence }}%</span>
            </li>
          </ul>
        </div>
      </section>
      <FractionCheck :analysis="discussion.result" class="mt-8" />
      <section class="mt-8 rounded-3xl bg-card p-6" aria-labelledby="discussion-comments">
        <h2 id="discussion-comments" class="text-xl font-bold">Discussion</h2>
        <p v-if="!comments.length && !loading && !commentsError" class="mt-4 text-ink/70">No comments yet. Start the discussion.</p>
        <ol aria-label="Comments" class="mt-4 divide-y divide-ink/10">
          <li v-for="comment in comments" :key="comment.id" class="py-4">
            <p class="text-sm"><strong>{{ comment.author_username }}</strong> · <time :datetime="comment.created_at" class="text-ink/70">{{ new Date(comment.created_at).toLocaleString() }}</time></p>
            <p class="mt-2 whitespace-pre-wrap break-words">{{ comment.body }}</p>
          </li>
        </ol>
        <p v-if="commentsError" role="alert" class="mt-4 text-conf-low">{{ commentsError }}</p>
        <button v-if="commentsError" type="button" class="mt-2 underline" @click="load">Reload discussion</button>
        <form v-if="sessionUser" class="mt-6" @submit.prevent="submit">
          <label for="community-comment" class="block font-semibold">Add a comment</label>
          <textarea id="community-comment" v-model="draft" :disabled="pending" maxlength="2000" required rows="4" class="mt-2 w-full rounded border border-ink/30 bg-white px-3 py-2" />
          <div class="mt-3 flex items-center justify-between gap-4">
            <small>{{ draft.length }}/2000</small>
            <button type="submit" :disabled="pending || loading || !draft.trim()" class="cursor-pointer rounded bg-bar px-6 py-2 disabled:opacity-50">{{ pending ? 'Posting…' : 'Post comment' }}</button>
          </div>
        </form>
        <RouterLink v-else :to="{ path: '/login', query: { redirect: route.fullPath } }" class="mt-6 inline-block underline">Log in to join the discussion</RouterLink>
      </section>
    </template>
  </main>
</template>
