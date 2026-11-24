<script setup>
import { ref, watch } from 'vue'
import { communityApi } from '../composables/communityApi'

const props = defineProps({
  discussionId: { type: Number, required: true },
  initialScore: { type: Number, default: 0 },
})

const score = ref(props.initialScore)
const myVote = ref(0)
const pending = ref(false)
const error = ref('')

async function load() {
  try {
    const state = await communityApi(`/discussions/${props.discussionId}/vote`)
    score.value = state.score
    myVote.value = state.my_vote
  } catch (failure) {
    error.value = failure.message
  }
}

async function vote(direction) {
  if (pending.value) return
  const value = myVote.value === direction ? 0 : direction // clicking again removes the vote
  const previous = { score: score.value, myVote: myVote.value }
  score.value += value - myVote.value
  myVote.value = value
  pending.value = true
  error.value = ''
  try {
    const state = await communityApi(`/discussions/${props.discussionId}/vote`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    })
    score.value = state.score
    myVote.value = state.my_vote
  } catch (failure) {
    score.value = previous.score
    myVote.value = previous.myVote
    error.value = failure.message
  } finally {
    pending.value = false
  }
}

watch(() => props.discussionId, load, { immediate: true })
</script>

<template>
  <div class="inline-flex items-center gap-2" role="group" aria-label="Vote on this discussion">
    <button type="button" :aria-pressed="myVote === 1" aria-label="Upvote" :disabled="pending"
      class="cursor-pointer rounded px-2 py-1 hover:bg-bar disabled:opacity-60"
      :class="myVote === 1 ? 'bg-bar font-bold' : ''" @click="vote(1)">▲</button>
    <span class="min-w-8 text-center font-semibold" aria-live="polite">{{ score }}</span>
    <button type="button" :aria-pressed="myVote === -1" aria-label="Downvote" :disabled="pending"
      class="cursor-pointer rounded px-2 py-1 hover:bg-bar disabled:opacity-60"
      :class="myVote === -1 ? 'bg-bar font-bold' : ''" @click="vote(-1)">▼</button>
    <span v-if="error" role="alert" class="text-sm text-red-900">{{ error }}</span>
  </div>
</template>