<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '../composables/communityApi'
import { sessionUser } from '../state/session'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import SymbolDiscussionDialog from '../components/SymbolDiscussionDialog.vue'

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
const selectedSymbol = ref(null)
const canDiscussSymbols = computed(() => Boolean(sessionUser.value)
  && sessionUser.value.id === discussion.value?.author_id)
let requestId = 0

function openSymbolDiscussion(symbol) {
  if (canDiscussSymbols.value) selectedSymbol.value = symbol
}

async function load() {
  const request = ++requestId
  discussion.value = null
  selectedSymbol.value = null
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
      <p v-if="discussion.sign_id != null" class="mt-3" data-testid="symbol-origin">
        {{ discussion.author_username }} created a discussion about symbol <strong>{{ discussion.symbol_name }}</strong>
        from tablet <strong>{{ discussion.tablet_filename }}</strong>.
      </p>
      <nav v-if="discussion.tablet_filename" class="mt-6 rounded-xl border border-ink/20 p-4" aria-label="Tablet discussion tree">
        <RouterLink v-if="discussion.parent_discussion && discussion.parent_discussion.id !== discussion.id" :to="`/community/${discussion.parent_discussion.id}`" class="font-semibold underline">
          Tablet {{ discussion.tablet_filename }} — {{ discussion.parent_discussion.title }}
        </RouterLink>
        <p v-else class="font-semibold">Tablet {{ discussion.tablet_filename }}</p>
        <p v-if="!discussion.parent_discussion && discussion.sign_id != null" class="mt-1 text-sm text-ink/70">This tablet has no general discussion yet.</p>
        <ul v-if="discussion.symbol_discussions?.length" class="mt-3 space-y-2 border-l border-ink/20 pl-4">
          <li v-for="child in discussion.symbol_discussions" :key="child.id">
            <RouterLink :to="`/community/${child.id}`" :aria-current="child.id === discussion.id ? 'page' : undefined" class="underline">
              Symbol {{ child.symbol_name }} — {{ child.title }}
            </RouterLink>
            <span class="text-sm text-ink/70"> · {{ child.author_username }}</span>
          </li>
        </ul>
      </nav>
      <section v-if="discussion.symbol" class="mt-8 rounded-3xl bg-card p-6" aria-label="Shared symbol">
        <p v-if="imageError" role="alert">The symbol image could not be loaded.</p>
        <img v-else :src="discussion.image_url" :alt="`Symbol ${discussion.symbol_name} from ${discussion.tablet_filename}`" class="mx-auto max-h-80 max-w-full rounded-lg bg-white object-contain" @error="imageError = true" />
        <h2 class="mt-4 text-xl font-bold">{{ discussion.symbol_name }}</h2>
        <p class="mt-2">Model reading: {{ discussion.symbol.reading || discussion.symbol.label }} · Confidence: {{ discussion.symbol.confidence }}%</p>
        <p v-if="discussion.symbol.meaning" class="mt-2">{{ discussion.symbol.meaning }}</p>
      </section>
      <section v-else-if="discussion.result" class="mt-8 grid items-start gap-6 md:grid-cols-2" aria-label="Shared analysis">
        <div>
          <p v-if="imageError" role="alert">The tablet image could not be loaded.</p>
          <TabletOverlay v-else :signs="discussion.result.signs" :formulas="discussion.result.formulas" :can-discuss="canDiscussSymbols" @discuss="openSymbolDiscussion">
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
      <FractionCheck v-if="discussion.result" :analysis="discussion.result" class="mt-8" />
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
      <SymbolDiscussionDialog v-if="selectedSymbol && canDiscussSymbols" :analysis-id="discussion.analysis_id" :filename="discussion.tablet_filename" :symbol="selectedSymbol" @close="selectedSymbol = null" />
    </template>
  </main>
</template>
