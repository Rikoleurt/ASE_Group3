<script setup>
import { onMounted, ref } from 'vue'
import ShareAnalysis from './ShareAnalysis.vue'

defineProps({
  analysisId: { type: Number, required: true },
  filename: { type: String, required: true },
  symbol: { type: Object, required: true },
})
const emit = defineEmits(['close'])
const dialog = ref(null)
onMounted(() => dialog.value.showModal())
</script>

<template>
  <dialog ref="dialog" aria-labelledby="symbol-discussion-title" class="m-auto w-full max-w-lg rounded-2xl bg-card p-6 text-ink shadow-xl backdrop:bg-black/40" @close="emit('close')">
    <h2 id="symbol-discussion-title" class="text-xl font-bold">Discuss this symbol</h2>
    <p class="mt-2 break-words text-sm">From tablet {{ filename }}</p>
    <ShareAnalysis :analysis-id="analysisId" :filename="filename" :symbol="symbol" auto-open @cancel="dialog.close()" />
  </dialog>
</template>
