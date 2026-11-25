<script setup>
// An edition's releases (workbench, story E): numbered snapshots that never change, which others
// vote on and cite. Releasing also opens the edition to everyone for viewing. Unsaved changes
// are not part of a release, so save them first.
import { onMounted, ref } from 'vue'
import { sessionFetch } from '../../state/session'

const props = defineProps({
  setId: { type: Number, required: true },
  canRelease: { type: Boolean, default: false },
  dirty: { type: Boolean, default: false },
})
const emit = defineEmits(['released'])

const RELEASES = ref([])
const NOTES = ref('')
const OPEN = ref(false)
const BUSY = ref(false)
const ERROR = ref('')

async function load() {
  const response = await sessionFetch(`/api/box-sets/${props.setId}/releases`).catch(() => null)
  if (response?.ok) RELEASES.value = await response.json()
}
onMounted(load)

async function release() {
  BUSY.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/box-sets/${props.setId}/releases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: NOTES.value.trim() || null }),
    })
    const body = await response.json().catch(() => null)
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string' ? body.detail : 'The edition could not be released.',
      )
    NOTES.value = ''
    OPEN.value = false
    emit('released', body)
    await load()
  } catch (failure) {
    ERROR.value =
      failure instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : failure.message
  } finally {
    BUSY.value = false
  }
}

const date = (value) =>
  new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
</script>

<template>
  <section class="rounded-3xl bg-card p-5" aria-labelledby="releases-h" data-testid="releases">
    <h2 id="releases-h" class="text-xl font-bold">Releases</h2>
    <p class="mt-1 text-sm text-ink/80">
      A release is a fixed snapshot that others vote on and cite; later edits do not change it.
    </p>
    <ul v-if="RELEASES.length" class="mt-2">
      <li v-for="item in RELEASES" :key="item.id" class="py-1" data-testid="release">
        <RouterLink :to="`/editions/${item.id}`" class="font-semibold underline"
          >Release {{ item.number }}</RouterLink
        >
        <span class="text-sm text-ink/80">
          · {{ date(item.created_at) }} · {{ item.box_count }} boxes</span
        >
        <span v-if="item.notes" class="block text-sm text-ink/80">{{ item.notes }}</span>
      </li>
    </ul>
    <template v-if="canRelease">
      <button
        v-if="!OPEN"
        type="button"
        class="mt-3 cursor-pointer rounded bg-bar px-4 py-1.5 font-semibold hover:brightness-95"
        data-testid="release-open"
        @click="OPEN = true"
      >
        Release this edition for voting
      </button>
      <form v-else class="mt-3" @submit.prevent="release">
        <label class="block text-sm font-semibold" for="release-notes"
          >What changed?
          <span class="font-normal text-ink/80">(optional, shown to voters)</span></label
        >
        <textarea
          id="release-notes"
          v-model="NOTES"
          maxlength="2000"
          rows="2"
          class="mt-1 w-full rounded border border-ink/30 bg-white px-3 py-1.5"
        />
        <p v-if="dirty" class="mt-1 text-sm text-confidence-low" role="alert">
          Save your changes first: unsaved changes are not released.
        </p>
        <p class="mt-1 text-sm text-ink/80">
          Releasing opens this edition to everyone logged in, to view.
        </p>
        <button
          type="submit"
          class="mt-2 cursor-pointer rounded bg-bar px-4 py-1.5 font-semibold disabled:opacity-50"
          :disabled="BUSY || dirty"
          data-testid="release-confirm"
        >
          {{ BUSY ? 'Releasing…' : `Release ${RELEASES.length + 1}` }}
        </button>
        <button type="button" class="ml-2 cursor-pointer underline" @click="OPEN = false">
          Cancel
        </button>
      </form>
    </template>
    <p v-if="ERROR" role="alert" class="mt-2 text-confidence-low">{{ ERROR }}</p>
  </section>
</template>
