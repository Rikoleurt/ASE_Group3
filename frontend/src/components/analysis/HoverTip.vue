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
      class="pointer-events-none invisible absolute bottom-full left-0 z-20 mb-2 w-72 rounded-lg bg-ink px-3 py-2 text-sm leading-snug text-page opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
    >
      {{ tip }}
    </span>
  </span>
</template>
