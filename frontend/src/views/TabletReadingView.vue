<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

// One tablet for now: HT 13 is the tablet the demo image shows.
const slug = 'HT-13'
const imageUrl = '/api/tablet-demo/ht13?annotated=false'

const reading = ref(null)
const fractionSigns = ref(null)
const loading = ref(true)
const error = ref('')

const VERDICTS = {
  BALANCED: { text: 'Balances', class: 'text-confidence-high' },
  OVERFULL: { text: 'Does not balance', class: 'text-confidence-low' },
  ERROR_NO_DAMAGE: { text: 'Does not balance', class: 'text-confidence-low' },
  IMPOSSIBLE: { text: 'Cannot balance', class: 'text-confidence-low' },
}

const UNICODE_FRACTIONS = {
  '1/2': '½', '1/3': '⅓', '2/3': '⅔', '1/4': '¼', '3/4': '¾', '1/5': '⅕', '2/5': '⅖',
  '1/6': '⅙', '1/8': '⅛', '1/10': '⅒',
}

// "261/2" -> "130½", "-1/2" -> "−½"
function formatValue(value) {
  if (value === null || value === undefined) return '?'
  const negative = value.startsWith('-')
  const [num, den] = value.replace('-', '').split('/').map(Number)
  if (!den) return (negative ? '−' : '') + num
  const whole = Math.floor(num / den)
  const rest = `${num % den}/${den}`
  const part = UNICODE_FRACTIONS[rest] || rest
  return (negative ? '−' : '') + (whole ? `${whole}${part}` : part)
}

function verdictOf(section) {
  return VERDICTS[section.verdict] || { text: section.verdict, class: 'text-confidence-mid' }
}

function tokenClass(token) {
  if (token.kind === 'number') return 'font-bold'
  if (token.kind === 'fraction') return 'font-bold text-accent'
  if (token.kind === 'damage') return 'text-ink/50'
  return ''
}

const damagedLines = computed(() =>
  (reading.value?.sections || []).flatMap((s) => s.entries.filter((e) => e.quantity.damaged).map((e) => e.line)),
)

