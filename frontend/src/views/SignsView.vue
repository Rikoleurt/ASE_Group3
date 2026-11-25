<script setup>
// Find a sign (workbench, story B): by number, reading or name, or by drawing it. Every sign of the
// catalogue is listed with its typical drawing; choosing one opens its page.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import SignPreview from '../components/signs/SignPreview.vue'
import SketchPad from '../components/signs/SketchPad.vue'
import { searchSigns } from '../components/signs/signSearch'
import { useCatalogue } from '../composables/useCatalogue'
import '../components/analysis/linearA.css'

const router = useRouter()
const CATALOGUE = useCatalogue()
const QUERY = ref('')
const SHOWN = computed(() =>
  QUERY.value.trim() ? searchSigns(CATALOGUE.value, QUERY.value, 60) : CATALOGUE.value,
)

function open(sign) {
  router.push(`/signs/${encodeURIComponent(sign)}`)
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <h1 class="text-3xl font-bold">Find a sign</h1>
    <p class="mt-1 text-ink/70">
      Type a sign's number, reading or name, or draw it if you only remember its shape.
    </p>

    <div class="mt-6 grid gap-6 lg:grid-cols-[1fr_auto]">
      <section aria-labelledby="type-h">
        <h2 id="type-h" class="sr-only">Search</h2>
        <label class="block text-sm font-semibold" for="signs-search"
          >Number, reading or name</label
        >
        <input
          id="signs-search"
          v-model="QUERY"
          type="search"
          autocomplete="off"
          placeholder="AB81, ku, VIN…"
          class="mt-1 w-full max-w-md rounded border border-ink/30 bg-white px-3 py-1.5"
          @keydown.enter.prevent="SHOWN.length && open(SHOWN[0].sign)"
        />
        <p class="mt-3 text-sm text-ink/70" role="status">
          {{
            QUERY.trim()
              ? `${SHOWN.length} match${SHOWN.length === 1 ? '' : 'es'}`
              : `${CATALOGUE.length} signs`
          }}
        </p>
        <ul
          class="mt-2 grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2"
          data-testid="sign-grid"
        >
          <li v-for="sign in SHOWN" :key="sign.sign">
            <RouterLink
              :to="`/signs/${encodeURIComponent(sign.sign)}`"
              class="flex items-center gap-2 rounded-lg bg-card p-2 hover:bg-bar"
              data-testid="sign-card-link"
            >
              <SignPreview
                :sign="sign.sign"
                :glyph="sign.glyph ?? ''"
                :preview-url="sign.preview_url"
                :size="44"
              />
              <span class="min-w-0">
                <span class="block font-semibold">{{ sign.sign }}</span>
                <span v-if="sign.reading" class="block text-sm text-ink/70">{{
                  sign.reading
                }}</span>
              </span>
            </RouterLink>
          </li>
        </ul>
      </section>

      <section
        class="rounded-2xl bg-card p-4 lg:sticky lg:top-4 lg:self-start"
        aria-labelledby="draw-h"
      >
        <h2 id="draw-h" class="font-bold">Draw it</h2>
        <SketchPad class="mt-2" @pick="open" />
      </section>
    </div>
  </main>
</template>
