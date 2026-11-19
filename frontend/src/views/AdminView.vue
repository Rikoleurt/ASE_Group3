<script setup>
// Admins find users and grant or remove the admin and reviewer roles (#80).
// The server checks the role on every request; this page only hides what it would refuse.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { loadSession, sessionFetch, sessionUser } from '../state/session'

const PAGE_SIZE = 50
const ROLES = [
  { key: 'admin', label: 'Admin' },
  { key: 'reviewer', label: 'Reviewer' },
]

const router = useRouter()
const QUERY = ref('')
const USERS = ref([])
const TOTAL = ref(0)
const OFFSET = ref(0)
const LOADING = ref(false)
const ERROR = ref('')
const FORBIDDEN = ref(false)
const NOTICE = ref('')
const SAVING = ref(null)
let searched = ''

const PAGES = computed(() => ({
  from: TOTAL.value ? OFFSET.value + 1 : 0,
  to: OFFSET.value + USERS.value.length,
  previous: OFFSET.value > 0,
  next: OFFSET.value + PAGE_SIZE < TOTAL.value,
}))

const isSelf = (user) => user.id === sessionUser.value?.id
const failure = (error) => (error instanceof TypeError ? "Couldn't reach the server. Check your connection and try again." : error.message)

async function detail(response, fallback) {
  const body = await response.json().catch(() => null)
  return typeof body?.detail === 'string' ? body.detail : fallback
}

let loadId = 0
async function load(offset = 0) {
  const mine = ++loadId
  LOADING.value = true
  ERROR.value = ''
  try {
    const query = new URLSearchParams({ q: searched, limit: PAGE_SIZE, offset })
    const response = await sessionFetch(`/api/admin/users?${query}`)
    if (mine !== loadId) return
    if (response.status === 401) {
      await router.push({ path: '/login', query: { redirect: '/admin' } })
      return
    }
    if (response.status === 403) {
      FORBIDDEN.value = true
      return
    }
    if (!response.ok) throw new Error('The users could not be loaded. Please try again.')
    const page = await response.json()
    USERS.value = page.items
    TOTAL.value = page.total
    OFFSET.value = offset
  } catch (error) {
    ERROR.value = failure(error)
  } finally {
    LOADING.value = false
  }
}

function search() {
  searched = QUERY.value.trim()
  NOTICE.value = ''
  load(0)
}

// Explains why a box can't be changed, or null when it can.
function lockReason(user, role) {
  if (role === 'admin' && isSelf(user) && user.admin) return 'You cannot remove your own admin role.'
  if (role === 'reviewer' && user.reviewer_from_env) return 'Always a reviewer (set in the server settings).'
  return null
}

async function toggle(user, role, event) {
  const grant = !user[role]
  SAVING.value = `${user.id}-${role}`
  NOTICE.value = ''
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/admin/users/${user.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [role]: grant }),
    })
    if (!response.ok) throw new Error(await detail(response, 'The role could not be changed. Please try again.'))
    const updated = await response.json()
    USERS.value = USERS.value.map((row) => (row.id === updated.id ? updated : row))
    NOTICE.value = `${updated.username} is ${grant ? 'now' : 'no longer'} ${role === 'admin' ? 'an admin' : 'a reviewer'}.`
  } catch (error) {
    ERROR.value = failure(error)
    // The box flipped when clicked; put it back, since the role did not change.
    if (event?.target) event.target.checked = user[role]
  } finally {
    SAVING.value = null
  }
}

// Training export (#87): every corrected copy, plus approved label corrections.
const EXPORTING = ref('')
// Anyone can register and correct boxes: by default the export takes admins' and reviewers' copies only (#98).
const EVERYONE = ref(false)

