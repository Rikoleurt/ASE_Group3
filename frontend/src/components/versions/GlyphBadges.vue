<script setup>
// Activity bubbles drawn at the top-right corner of boxes over a tablet image (workbench, story I).
// Put inside a `relative` container the size of the image; boxes are fractions of the image.
defineProps({
  items: { type: Array, default: () => [] }, // [{ key, box: { x, y, w, h }, count }]
})

const percent = (value) => `${Math.round(value * 100000) / 1000}%`
</script>

<template>
  <span
    v-for="item in items"
    :key="item.key"
    class="pointer-events-none absolute z-20 flex h-5 min-w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-accent px-1 text-xs font-bold text-white shadow ring-2 ring-white"
    :style="{ left: percent(item.box.x + item.box.w), top: percent(item.box.y) }"
    :aria-label="typeof item.count === 'number' ? `${item.count} new` : String(item.count)"
    data-testid="glyph-badge"
    >{{ item.count > 99 ? '99+' : item.count }}</span
  >
</template>
