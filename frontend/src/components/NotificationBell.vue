<script setup>
// Notifications (workbench, story I): a bell with how many are unread, checked every minute while
// the page is visible (no live connection), and a list that marks them read.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionFetch } from '../state/session'

const POLL_MS = 60_000
const router = useRouter()
const UNREAD = ref(0)
const OPEN = ref(false)
const ITEMS = ref([])
const NEXT = ref(null)
const LOADING = ref(false)
const ERROR = ref('')
let timer = null

async function count() {
  if (document.visibilityState === 'hidden') return
  const response = await fetch('/api/notifications/unread-count').catch(() => null)
  if (response?.ok) UNREAD.value = (await response.json()).unread
}

async function load(more = false) {
  LOADING.value = true
  ERROR.value = ''
  try {
    const query = new URLSearchParams({
      limit: '20',
      ...(more && NEXT.value ? { before: String(NEXT.value) } : {}),
    })
    const response = await fetch(`/api/notifications?${query}`)
    if (!response.ok) throw new Error('Notifications could not be loaded.')
    const page = await response.json()
    ITEMS.value = more ? [...ITEMS.value, ...page.items] : page.items
    NEXT.value = page.next_before
    UNREAD.value = page.unread
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? "Couldn't reach the server." : failure.message
  } finally {
    LOADING.value = false
  }
}

async function toggle() {
  OPEN.value = !OPEN.value
  if (OPEN.value) await load()
}

async function markRead(ids) {
  const response = await sessionFetch('/api/notifications/read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ids ? { ids } : {}),
  }).catch(() => null)
  if (!response?.ok) return
  UNREAD.value = (await response.json()).unread
  ITEMS.value = ITEMS.value.map((item) =>
    !ids || ids.includes(item.id) ? { ...item, read: true } : item,
  )
}

async function open(item) {
  if (!item.read) await markRead([item.id])
  OPEN.value = false
  if (item.link) await router.push(item.link)
}

function close(event) {
  if (OPEN.value && event.key === 'Escape') OPEN.value = false
}

const when = (stamp) =>
  new Date(stamp).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

onMounted(() => {
  count()
  timer = setInterval(count, POLL_MS)
  document.addEventListener('visibilitychange', count)
  document.addEventListener('keydown', close)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', count)
  document.removeEventListener('keydown', close)
})
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-full hover:bg-black/10"
      :aria-expanded="OPEN"
      :aria-label="UNREAD ? `Notifications: ${UNREAD} unread` : 'Notifications'"
      data-testid="bell"
      @click="toggle"
    >
      <svg class="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M6 8a6 6 0 1112 0c0 7 3 9 3 9H3s3-2 3-9zM10 21a2 2 0 004 0"
        />
      </svg>
      <span
        v-if="UNREAD"
        class="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-confidence-low px-1 text-[10px] font-bold text-white"
        data-testid="unread"
        >{{ UNREAD > 99 ? '99+' : UNREAD }}</span
      >
    </button>
    <section
      v-if="OPEN"
      class="absolute right-0 z-40 mt-2 w-[min(24rem,90vw)] rounded-xl bg-page p-3 text-ink shadow-xl ring-1 ring-ink/10"
      aria-label="Notifications"
      data-testid="notifications"
    >
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-bold">Notifications</h2>
        <button
          v-if="UNREAD"
          type="button"
          class="cursor-pointer text-sm underline"
          data-testid="read-all"
          @click="markRead(null)"
        >
          Mark all read
        </button>
      </div>
      <p v-if="ERROR" role="alert" class="mt-2 text-sm text-confidence-low">{{ ERROR }}</p>
      <p v-else-if="!LOADING && !ITEMS.length" class="mt-2 text-sm text-ink/70">
        Nothing yet. You will hear here when someone shares, comments, mentions you, backs your
        edition or merges your boxes.
      </p>
      <ul class="mt-2 max-h-96 overflow-auto">
        <li v-for="item in ITEMS" :key="item.id">
          <button
            type="button"
            class="w-full cursor-pointer rounded-lg px-2 py-1.5 text-left text-sm hover:bg-bar"
            :class="{ 'font-semibold': !item.read }"
            data-testid="notification"
            @click="open(item)"
          >
            <span class="flex items-start gap-2">
              <span
                v-if="!item.read"
                class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent"
                aria-label="unread"
              />
              <span>
                {{ item.message }}
                <span class="block text-xs font-normal text-ink/60">{{
                  when(item.created_at)
                }}</span>
              </span>
            </span>
          </button>
        </li>
      </ul>
      <button
        v-if="NEXT"
        type="button"
        class="mt-1 cursor-pointer text-sm underline"
        :disabled="LOADING"
        @click="load(true)"
      >
        Older
      </button>
    </section>
  </div>
</template>
