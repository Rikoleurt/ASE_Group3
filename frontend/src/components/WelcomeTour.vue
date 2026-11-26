<script setup>
// The home page's welcome for first-time visitors: points to the tutorials until dismissed (in this
// browser) or until every lesson has been watched.
import { computed } from 'vue'
import { LESSONS, WATCHED, WELCOME_DISMISSED, dismissWelcome } from '../state/tutorials'

const SHOWN = computed(() => !WELCOME_DISMISSED.value && WATCHED.value.length < LESSONS.length)
const NEXT = computed(
  () => LESSONS.find((lesson) => !WATCHED.value.includes(lesson.id)) ?? LESSONS[0],
)
const STARTED = computed(() => WATCHED.value.length > 0)
</script>

<template>
  <section
    v-if="SHOWN"
    class="w-full rounded-2xl bg-card p-6 text-left shadow-sm"
    aria-labelledby="welcome-h"
    data-testid="welcome-tour"
  >
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div class="max-w-xl">
        <h2 id="welcome-h" class="text-xl font-bold">
          {{ STARTED ? 'Pick up the tour where you left off' : 'New here? Take the tour' }}
        </h2>
        <p class="mt-1 text-ink/80">
          {{ LESSONS.length }} short videos, recorded from this site, show how to read a tablet,
          correct its signs and build an edition with other scholars.
          <template v-if="STARTED"
            >You have watched {{ WATCHED.length }} of {{ LESSONS.length }}.</template
          >
        </p>
      </div>
      <button
        type="button"
        class="inline-flex min-h-10 cursor-pointer items-center rounded-lg px-3 text-sm underline hover:bg-bar/40"
        data-testid="welcome-dismiss"
        @click="dismissWelcome"
      >
        Not now
      </button>
    </div>
    <div class="mt-4 flex flex-wrap items-center gap-3">
      <RouterLink
        :to="`/tutorials/${NEXT.id}`"
        class="inline-flex min-h-10 items-center rounded-lg bg-bar px-5 py-2 font-semibold hover:brightness-95"
        data-testid="welcome-start"
        >{{ STARTED ? `Continue: ${NEXT.title}` : 'Start with the tour' }}</RouterLink
      >
      <RouterLink to="/tutorials" class="inline-flex min-h-10 items-center underline"
        >See all lessons</RouterLink
      >
    </div>
  </section>
</template>
