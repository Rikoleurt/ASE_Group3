<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '../composables/communityApi'

const props = defineProps({
  analysisId: { type: Number, required: true },
  filename: { type: String, default: 'Tablet analysis' },
  discussionId: { type: Number, default: null },
})
const router = useRouter()
const route = useRoute()
const editing = ref(false)
const title = ref('')
const sharedId = ref(null)
const pending = ref(false)
const error = ref('')
let requestId = 0
watch(() => [props.analysisId, props.discussionId], () => {
  requestId++
  editing.value = false
  pending.value = false
  error.value = ''
  title.value = props.filename.slice(0, 160)
  sharedId.value = props.discussionId
}, { immediate: true })
onBeforeUnmount(() => { requestId++ })

async function share() {
  if (pending.value || !title.value.trim()) return
  const request = ++requestId
  pending.value = true
  error.value = ''
  try {
    const discussion = await communityApi('/discussions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: props.analysisId, title: title.value.trim() }),
    })
    if (request === requestId) sharedId.value = discussion.id
  } catch (failure) {
    if (request !== requestId) return
    if (failure.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
    } else error.value = failure.message
  } finally {
    if (request === requestId) pending.value = false
  }
}
</script>

<template>
  <section class="mt-6 border-t border-ink/10 pt-6" aria-label="Share analysis">
    <RouterLink v-if="sharedId" :to="`/community/${sharedId}`" class="font-semibold underline">View discussion →</RouterLink>
    <template v-else>
      <button v-if="!editing" type="button" class="cursor-pointer rounded bg-bar px-5 py-2 hover:brightness-95" @click="editing = true">Share with community</button>
      <form v-else class="space-y-3" @submit.prevent="share">
        <p class="text-sm text-ink/70">Your tablet image and analysis will be public. Private history comments will stay private.</p>
        <label class="block font-semibold">
          Discussion title
          <input v-model="title" maxlength="160" required :disabled="pending" class="mt-2 block w-full rounded border border-ink/30 bg-white px-3 py-2 font-normal" />
        </label>
        <div class="flex gap-4">
          <button type="submit" :disabled="pending || !title.trim()" class="cursor-pointer rounded bg-bar px-5 py-2 disabled:opacity-50">{{ pending ? 'Sharing…' : 'Publish discussion' }}</button>
          <button type="button" :disabled="pending" class="underline" @click="editing = false">Cancel</button>
        </div>
        <p v-if="error" role="alert" class="text-conf-low">{{ error }}</p>
      </form>
    </template>
  </section>
</template>
