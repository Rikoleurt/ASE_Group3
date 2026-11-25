<script setup>
defineProps({ label: { type: String, default: 'Loading…' } })
</script>

<template>
  <div role="status" aria-live="polite" class="flex items-center gap-3 text-ink/80">
    <span aria-hidden="true" class="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-ink/20 border-t-ink motion-reduce:animate-none" />
    <span>{{ label }}</span>
  </div>
</template>
