<script setup>
// The released editions of a tablet and the vote on them (workbench, story E). Each account backs
// one release per tablet; the most backed one is the tablet's community edition, unless an admin
// chose another, which is shown with the admin's reason. Admins choose or return to the vote here.
import { computed, ref, watch } from 'vue'
import { sessionAdmin, sessionFetch, sessionUser } from '../../state/session'

const props = defineProps({ slug: { type: String, required: true } })
const MIN_REASON = 15

const PAGE = ref(null)
const ERROR = ref('')
const BUSY = ref(false)
const CHOOSING = ref(null) // release id an admin is choosing, or 'clear'
const REASON = ref('')
const REASON_OK = computed(() => REASON.value.trim().split(/\s+/).join(' ').length >= MIN_REASON)

async function detail(response, fallback) {
  const body = await response.json().catch(() => null)
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail))
    return body.detail.map((item) => item.msg?.replace(/^Value error, /, '')).join(' ')
  return fallback
}

let request = 0
async function load() {
  const mine = ++request
  ERROR.value = ''
  const response = await fetch(`/api/tablets/${encodeURIComponent(props.slug)}/editions`).catch(
    () => null,
  )
  if (mine !== request) return
  if (response?.ok) PAGE.value = await response.json()
  else PAGE.value = null
}
watch([() => props.slug, () => sessionUser.value?.id], load, { immediate: true })

async function send(url, method, body) {
  BUSY.value = true
  ERROR.value = ''
  try {
    const response = await sessionFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    if (!response.ok)
      throw new Error(await detail(response, 'That did not work. Please try again.'))
    PAGE.value = await response.json()
    CHOOSING.value = null
    REASON.value = ''
  } catch (failure) {
    ERROR.value =
      failure instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : failure.message
  } finally {
    BUSY.value = false
  }
}

const base = computed(() => `/api/tablets/${encodeURIComponent(props.slug)}`)
const back = (item) => send(`${base.value}/vote`, 'PUT', { release_id: item.id })
const withdraw = () => send(`${base.value}/vote`, 'DELETE')
const choose = (item) =>
  send(`${base.value}/edition-override`, 'PUT', { release_id: item.id, comment: REASON.value })
const clear = () => send(`${base.value}/edition-override/clear`, 'POST', { comment: REASON.value })

function name(item) {
  return `${item.title || `${item.owner}'s edition`}, release ${item.number}`
}

function backers(item) {
  const people = `${item.votes} backer${item.votes === 1 ? '' : 's'}`
  return item.reviewer_votes
    ? `${people}, ${item.reviewer_votes} of them reviewer${item.reviewer_votes === 1 ? '' : 's'}`
    : people
}

const date = (value) =>
  new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
</script>

<template>
  <section
    v-if="PAGE"
    class="rounded-2xl bg-card p-4"
    aria-labelledby="editions-h"
    data-testid="editions"
  >
    <h3 id="editions-h" class="font-bold">Editions</h3>
    <p
      v-if="PAGE.override"
      class="mt-2 rounded-lg border-l-4 border-accent bg-white/60 p-2 text-sm"
      role="note"
      data-testid="override"
    >
      <strong>Chosen by an admin</strong> ({{ PAGE.override.admin ?? 'a former admin' }},
      {{ date(PAGE.override.created_at) }}): “{{ PAGE.override.comment }}” The votes are still shown
      below.
    </p>
    <p v-if="!PAGE.items.length" class="mt-1 text-sm text-ink/70">
      No released editions yet. Merge versions into an edition and release it for others to vote on.
    </p>
    <p
      v-else-if="!PAGE.voting.allowed"
      class="mt-1 text-sm text-ink/70"
      data-testid="voting-blocked"
    >
      {{ PAGE.voting.reason }}
    </p>
    <ul class="mt-2">
      <li
        v-for="item in PAGE.items"
        :key="item.id"
        class="border-t border-ink/10 py-2 first:border-t-0"
        data-testid="edition"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span
            v-if="item.accepted"
            class="rounded bg-confidence-high/20 px-1.5 text-xs font-semibold"
            data-testid="community-edition"
            >Community edition</span
          >
          <RouterLink
            :to="`/editions/${item.id}`"
            class="font-semibold underline-offset-2 hover:underline"
            >{{ name(item) }}</RouterLink
          >
          <span class="text-sm text-ink/60"
            >· {{ backers(item) }} · {{ item.box_count }} boxes</span
          >
        </div>
        <p v-if="item.notes" class="text-sm text-ink/70">{{ item.notes }}</p>
        <div class="mt-1 flex flex-wrap gap-2 text-sm">
          <template v-if="PAGE.voting.allowed">
            <button
              v-if="PAGE.my_vote === item.id"
              type="button"
              class="cursor-pointer rounded bg-bar px-3 py-0.5 font-semibold"
              :disabled="BUSY"
              aria-pressed="true"
              data-testid="withdraw"
              @click="withdraw"
            >
              You back this · withdraw
            </button>
            <button
              v-else
              type="button"
              class="cursor-pointer rounded border border-ink/30 px-3 py-0.5 hover:bg-bar"
              :disabled="BUSY"
              aria-pressed="false"
              data-testid="back"
              @click="back(item)"
            >
              Back this edition
            </button>
          </template>
          <button
            v-if="sessionAdmin && PAGE.override?.release_id !== item.id"
            type="button"
            class="cursor-pointer underline"
            data-testid="choose"
            @click="CHOOSING = item.id"
          >
            Choose over the vote
          </button>
        </div>
        <form v-if="CHOOSING === item.id" class="mt-2" @submit.prevent="choose(item)">
          <label class="block text-sm font-semibold" :for="`choose-${item.id}`"
            >Why this edition? Everyone will see this (at least {{ MIN_REASON }} characters).</label
          >
          <textarea
            :id="`choose-${item.id}`"
            v-model="REASON"
            maxlength="1000"
            rows="2"
            class="mt-1 w-full rounded border border-ink/30 bg-white px-2 py-1"
          />
          <button
            type="submit"
            class="mt-1 cursor-pointer rounded bg-bar px-3 py-1 font-semibold disabled:opacity-50"
            :disabled="BUSY || !REASON_OK"
            data-testid="choose-confirm"
          >
            Choose it
          </button>
          <button type="button" class="ml-2 cursor-pointer underline" @click="CHOOSING = null">
            Cancel
          </button>
        </form>
      </li>
    </ul>
    <div v-if="sessionAdmin && PAGE.override" class="mt-2 text-sm">
      <button
        v-if="CHOOSING !== 'clear'"
        type="button"
        class="cursor-pointer underline"
        data-testid="clear-override"
        @click="CHOOSING = 'clear'"
      >
        Return the choice to the vote
      </button>
      <form v-else @submit.prevent="clear">
        <label class="block font-semibold" for="clear-reason"
          >Why? (kept on record, at least {{ MIN_REASON }} characters)</label
        >
        <textarea
          id="clear-reason"
          v-model="REASON"
          maxlength="1000"
          rows="2"
          class="mt-1 w-full rounded border border-ink/30 bg-white px-2 py-1"
        />
        <button
          type="submit"
          class="mt-1 cursor-pointer rounded bg-bar px-3 py-1 font-semibold disabled:opacity-50"
          :disabled="BUSY || !REASON_OK"
          data-testid="clear-confirm"
        >
          Return to the vote
        </button>
      </form>
    </div>
    <p v-if="ERROR" role="alert" class="mt-2 text-confidence-low">{{ ERROR }}</p>
  </section>
</template>
