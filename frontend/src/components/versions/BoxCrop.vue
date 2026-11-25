<script setup>
// One box of a tablet image, cut out in the browser: an SVG whose viewBox is the box (with a
// little margin), so no image is cropped or stored on the server.
import { computed } from 'vue'

const props = defineProps({
  imageUrl: { type: String, required: true },
  width: { type: Number, required: true }, // the image's size in pixels
  height: { type: Number, required: true },
  box: { type: Object, required: true }, // { x, y, w, h } as fractions of the image
  size: { type: Number, default: 64 },
  colour: { type: String, default: null },
})

const MARGIN = 0.15 // of the box's longer side
const VIEW = computed(() => {
  const { x, y, w, h } = props.box
  const pad = Math.max(w * props.width, h * props.height) * MARGIN
  return [
    x * props.width - pad,
    y * props.height - pad,
    w * props.width + 2 * pad,
    h * props.height + 2 * pad,
  ]
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="VIEW.join(' ')"
    preserveAspectRatio="xMidYMid meet"
    class="shrink-0 rounded border bg-white"
    :style="{ borderColor: colour ?? 'rgb(0 0 0 / 0.15)' }"
    aria-hidden="true"
    data-testid="box-crop"
  >
    <image :href="imageUrl" x="0" y="0" :width="width" :height="height" />
  </svg>
</template>
