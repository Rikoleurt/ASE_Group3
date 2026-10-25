<script setup>
// What the reader made of one sign: its Linear A glyph and how it decodes.
import { computed } from 'vue'
import { ROLES } from './colors.js'
import './linearA.css'

const props = defineProps({
  sign: { type: Object, required: true },
  roleKey: { type: String, required: true },
})

const ROLE = computed(() => ROLES[props.roleKey])
// The runner-up readings worth mentioning: below 1% they are noise.
const OTHERS = computed(() => (props.sign.candidates ?? []).slice(1).filter((other) => other.probability >= 1))
</script>

<template>
  <div class="w-64 rounded-xl bg-ink p-3 text-page shadow-xl" data-testid="sign-card">
    <div class="flex items-center gap-3">
      <span
        class="linear-a flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-page text-4xl"
        :style="{ color: ROLE.color }"
        data-testid="sign-glyph"
      >
        {{ sign.glyph ?? '?' }}
      </span>
      <div class="min-w-0">
        <p class="text-lg font-bold leading-tight">{{ sign.reading ?? sign.label }}</p>
        <p class="text-sm opacity-80">{{ sign.sign ?? 'unidentified' }}</p>
        <p class="mt-1 inline-flex items-center gap-1.5 text-xs">
          <span class="inline-block h-2.5 w-2.5 rounded-sm" :style="{ backgroundColor: ROLE.color }" />
          {{ ROLE.label }}
        </p>
      </div>
    </div>
    <dl class="mt-3 space-y-1 text-sm">
      <div v-if="sign.meaning" class="flex justify-between gap-3">
        <dt class="opacity-70">Means</dt>
        <dd class="text-right font-medium" data-testid="sign-meaning">{{ sign.meaning }}</dd>
      </div>
      <div class="flex justify-between gap-3">
        <dt class="opacity-70">Confidence</dt>
        <dd class="font-medium">{{ Math.round(sign.confidence) }}%</dd>
      </div>
      <div v-if="OTHERS.length" class="flex justify-between gap-3">
        <dt class="opacity-70">Or perhaps</dt>
        <dd class="text-right">
          {{ OTHERS.map((other) => `${other.label} (${Math.round(other.probability)}%)`).join(', ') }}
        </dd>
      </div>
    </dl>
    <p v-if="!sign.glyph" class="mt-2 text-xs opacity-70">This sign has no Unicode character.</p>
  </div>
</template>