async function getJson(url) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    reading.value = await getJson(`/api/tablets/${slug}/reading`)
  } catch {
    error.value = 'The tablet reading could not be loaded. Check that the backend is running.'
    loading.value = false
    return
  }
  try {
    fractionSigns.value = await getJson(`/api/tablets/${slug}/fraction-signs`)
  } catch {
    fractionSigns.value = { available: false, signs: [] }
  }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <main class="flex flex-col gap-6 p-6 md:flex-row">
    <section class="md:w-1/3">
      <img :src="imageUrl" alt="HT 13 tablet drawing" width="1367" height="2253" class="block h-auto w-full bg-white" />
      <RouterLink to="/tablet-demo" class="mt-3 inline-block font-bold underline hover:text-accent">
        See sign detection on this tablet
      </RouterLink>
    </section>

    <div class="hidden w-0.5 bg-ink md:block" />

    <section class="flex flex-col gap-6 md:flex-1">
      <p v-if="loading" role="status">Reading the tablet…</p>
      <p v-else-if="error" role="alert" class="rounded-3xl bg-card p-6 text-confidence-low">{{ error }}</p>

      <template v-if="reading">
        <header class="rounded-3xl bg-card p-6">
          <h1 class="text-3xl font-bold">{{ reading.id }}</h1>
          <p class="mt-1 text-ink/70">
            {{ [reading.site, reading.period, reading.scribe].filter(Boolean).join(' · ') }}
          </p>
          <a v-if="reading.url" :href="reading.url" target="_blank" rel="noopener" class="mt-2 inline-block underline hover:text-accent">
            View on lineara.eu
          </a>
        </header>

        <section class="rounded-3xl bg-card p-6" aria-labelledby="transcription-title">
          <h2 id="transcription-title" class="text-xl font-bold">Transcription</h2>
          <ol class="mt-4 space-y-1 font-mono">
            <li v-for="line in reading.lines" :key="line.number" data-testid="line" class="flex gap-3">
              <span class="w-6 shrink-0 text-right text-ink/50">{{ line.number }}</span>
              <span class="flex flex-wrap gap-x-2">
                <span
                  v-for="(token, i) in line.tokens.filter((t) => t.kind !== 'divider')"
                  :key="i"
                  :class="tokenClass(token)"
                  :title="token.kind === 'fraction' && token.value ? `${token.text} = ${formatValue(token.value)}` : undefined"
                >{{ token.text }}</span>
              </span>
            </li>
          </ol>
          <p class="mt-3 text-sm text-ink/70">
            Syllables as read by SigLA; numbers in bold; fraction signs in colour; [ ] marks a break in the clay.
          </p>
        </section>

        <section
          v-for="(section, index) in reading.sections"
          :key="index"
          class="rounded-3xl bg-card p-6"
          aria-labelledby="arithmetic-title"
        >
          <h2 id="arithmetic-title" class="text-xl font-bold">Arithmetic check</h2>
          <table class="mt-4 w-full text-left">
            <thead>
              <tr class="text-ink/70">
                <th class="py-1 font-normal">Line</th>
                <th class="py-1 font-normal">Word</th>
                <th class="py-1 text-right font-normal">Amount</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-ink/10">
              <tr v-for="entry in section.entries" :key="entry.line">
                <td class="py-1">{{ entry.line }}</td>
                <td class="py-1">{{ entry.word || '—' }}</td>
                <td class="py-1 text-right">
                  {{ formatValue(entry.quantity.value) }}<span v-if="entry.quantity.damaged" class="text-ink/50"> (broken)</span>
                </td>
              </tr>
              <tr class="font-bold">
                <td class="py-1">{{ section.total.line }}</td>
                <td class="py-1">{{ section.total.marker }} (total)</td>
                <td class="py-1 text-right">{{ formatValue(section.total.quantity.value) }}</td>
              </tr>
            </tbody>
          </table>

          <p class="mt-4">
            The entries add up to <strong>{{ formatValue(section.entries_value) }}</strong>; the scribe's total is
            <strong>{{ formatValue(section.total.quantity.value) }}</strong>.
          </p>
          <p class="mt-2 text-lg font-bold" data-testid="verdict">
            <span :class="verdictOf(section).class">{{ verdictOf(section).text }}</span>
            <span v-if="section.residual && section.residual !== '0'"> (off by {{ formatValue(section.residual) }})</span>
          </p>
          <p class="mt-1">{{ section.means }}</p>
          <p v-if="damagedLines.length" class="mt-2 text-sm">
            Line {{ damagedLines.join(', ') }} is broken, so its amount may be incomplete, but a break can only hide
            more, never less.
          </p>
          <p
            v-if="reading.upstream_arithmetic && section.verdict !== 'BALANCED' && section.integer_sum === section.total.quantity.integer"
            class="mt-2 text-sm"
          >
            lineara.eu reports “{{ reading.upstream_arithmetic.detail }}”: it checks whole numbers only, so it misses
            that the fraction signs do not add up.
          </p>
          <p class="mt-3 text-sm text-ink/70">Fraction values from Corazza et al. (2021).</p>
        </section>

        <section class="rounded-3xl bg-card p-6" aria-labelledby="fractions-title">
          <h2 id="fractions-title" class="text-xl font-bold">Fraction signs, identified by shape</h2>
          <p class="mt-2 text-sm">
            Each fraction sign's drawing is compared with
            {{ fractionSigns?.references || 'every' }} drawings from other tablets, with no training. This was measured
            at 88% correct on fraction signs, so only fraction signs are attempted.
          </p>

          <p v-if="!fractionSigns" role="status" class="mt-4">Comparing shapes…</p>
          <p v-else-if="!fractionSigns.available" class="mt-4">
            Sign drawings are not downloaded yet. Run <code>python -m la.cli images</code> in
            <code>fraction-solver/</code> to enable this.
          </p>
          <ul v-else class="mt-4 grid grid-cols-2 gap-6 lg:grid-cols-3">
            <li v-for="sign in fractionSigns.signs" :key="sign.position" data-testid="fraction-sign" class="text-sm">
              <div class="mb-2 flex h-32 items-center justify-center rounded bg-white p-2">
                <img :src="`/api${sign.image}`" :alt="`Fraction sign at position ${sign.position}`" class="max-h-full max-w-full" />
              </div>
              <p class="font-bold">
                Best match: {{ sign.guesses[0]?.label }}
                <span :class="sign.correct ? 'text-confidence-high' : 'text-confidence-low'">
                  {{ sign.correct ? '✓ matches' : '✗ differs from' }} transcription ({{ sign.transcribed.label }})
                </span>
              </p>
              <p class="text-ink/70">Next: {{ sign.guesses.slice(1).map((g) => g.label).join(', ') }}</p>
            </li>
          </ul>
        </section>

        <p class="text-xs text-ink/70">
          {{ reading.credit.text }}
          <a :href="reading.credit.url" target="_blank" rel="noopener" class="underline">{{ reading.credit.licence }}</a>.
        </p>
      </template>
    </section>
  </main>
</template>
