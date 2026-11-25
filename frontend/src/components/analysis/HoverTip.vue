<script setup>
// A label that shows a short explanation while it is hovered or keyboard-focused.
import { useId } from 'vue'

defineProps({
  tip: { type: String, required: true },
})

const ID = useId()
</script>

<template>
  <span class="group relative inline-flex">
    <span
      tabindex="0"
      class="cursor-help underline decoration-dotted underline-offset-4 focus:outline-2 focus:outline-offset-2 focus:outline-accent"
      :aria-describedby="ID"
    >
      <slot />
    </span>
    <span
      :id="ID"
      role="tooltip"
      class="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-72 max-w-[calc(100vw-2rem)] rounded-lg bg-ink px-3 py-2 text-sm leading-snug text-page shadow-lg group-hover:block group-focus-within:block"
    >
      {{ tip }}
    </span>
  </span>
</template>
