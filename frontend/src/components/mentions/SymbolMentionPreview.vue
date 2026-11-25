<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { communityApi } from '../../composables/communityApi'
import LoadingIndicator from '../LoadingIndicator.vue'

const props = defineProps({ target: { type: Object, required: true } })
const emit = defineEmits(['close'])
const dialog = ref(null)
const preview = ref(null)
const loading = ref(true)
const error = ref('')
const imageError = ref(false)
const request = new AbortController()
onMounted(async () => {
  dialog.value.showModal()
  try {
    const result = await communityApi(`/symbols/${props.target.analysis_id}/${props.target.sign_id}`, { signal: request.signal })
    if (!request.signal.aborted) preview.value = result
  } catch (failure) {
    if (!request.signal.aborted) error.value = failure.status === 404 ? 'This symbol is no longer available.' : failure.message
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
})
onBeforeUnmount(() => request.abort())
</script>

<template>
  <dialog ref="dialog" aria-labelledby="symbol-preview-title" class="m-auto w-full max-w-lg rounded-2xl bg-card p-6 text-ink shadow-xl backdrop:bg-black/40" @close="emit('close')">
    <div class="flex items-center justify-between gap-4">
      <h2 id="symbol-preview-title" class="text-xl font-bold">Symbol {{ preview?.target.label || target.label }}</h2>
      <button type="button" class="rounded bg-bar px-3 py-1" @click="dialog.close()">Close</button>
    </div>
    <LoadingIndicator v-if="loading" class="mt-4" label="Loading symbol…" />
    <p v-if="error" role="alert" class="mt-4">{{ error }}</p>
    <template v-if="preview">
      <p class="mt-3 break-words">{{ preview.target.tablet_filename }} · Occurrence {{ preview.target.sign_id }}</p>
      <p v-if="imageError" role="alert" class="mt-4">The symbol image is unavailable.</p>
      <img v-else :src="preview.target.image_url" :alt="`Symbol ${preview.target.label}`" class="mx-auto mt-4 max-h-64 max-w-full rounded bg-white object-contain" @error="imageError = true" />
      <p class="mt-4">Model reading: {{ preview.symbol.reading || preview.symbol.label }} · Confidence: {{ Math.round(preview.symbol.confidence) }}%</p>
      <RouterLink v-if="preview.target.discussion_id" :to="`/community/${preview.target.discussion_id}`" class="mt-4 inline-block font-semibold hover:underline" @click="dialog.close()">Open symbol discussion →</RouterLink>
      <p v-else class="mt-4 text-sm text-ink/80">This symbol has no dedicated discussion yet.</p>
    </template>
  </dialog>
</template>
