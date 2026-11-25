<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '../composables/communityApi'
import { sessionUser } from '../state/session'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import LoadingIndicator from '../components/LoadingIndicator.vue'
import SymbolDiscussionDialog from '../components/SymbolDiscussionDialog.vue'
import VoteButtons from '../components/VoteButtons.vue'
import MentionComposer from '../components/mentions/MentionComposer.vue'
import MentionText from '../components/mentions/MentionText.vue'
import SymbolMentionPreview from '../components/mentions/SymbolMentionPreview.vue'

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
const mentionComposer = ref(null)
const previewTarget = ref(null)
const tabletName = computed(() => (discussion.value?.tablet_filename || '').replace(/\.png$/i, ''))
const canDiscussSymbols = computed(() => Boolean(sessionUser.value)
  && sessionUser.value.id === discussion.value?.author_id)
let requestId = 0

function openSymbolDiscussion(symbol) {
  if (canDiscussSymbols.value) selectedSymbol.value = symbol
}

function round(value, decimals) {
    return Number(Math.round(value+'e'+decimals)+'e-'+decimals);
}

function mentionSymbol(symbol) {
  if (!sessionUser.value || !discussion.value || pending.value) return
  const analysisId = discussion.value.analysis_id
  const label = symbol.sign ? (symbol.reading || symbol.label || symbol.sign) : `symbol-${symbol.id}`
  mentionComposer.value?.insertMention({ key: `symbol:${analysisId}:${symbol.id}`, kind: 'symbol', label })
}

async function load() {
  const request = ++requestId
  discussion.value = null
  selectedSymbol.value = null
  previewTarget.value = null
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
  if (request === requestId) await prefillMention()
}