async function download(kind) {
  EXPORTING.value = kind
  ERROR.value = ''
  try {
    const suffix = EVERYONE.value ? '?everyone=true' : ''
    const response = await sessionFetch(`${kind === 'zip' ? '/api/admin/export/corrections.zip' : '/api/admin/export/corrections'}${suffix}`)
    if (!response.ok) throw new Error(await detail(response, 'The export failed. Please try again.'))
    const blob = kind === 'zip' ? await response.blob() : new Blob([JSON.stringify(await response.json(), null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = kind === 'zip' ? 'corrections-yolo.zip' : 'corrections.json'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ERROR.value = failure(error)
  } finally {
    EXPORTING.value = ''
  }
}

onMounted(async () => {
  // The router guard usually loaded the session already; the page needs it to mark your own row.
  if (!sessionUser.value) await loadSession().catch(() => {})
  load(0)
})
</script>

<template>
  <main class="mx-auto max-w-4xl px-6 py-10">
    <h1 class="text-3xl font-bold">Admin</h1>

    <p v-if="FORBIDDEN" role="alert" class="mt-6 rounded-2xl bg-card p-6">Only admins can see this page.</p>

    <template v-else>
      <p class="mt-2 text-ink/70">
        Admins manage roles. Reviewers approve or reject sign corrections before they become training labels.
      </p>

      <section class="mt-6 rounded-2xl bg-card p-5" aria-labelledby="export-h">
        <h2 id="export-h" class="text-xl font-bold">Training data</h2>
        <p class="mt-1 text-sm text-ink/70">
          Corrected boxes, with approved sign corrections, to train the reader on. JSON matches the format of the
          training set; the YOLO zip has images, labels and the class list.
        </p>
        <label class="mt-3 flex items-center gap-2 text-sm">
          <input v-model="EVERYONE" type="checkbox" data-testid="export-everyone" />
          Include copies by all users, not only admins and reviewers (not reviewed)
        </label>
        <div class="mt-3 flex flex-wrap gap-3">
          <button type="button" class="cursor-pointer rounded border border-ink/30 px-4 py-2 hover:bg-ink/5 disabled:opacity-60" :disabled="EXPORTING !== ''" data-testid="export-json" @click="download('json')">
            {{ EXPORTING === 'json' ? 'Exporting…' : 'Export corrections (JSON)' }}
          </button>
          <button type="button" class="cursor-pointer rounded border border-ink/30 px-4 py-2 hover:bg-ink/5 disabled:opacity-60" :disabled="EXPORTING !== ''" data-testid="export-zip" @click="download('zip')">
            {{ EXPORTING === 'zip' ? 'Exporting…' : 'Export as YOLO dataset (zip)' }}
          </button>
        </div>
      </section>

      <form class="mt-6 flex flex-wrap items-end gap-3" role="search" @submit.prevent="search">
        <label class="flex flex-col gap-1 text-sm font-semibold" for="user-search">
          Find a user
          <input
            id="user-search"
            v-model="QUERY"
            type="search"
            maxlength="255"
            placeholder="Username or email"
            class="w-72 rounded border border-ink/30 bg-white px-3 py-2 font-normal"
          />
        </label>
        <button type="submit" class="cursor-pointer rounded bg-bar px-4 py-2 font-semibold hover:brightness-95">Search</button>
      </form>

      <p v-if="NOTICE" role="status" class="mt-6 rounded-lg bg-accent/10 p-3">{{ NOTICE }}</p>
      <p v-if="ERROR" role="alert" class="mt-6 text-conf-low">{{ ERROR }}</p>
      <p v-if="LOADING" role="status" class="mt-6">Loading users…</p>
      <p v-else-if="!ERROR && !USERS.length" class="mt-8 rounded-2xl bg-card p-6">No users found.</p>

      <table v-if="USERS.length" class="mt-6 w-full border-collapse text-left" data-testid="admin-users">
        <caption class="sr-only">Users and their roles</caption>
        <thead>
          <tr class="border-b border-ink/20">
            <th scope="col" class="py-2 pr-4">User</th>
            <th v-for="role in ROLES" :key="role.key" scope="col" class="py-2 pr-4 text-center">{{ role.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in USERS" :key="user.id" class="border-b border-ink/10" data-testid="admin-user">
            <th scope="row" class="py-2 pr-4 font-normal">
              <span class="font-semibold">{{ user.username }}</span>
              <span v-if="isSelf(user)" class="text-ink/70"> (you)</span>
              <span class="block text-sm text-ink/70">{{ user.email }}</span>
            </th>
            <td v-for="role in ROLES" :key="role.key" class="py-2 pr-4 text-center">
              <input
                type="checkbox"
                class="h-5 w-5 cursor-pointer accent-accent disabled:cursor-not-allowed"
                :checked="user[role.key] || (role.key === 'reviewer' && user.reviewer_from_env)"
                :disabled="SAVING !== null || lockReason(user, role.key) !== null"
                :title="lockReason(user, role.key) ?? undefined"
                :aria-label="`${role.label}: ${user.username}`"
                :data-testid="`role-${role.key}`"
                @change="toggle(user, role.key, $event)"
              />
              <span v-if="lockReason(user, role.key)" class="block text-xs text-ink/60">{{ lockReason(user, role.key) }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <nav v-if="TOTAL > PAGE_SIZE" aria-label="Pages" class="mt-4 flex items-center gap-4">
        <button type="button" class="cursor-pointer rounded px-3 py-1 hover:bg-bar disabled:opacity-50" :disabled="!PAGES.previous || LOADING" @click="load(OFFSET - PAGE_SIZE)">Previous</button>
        <span>{{ PAGES.from }}–{{ PAGES.to }} of {{ TOTAL }}</span>
        <button type="button" class="cursor-pointer rounded px-3 py-1 hover:bg-bar disabled:opacity-50" :disabled="!PAGES.next || LOADING" @click="load(OFFSET + PAGE_SIZE)">Next</button>
      </nav>
    </template>
  </main>
</template>
