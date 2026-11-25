<script setup>
// A small picture of a sign: its most typical corpus drawing (from /glyphs/{sign}/preview.png),
// or its Unicode character when the picture is missing or fails to load.
import { ref, watch } from 'vue'

const props = defineProps({
  sign: { type: String, default: null },
  glyph: { type: String, default: '' },
  previewUrl: { type: String, default: null },
  size: { type: Number, default: 40 },
})

const FAILED = ref(false)
watch(() => props.previewUrl, () => { FAILED.value = false })
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center justify-center overflow-hidden rounded border border-ink/15 bg-white"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
    data-testid="sign-preview"
  >
    <img
      v-if="previewUrl && !FAILED"
      :src="`/api${previewUrl}`"
      alt=""
      loading="lazy"
      class="h-full w-full object-contain"
      @error="FAILED = true"
    />
    <span v-else class="linear-a" :style="{ fontSize: `${Math.round(size * 0.6)}px` }">{{ glyph || '?' }}</span>
  </span>
</template>