// Sent here to mention a glyph, an edition or a sign (workbench, story L): put the mention in the
// comment box, then drop it from the address so a reload does not add it again.
async function prefillMention() {
  const key = typeof route.query.mention === 'string' ? route.query.mention : ''
  const label = typeof route.query.label === 'string' ? route.query.label.slice(0, 255) : ''
  if (!/^(glyph|edition|sign):/.test(key) || !label || !sessionUser.value || !discussion.value) return
  await nextTick()
  mentionComposer.value?.insertMention({ key, kind: key.split(':')[0], label })
  router.replace({ path: route.path })
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
    <LoadingIndicator v-if="loading" class="mt-6" label="Loading discussion…" />
    <p v-if="error" role="alert" class="mt-6 text-conf-low">{{ error }}</p>
    <button v-if="error" type="button" class="mt-4 rounded bg-bar px-6 py-2" @click="load">Try again</button>
    <template v-if="discussion">
      <h1 class="mt-6 break-words text-3xl font-bold">{{ discussion.title }}</h1>
      <p class="mt-2 text-ink/70">Shared by {{ discussion.author_username }} · <time :datetime="discussion.created_at">{{ new Date(discussion.created_at).toLocaleString() }}</time></p>
      <VoteButtons v-if="sessionUser" class="mt-3" :discussion-id="discussion.id" :initial-score="discussion.score" />
      <p v-else class="mt-3 text-ink/70">{{ discussion.score }} points</p>
      <nav v-if="discussion.tablet_filename" class="mt-6 rounded-xl border border-ink/20 p-4" aria-labelledby="discussion-tree-title">
        <h2 id="discussion-tree-title" class="mb-3 text-xl font-bold">Discussion tree</h2>
        <RouterLink v-if="discussion.parent_discussion && discussion.parent_discussion.id !== discussion.id" :to="`/community/${discussion.parent_discussion.id}`" class="font-semibold hover:underline">
          Tablet {{ tabletName }} — {{ discussion.parent_discussion.title }}
        </RouterLink>
        <p v-else class="font-semibold">Tablet {{ tabletName }}</p>
        <p v-if="!discussion.parent_discussion && discussion.sign_id != null" class="mt-1 text-sm text-ink/70">This tablet has no general discussion yet.</p>
        <ul v-if="discussion.symbol_discussions?.length" class="mt-3 space-y-2 border-l border-ink/20 pl-4">
          <li v-for="child in discussion.symbol_discussions" :key="child.id">
            <RouterLink :to="`/community/${child.id}`" :aria-current="child.id === discussion.id ? 'page' : undefined" class="hover:underline">
              Symbol {{ child.symbol_name }} — {{ child.title }}
            </RouterLink>
            <span class="text-sm text-ink/70"> · {{ child.author_username }}</span>
          </li>
        </ul>
      </nav>
      <section v-if="discussion.symbol" class="mt-8 rounded-3xl bg-card p-6" aria-label="Shared symbol">
        <p v-if="imageError" role="alert">The symbol image could not be loaded.</p>
        <img v-else :src="discussion.image_url" :alt="`Symbol ${discussion.symbol_name} from ${tabletName}`" class="mx-auto max-h-80 max-w-full rounded-lg bg-white object-contain" @error="imageError = true" />
        <h2 class="mt-4 text-xl font-bold">{{ discussion.symbol_name }}</h2>
        <button v-if="sessionUser" type="button" :disabled="pending || loading" class="mt-3 rounded bg-bar px-3 py-2 disabled:opacity-50" @click="mentionSymbol(discussion.symbol)">Mention this symbol</button>
        <p class="mt-2">Model reading: {{ discussion.symbol.reading || discussion.symbol.label }} · Confidence: {{ round(discussion.symbol.confidence, 2) }}%</p>
        <p v-if="discussion.symbol.meaning" class="mt-2">{{ discussion.symbol.meaning }}</p>
      </section>
      <section v-else-if="discussion.result" class="mt-8 grid items-start gap-6 md:grid-cols-2" aria-label="Shared analysis">
        <div>
          <p v-if="imageError" role="alert">The tablet image could not be loaded.</p>
          <TabletOverlay v-else :signs="discussion.result.signs" :formulas="discussion.result.formulas" :can-discuss="canDiscussSymbols" :can-mention="Boolean(sessionUser) && !pending && !loading" @discuss="openSymbolDiscussion" @mention="mentionSymbol">
            <img :src="discussion.image_url" :alt="discussion.title" class="w-full rounded-lg bg-white" @error="imageError = true" />
          </TabletOverlay>
        </div>
        <div class="rounded-3xl bg-card p-6">
          <h2 class="text-xl font-bold">Model analysis</h2>
          <p class="mt-4">{{ discussion.result.summary }}</p>
          <dl class="mt-4 divide-y divide-ink/10">
            <div class="flex justify-between gap-4 py-3"><dt>Interpretation</dt><dd class="break-words">{{ discussion.result.symbol_interpretation }}</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Confidence</dt><dd>{{ round(discussion.result.confidence, 2) }}%</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt>Processing time</dt><dd>{{ discussion.result.time_taken }} s</dd></div>
          </dl>
          <ul class="mt-4 divide-y divide-ink/10" aria-label="Recognized signs">
            <li v-for="sign in discussion.result.signs" :key="sign.id" class="flex justify-between gap-3 py-2">
              <span><span class="linear-a text-xl">{{ sign.glyph }}</span> {{ sign.reading || sign.label }} <span v-if="sign.meaning">— {{ sign.meaning }}</span></span>
              <span>{{ round(sign.confidence, 2) }}%</span>
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
            <MentionText :body="comment.body" :mentions="comment.mentions || []" class="mt-2" @preview="previewTarget = $event" />
          </li>
        </ol>
        <p v-if="commentsError" role="alert" class="mt-4 text-conf-low">{{ commentsError }}</p>
        <button v-if="commentsError" type="button" class="mt-2 underline" @click="load">Reload discussion</button>
        <form v-if="sessionUser" class="mt-6" @submit.prevent="submit">
          <label for="community-comment" class="block font-semibold">Add a comment</label>
          <MentionComposer ref="mentionComposer" v-model="draft" :discussion-id="discussion.id" :disabled="pending || loading" />
          <div class="mt-3 flex items-center justify-between gap-4">
            <small>{{ draft.length }}/2000</small>
            <button type="submit" :disabled="pending || loading || !draft.trim()" class="cursor-pointer rounded bg-bar px-6 py-2 disabled:opacity-50">{{ pending ? 'Posting…' : 'Post comment' }}</button>
          </div>
        </form>
        <RouterLink v-else :to="{ path: '/login', query: { redirect: route.fullPath } }" class="mt-6 inline-block underline">Log in to join the discussion</RouterLink>
      </section>
      <SymbolMentionPreview v-if="previewTarget" :key="previewTarget.key" :target="previewTarget" @close="previewTarget = null" />
      <SymbolDiscussionDialog v-if="selectedSymbol && canDiscussSymbols" :analysis-id="discussion.analysis_id" :filename="tabletName" :symbol="selectedSymbol" @close="selectedSymbol = null" />
    </template>
  </main>
</template>
