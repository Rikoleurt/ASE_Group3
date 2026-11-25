<script setup>
// Discussions about a corpus glyph, an edition release or a sign (workbench, story L): the ones
// that mention it, and a way to mention it in a discussion, which opens that discussion with the
// mention already in the comment box.
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionUser } from '../state/session'

const props = defineProps({
  target: { type: String, required: true }, // glyph:HT-13:5, edition:7 or sign:AB81
  label: { type: String, required: true }, // how the mention reads, e.g. "HT 13 · ka"
})

const router = useRouter()
const LINKED = ref([])
const CHOOSING = ref(false)
const RECENT = ref([])
const ERROR = ref('')

async function load() {
  LINKED.value = []
  const response = await fetch(
    `/api/community/linked?target=${encodeURIComponent(props.target)}`,
  ).catch(() => null)
  if (response?.ok) LINKED.value = (await response.json()).items
}
watch(() => props.target, load, { immediate: true })

async function choose() {
  CHOOSING.value = !CHOOSING.value
  if (!CHOOSING.value) return
  ERROR.value = ''
  const response = await fetch('/api/community/discussions?limit=10').catch(() => null)
  if (response?.ok) RECENT.value = (await response.json()).items ?? []
  else ERROR.value = 'Discussions could not be loaded.'
}

function mentionIn(discussion) {
  router.push({
    path: `/community/${discussion.id}`,
    query: { mention: props.target, label: props.label },
  })
}
</script>

<template>
  <section
    class="mt-4 border-t border-ink/10 pt-3 text-sm"
    aria-label="Discussions"
    data-testid="discussion-links"
  >
    <h3 class="font-semibold">Discussions</h3>
    <ul v-if="LINKED.length" class="mt-1" data-testid="linked-discussions">
      <li v-for="discussion in LINKED" :key="discussion.id">
        <RouterLink :to="`/community/${discussion.id}`" class="underline">{{
          discussion.title
        }}</RouterLink>
        <span class="text-ink/80"> · {{ discussion.author }}</span>
      </li>
    </ul>
    <p v-else class="mt-1 text-ink/80">No discussion mentions this yet.</p>
    <template v-if="sessionUser">
      <button
        type="button"
        class="mt-2 cursor-pointer underline"
        :aria-expanded="CHOOSING"
        data-testid="mention-in"
        @click="choose"
      >
        Mention it in a discussion
      </button>
      <div v-if="CHOOSING" class="mt-1 rounded-lg bg-white/70 p-2" data-testid="discussion-choice">
        <p v-if="ERROR" role="alert" class="text-confidence-low">{{ ERROR }}</p>
        <p v-else-if="!RECENT.length" class="text-ink/80">
          No discussions yet: start one from a saved analysis on the Community page.
        </p>
        <ul v-else>
          <li v-for="discussion in RECENT" :key="discussion.id">
            <button
              type="button"
              class="w-full cursor-pointer rounded px-1 py-0.5 text-left hover:bg-bar"
              @click="mentionIn(discussion)"
            >
              {{ discussion.title }}
            </button>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>
