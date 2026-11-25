<script setup>
// Choose a sign: the model's guesses (when there are any) and a catalogue search, each sign
// shown with its typical drawing, character, number and reading. Arrow keys move through
// the results, Enter picks, Escape clears the search. Emits `pick` with the sign ID.
import { computed, ref, watch } from 'vue'
import { useCatalogue } from '../../composables/useCatalogue'
import SignPreview from './SignPreview.vue'
import SketchPad from './SketchPad.vue'
import { searchSigns } from './signSearch'

const props = defineProps({
  selected: { type: String, default: null }, // the sign chosen now, marked in the guesses
  candidates: { type: Array, default: () => [] }, // the model's guesses: { sign, label, probability }
  inputId: { type: String, default: 'sign-search' },
  label: { type: String, default: 'Find another sign' },
  placeholder: { type: String, default: 'AB81, ku, VIN…' },
})
const emit = defineEmits(['pick'])

const CATALOGUE = useCatalogue()
const BY_SIGN = computed(() => Object.fromEntries(CATALOGUE.value.map((sign) => [sign.sign, sign])))
const QUERY = ref('')
const SKETCHING = ref(false) // the drawing pad is open (workbench, story B)
const ACTIVE = ref(0)
const MATCHES = computed(() => searchSigns(CATALOGUE.value, QUERY.value))
const LIST_ID = computed(() => `${props.inputId}-matches`)
watch(MATCHES, () => {
  ACTIVE.value = 0
})

const entry = (sign) => BY_SIGN.value[sign] ?? { sign, name: sign, glyph: '', preview_url: null }

function pick(sign) {
  emit('pick', sign)
  QUERY.value = ''
}

function move(step) {
  if (!MATCHES.value.length) return
  ACTIVE.value = (ACTIVE.value + step + MATCHES.value.length) % MATCHES.value.length
}

function choose() {
  const match = MATCHES.value[ACTIVE.value]
  if (match) pick(match.sign)
}
</script>

<template>
  <div>
    <div v-if="candidates.length" class="mt-4">
      <h3 class="text-sm font-semibold">The model's guesses</h3>
      <div class="mt-1 flex flex-wrap gap-2">
        <button
          v-for="candidate in candidates"
          :key="candidate.sign"
          type="button"
          class="flex cursor-pointer items-center gap-2 rounded border border-ink/20 py-1 pr-2 pl-1 text-sm hover:bg-bar"
          :class="{ 'bg-bar font-semibold': candidate.sign === selected }"
          :aria-pressed="candidate.sign === selected"
          data-testid="candidate"
          @click="pick(candidate.sign)"
        >
          <SignPreview
            :sign="candidate.sign"
            :glyph="entry(candidate.sign).glyph"
            :preview-url="entry(candidate.sign).preview_url"
            :size="32"
          />
          <span
            >{{ candidate.label }}
            <span class="text-ink/60">{{ Math.round(candidate.probability) }}%</span></span
          >
        </button>
      </div>
    </div>

    <div class="mt-4 flex items-end justify-between gap-2">
      <label class="block text-sm font-semibold" :for="inputId">{{ label }}</label>
      <button
        type="button"
        class="cursor-pointer rounded border border-ink/30 px-2 py-0.5 text-sm hover:bg-bar"
        :aria-expanded="SKETCHING"
        data-testid="sketch-open"
        @click="SKETCHING = !SKETCHING"
      >
        ✎ {{ SKETCHING ? 'Close drawing' : 'Draw it' }}
      </button>
    </div>
    <SketchPad
      v-if="SKETCHING"
      class="mt-2 rounded-lg bg-white/60 p-2"
      @pick="
        (sign) => {
          SKETCHING = false
          pick(sign)
        }
      "
    />
    <input
      :id="inputId"
      v-model="QUERY"
      type="search"
      role="combobox"
      :aria-expanded="MATCHES.length > 0"
      :aria-controls="LIST_ID"
      :aria-activedescendant="MATCHES.length ? `${LIST_ID}-${ACTIVE}` : undefined"
      aria-autocomplete="list"
      :placeholder="placeholder"
      autocomplete="off"
      class="mt-1 w-full rounded border border-ink/30 bg-white px-3 py-1.5"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="choose"
      @keydown.esc="QUERY = ''"
    />
    <ul
      v-if="MATCHES.length"
      :id="LIST_ID"
      role="listbox"
      class="mt-1 max-h-64 overflow-auto rounded border border-ink/15 bg-white"
      data-testid="sign-matches"
    >
      <li
        v-for="(sign, index) in MATCHES"
        :id="`${LIST_ID}-${index}`"
        :key="sign.sign"
        role="option"
        :aria-selected="index === ACTIVE"
      >
        <button
          type="button"
          tabindex="-1"
          class="flex w-full cursor-pointer items-center gap-3 px-2 py-1 text-left hover:bg-bar"
          :class="{ 'bg-bar': index === ACTIVE }"
          @mouseenter="ACTIVE = index"
          @click="pick(sign.sign)"
        >
          <SignPreview
            :sign="sign.sign"
            :glyph="sign.glyph"
            :preview-url="sign.preview_url"
            :size="40"
          />
          <span v-if="sign.preview_url" class="linear-a text-xl" aria-hidden="true">{{
            sign.glyph
          }}</span>
          <span class="min-w-0 flex-1">
            <span class="font-semibold">{{ sign.sign }}</span>
            <span v-if="sign.reading" class="ml-1.5 text-ink/70">{{ sign.reading }}</span>
            <span
              v-if="
                sign.name && sign.name !== sign.sign && !sign.name.includes(`(${sign.reading})`)
              "
              class="block truncate text-xs text-ink/60"
              >{{ sign.name }}</span
            >
          </span>
        </button>
      </li>
    </ul>
    <p v-else-if="QUERY.trim()" class="mt-1 text-sm text-ink/70">No sign matches.</p>
  </div>
</template>
