<script setup>
// The tablet as the reader read it: each line in Linear A glyphs, coloured like
// their boxes, with each sign's reading under it and the line's transliteration
// and gloss beside.
import { computed } from 'vue'
import { ROLES, roleKey } from './colors.js'
import './linearA.css'

const props = defineProps({
  analysis: { type: Object, required: true },
})

const MARKERS = computed(() => new Set((props.analysis.formulas ?? []).flatMap((formula) => formula.marker_ids)))
const LINES = computed(() => {
  const byId = new Map((props.analysis.signs ?? []).map((sign) => [sign.id, sign]))
  return (props.analysis.lines ?? []).map((line) => ({ ...line, signs: line.sign_ids.map((id) => byId.get(id)) }))
})

function reading(sign) {
  // "ni FIC" is written by role: the syllable "ni" or the logogram "FIC".
  const words = (sign.reading ?? '').split(' ').filter(Boolean)
  const wanted = sign.role === 'logogram' ? words.find((word) => word !== word.toLowerCase()) : words.find((word) => word === word.toLowerCase())
  return wanted ?? sign.reading ?? sign.sign ?? '?'
}
</script>

<template>
  <ol v-if="LINES.length" class="mt-3 space-y-3" data-testid="tablet-text">
    <li v-for="line in LINES" :key="line.index" class="flex flex-wrap items-end gap-x-6 gap-y-1">
      <span class="w-6 self-center text-right text-sm text-ink/50">{{ line.index + 1 }}</span>
      <span class="flex flex-wrap items-end gap-2">
        <span
          v-for="sign in line.signs"
          :key="sign.id"
          class="flex min-w-8 flex-col items-center"
          :title="sign.meaning ? `${reading(sign)}: ${sign.meaning}` : reading(sign)"
          data-testid="glyph-cell"
        >
          <span class="linear-a text-3xl" :style="{ color: ROLES[roleKey(sign, MARKERS)].color }">
            {{ sign.glyph ?? '□' }}
          </span>
          <span class="mt-1 text-xs">{{ reading(sign) }}</span>
        </span>
      </span>
      <span class="text-sm">
        <span class="font-medium">{{ line.text }}</span>
        <span v-if="line.gloss !== line.text" class="text-ink/70"> — {{ line.gloss }}</span>
      </span>
    </li>
  </ol>
</template>
