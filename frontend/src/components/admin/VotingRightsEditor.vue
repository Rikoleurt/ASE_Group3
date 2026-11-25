<script setup>
// An account's voting rights on editions (workbench, story E): shown with the latest change and
// its reason; an admin removes or restores them with a reason of at least 15 characters, which
// the account is shown. Its votes are kept but not counted while they are removed.
import { computed, onMounted, ref } from 'vue'
import { sessionFetch } from '../../state/session'

const props = defineProps({ user: { type: Object, required: true } })
const emit = defineEmits(['close'])
const MIN_REASON = 15

const RIGHTS = ref(null)
const REASON = ref('')
const ERROR = ref('')
const SAVING = ref(false)
const REASON_OK = computed(() => REASON.value.trim().split(/\s+/).join(' ').length >= MIN_REASON)

async function detail(response, fallback) {
  const body = await response.json().catch(() => null)
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail))
    return body.detail.map((item) => item.msg?.replace(/^Value error, /, '')).join(' ')
  return fallback
}

onMounted(async () => {
  try {
    const response = await sessionFetch(`/api/admin/users/${props.user.id}/voting`)
    if (!response.ok) throw new Error(await detail(response, 'Voting rights could not be loaded.'))
    RIGHTS.value = await response.json()
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? "Couldn't reach the server." : failure.message
  }
})

async function change() {
  SAVING.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(`/api/admin/users/${props.user.id}/voting`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ can_vote: !RIGHTS.value.can_vote, reason: REASON.value }),
    })
    if (!response.ok) throw new Error(await detail(response, 'The change could not be saved.'))
    RIGHTS.value = await response.json()
    REASON.value = ''
  } catch (failure) {
    ERROR.value = failure instanceof TypeError ? "Couldn't reach the server." : failure.message
  } finally {
    SAVING.value = false
  }
}
</script>

<template>
  <section
    class="rounded-xl bg-card p-4"
    :aria-label="`Voting rights of ${user.username}`"
    data-testid="voting-rights"
  >
    <div class="flex items-start justify-between gap-4">
      <h3 class="font-bold">Voting rights: {{ user.username }}</h3>
      <button type="button" class="cursor-pointer text-sm underline" @click="emit('close')">
        Close
      </button>
    </div>
    <p v-if="ERROR" role="alert" class="mt-2 text-conf-low">{{ ERROR }}</p>
    <template v-if="RIGHTS">
      <p class="mt-2" data-testid="voting-status">
        {{
          RIGHTS.can_vote
            ? 'Can vote on editions.'
            : 'Cannot vote: their votes are kept but not counted.'
        }}
        <span v-if="RIGHTS.reason" class="block text-sm text-ink/70"
          >Last change by {{ RIGHTS.changed_by }}: “{{ RIGHTS.reason }}”</span
        >
      </p>
      <label class="mt-3 block text-sm font-semibold" :for="`voting-reason-${user.id}`">
        Reason (shown to {{ user.username }}; at least {{ MIN_REASON }} characters)
      </label>
      <textarea
        :id="`voting-reason-${user.id}`"
        v-model="REASON"
        maxlength="500"
        rows="2"
        class="mt-1 w-full rounded border border-ink/30 bg-white px-3 py-1.5"
      />
      <button
        type="button"
        class="mt-2 cursor-pointer rounded px-4 py-1.5 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
        :class="RIGHTS.can_vote ? 'bg-confidence-low/15 text-confidence-low' : 'bg-bar'"
        :disabled="SAVING || !REASON_OK"
        data-testid="voting-change"
        @click="change"
      >
        {{ RIGHTS.can_vote ? 'Remove voting rights' : 'Restore voting rights' }}
      </button>
    </template>
  </section>
</template>
