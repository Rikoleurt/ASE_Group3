<script setup>
// The selected box's epigraphic marks (workbench, story F), in GORILA/SigLA conventions: how sure
// the reading is, how well the sign is preserved, other possible readings, and the end of a word.
// Emits `update` with the fields that changed. Shortcuts in the editor: U (uncertain), W (word end).
import { computed } from 'vue'
import SignPicker from '../signs/SignPicker.vue'
import SignPreview from '../signs/SignPreview.vue'
import { useCatalogue } from '../../composables/useCatalogue'
import { marksOf } from '../../composables/useBoxSet'

const props = defineProps({
  box: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update'])

const CATALOGUE = useCatalogue()
const BY_SIGN = computed(() => Object.fromEntries(CATALOGUE.value.map((sign) => [sign.sign, sign])))
const MARKS = computed(() => marksOf(props.box))

const CERTAINTY = [
  { value: 'certain', label: 'Certain' },
  { value: 'uncertain', label: 'Uncertain', hint: 'dotted under: ḳụ' },
  { value: 'illegible', label: 'Illegible', hint: 'written •' },
]
const DAMAGE = [
  { value: 'none', label: 'Whole' },
  { value: 'partial', label: 'Partly preserved', hint: '⸢ku⸣' },
  { value: 'restored', label: 'Lost, restored', hint: '[ku]' },
]

function addAlternative(sign) {
  if (
    !sign ||
    sign === props.box.sign ||
    MARKS.value.alternatives.includes(sign) ||
    MARKS.value.alternatives.length >= 5
  )
    return
  emit('update', { alternatives: [...MARKS.value.alternatives, sign] })
}

function removeAlternative(sign) {
  emit('update', { alternatives: MARKS.value.alternatives.filter((item) => item !== sign) })
}
</script>

<template>
  <section
    class="mt-4 border-t border-ink/10 pt-3"
    aria-label="Epigraphic marks"
    data-testid="marks"
  >
    <fieldset :disabled="disabled">
      <legend class="text-sm font-semibold">Reading</legend>
      <div class="mt-1 flex flex-wrap gap-1">
        <label
          v-for="option in CERTAINTY"
          :key="option.value"
          class="cursor-pointer rounded border px-2 py-0.5 text-sm"
          :class="
            MARKS.certainty === option.value
              ? 'border-ink bg-bar font-semibold'
              : 'border-ink/20 hover:bg-bar'
          "
          :title="option.hint"
        >
          <input
            type="radio"
            class="sr-only"
            name="certainty"
            :value="option.value"
            :checked="MARKS.certainty === option.value"
            :data-testid="`certainty-${option.value}`"
            @change="emit('update', { certainty: option.value })"
          />
          {{ option.label }}
        </label>
      </div>
    </fieldset>
    <fieldset class="mt-2" :disabled="disabled">
      <legend class="text-sm font-semibold">Preservation</legend>
      <div class="mt-1 flex flex-wrap gap-1">
        <label
          v-for="option in DAMAGE"
          :key="option.value"
          class="cursor-pointer rounded border px-2 py-0.5 text-sm"
          :class="
            MARKS.damage === option.value
              ? 'border-ink bg-bar font-semibold'
              : 'border-ink/20 hover:bg-bar'
          "
          :title="option.hint"
        >
          <input
            type="radio"
            class="sr-only"
            name="damage"
            :value="option.value"
            :checked="MARKS.damage === option.value"
            :data-testid="`damage-${option.value}`"
            @change="emit('update', { damage: option.value })"
          />
          {{ option.label }}
        </label>
      </div>
    </fieldset>
    <label class="mt-2 flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        :checked="MARKS.word_end"
        :disabled="disabled"
        data-testid="word-end"
        @change="emit('update', { word_end: $event.target.checked })"
      />
      A word ends after this sign
    </label>

    <div class="mt-3">
      <h3 class="text-sm font-semibold">Other possible readings</h3>
      <ul
        v-if="MARKS.alternatives.length"
        class="mt-1 flex flex-wrap gap-1"
        data-testid="alternatives"
      >
        <li
          v-for="sign in MARKS.alternatives"
          :key="sign"
          class="flex items-center gap-1 rounded border border-ink/20 bg-white/70 py-0.5 pr-1 pl-0.5 text-sm"
        >
          <SignPreview
            :sign="sign"
            :glyph="BY_SIGN[sign]?.glyph ?? ''"
            :preview-url="BY_SIGN[sign]?.preview_url ?? `/glyphs/${sign}/preview.png`"
            :size="22"
          />
          {{ BY_SIGN[sign]?.name ?? sign }}
          <button
            v-if="!disabled"
            type="button"
            class="cursor-pointer px-1 text-ink/60 hover:text-ink"
            :aria-label="`Remove ${sign}`"
            @click="removeAlternative(sign)"
          >
            ×
          </button>
        </li>
      </ul>
      <SignPicker
        v-if="!disabled && MARKS.alternatives.length < 5"
        input-id="alternative-search"
        label="Add another possible reading"
        @pick="addAlternative"
      />
    </div>
  </section>
</template>
