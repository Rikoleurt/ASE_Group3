<script setup>
// Who a corrected copy is shared with (#84): named people at a level, and every logged-in
// user at a level. Shown to the owner and to people who manage the copy.
import { onMounted, ref, watch } from 'vue'
import { sessionFetch } from '../../state/session'

const props = defineProps({ setId: { type: Number, required: true } })
const emit = defineEmits(['close', 'changed'])

const LEVELS = [
  { value: 'view', label: 'Can view', hint: 'See the boxes, the reading and the change history.' },
  { value: 'comment', label: 'Can comment', hint: 'Also comment on boxes.' },
  { value: 'edit', label: 'Can edit', hint: 'Also move, draw, delete and name boxes, and undo changes.' },
  { value: 'manage', label: 'Can manage', hint: 'Also share the copy and change who has access.' },
]
const EVERYONE = [{ value: 'none', label: 'No access' }, ...LEVELS.filter((level) => level.value !== 'manage')]

const SHARING = ref(null)
const ERROR = ref('')
const BUSY = ref(false)
const QUERY = ref('')
const MATCHES = ref([])
const NEW_LEVEL = ref('view')
let searchTimer = null
let searchId = 0

async function call(url, options = {}) {
  ERROR.value = ''
  BUSY.value = true
  try {
    const response = await sessionFetch(url, {
      ...options,
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    })
    if (response.status === 204) return null
    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'Sharing could not be changed. Please try again.')
    return body
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? 'Couldnt reach the server' : failure.message
    return undefined
  } finally {
    BUSY.value = false
  }
}

async function load() {
  const body = await call(`/api/box-sets/${props.setId}/shares`)
  if (body) SHARING.value = body
}

async function update(result) {
  if (result) {
    SHARING.value = result
    emit('changed', result)
  }
}

async function share(user, permission) {
  await update(await call(`/api/box-sets/${props.setId}/shares/${user.id}`, { method: 'PUT', body: JSON.stringify({ permission }) }))
  QUERY.value = ''
  MATCHES.value = []
}

async function unshare(user) {
  if ((await call(`/api/box-sets/${props.setId}/shares/${user.id}`, { method: 'DELETE' })) === null) {
    SHARING.value = { ...SHARING.value, shares: SHARING.value.shares.filter((item) => item.user.id !== user.id) }
    emit('changed', SHARING.value)
  }
}

async function setEveryone(permission) {
  await update(await call(`/api/box-sets/${props.setId}/everyone`, { method: 'PUT', body: JSON.stringify({ permission }) }))
}

// Search as the user types, a moment after they stop; older answers are dropped.
watch(QUERY, (value) => {
  clearTimeout(searchTimer)
  const query = value.trim()
  if (query.length < 2) {
    MATCHES.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    const mine = ++searchId
    const response = await sessionFetch(`/api/users/search?q=${encodeURIComponent(query)}`).catch(() => null)
    if (mine !== searchId || !response?.ok) return
    const shared = new Set((SHARING.value?.shares ?? []).map((item) => item.user.id))
    MATCHES.value = (await response.json()).filter((user) => !shared.has(user.id))
  }, 250)
})

onMounted(load)
</script>

<template>
  <section class="rounded-3xl border border-ink/15 bg-white p-5 shadow-lg" role="dialog" aria-labelledby="share-h" data-testid="share-dialog" @keydown.esc="emit('close')">
    <div class="flex items-center justify-between">
      <h2 id="share-h" class="text-xl font-bold">Share this copy</h2>
      <button type="button" class="cursor-pointer underline" @click="emit('close')">Close</button>
    </div>
    <p v-if="ERROR" role="alert" class="mt-3 text-confidence-low">{{ ERROR }}</p>
    <p v-if="!SHARING && !ERROR" role="status" class="mt-3">Loading…</p>

    <template v-if="SHARING">
      <label class="mt-4 block text-sm font-semibold" for="share-search">Add people</label>
      <div class="mt-1 flex gap-2">
        <input id="share-search" v-model="QUERY" type="search" autocomplete="off" placeholder="Username" class="min-w-0 flex-1 rounded border border-ink/30 px-3 py-1.5" />
        <select v-model="NEW_LEVEL" class="rounded border border-ink/30 px-2" aria-label="Level for the person you add" data-testid="new-level">
          <option v-for="level in LEVELS" :key="level.value" :value="level.value">{{ level.label }}</option>
        </select>
      </div>
      <ul v-if="MATCHES.length" class="mt-1 rounded border border-ink/15" data-testid="user-matches">
        <li v-for="user in MATCHES" :key="user.id">
          <button type="button" class="w-full cursor-pointer px-3 py-1 text-left hover:bg-bar disabled:opacity-60" :disabled="BUSY" @click="share(user, NEW_LEVEL)">
            {{ user.username }}
          </button>
        </li>
      </ul>
      <p v-else-if="QUERY.trim().length >= 2" class="mt-1 text-sm text-ink/70">Type a username; matches appear here.</p>

      <h3 class="mt-5 text-sm font-semibold">People with access</h3>
      <p v-if="!SHARING.shares.length" class="mt-1 text-sm text-ink/70">Nobody yet. Only you can see this copy{{ SHARING.everyone !== 'none' ? ', apart from everyone logged in (below)' : '' }}.</p>
      <ul class="mt-1 divide-y divide-ink/10">
        <li v-for="item in SHARING.shares" :key="item.user.id" class="flex items-center gap-2 py-2" data-testid="share-row">
          <span class="flex-1">{{ item.user.username }}</span>
          <select
            :value="item.permission"
            :disabled="BUSY"
            class="rounded border border-ink/30 px-2 py-1"
            :aria-label="`Level for ${item.user.username}`"
            @change="share(item.user, $event.target.value)"
          >
            <option v-for="level in LEVELS" :key="level.value" :value="level.value">{{ level.label }}</option>
          </select>
          <button type="button" class="cursor-pointer text-sm underline disabled:opacity-60" :disabled="BUSY" :aria-label="`Remove ${item.user.username}`" @click="unshare(item.user)">Remove</button>
        </li>
      </ul>

      <label class="mt-5 block text-sm font-semibold" for="share-everyone">Everyone logged in</label>
      <select id="share-everyone" :value="SHARING.everyone" :disabled="BUSY" class="mt-1 rounded border border-ink/30 px-2 py-1" @change="setEveryone($event.target.value)">
        <option v-for="level in EVERYONE" :key="level.value" :value="level.value">{{ level.label }}</option>
      </select>

      <details class="mt-5 text-sm text-ink/70">
        <summary class="cursor-pointer">What the levels allow</summary>
        <dl class="mt-2">
          <template v-for="level in LEVELS" :key="level.value"><dt class="font-semibold">{{ level.label }}</dt><dd class="mb-1">{{ level.hint }}</dd></template>
          <dt class="font-semibold">Owner</dt><dd>Everything, and deleting the copy. Only the owner can delete it.</dd>
        </dl>
      </details>
    </template>
  </section>
</template>
