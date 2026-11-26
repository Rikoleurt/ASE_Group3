<script setup>
// Tutorials: short walkthroughs of each feature, recorded from the real app, for new users.
// The lesson list remembers (in this browser) which videos were watched.
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LESSONS, SECTIONS, WATCHED, markWatched, posterUrl, videoUrl } from '../state/tutorials'

const route = useRoute()
const router = useRouter()
const PLAYER = ref(null)
const VIDEO_FAILED = ref(false)

const LESSON = computed(
  () => LESSONS.find((lesson) => lesson.id === route.params.lesson) ?? LESSONS[0],
)
const INDEX = computed(() => LESSONS.indexOf(LESSON.value))
const NEXT = computed(() => LESSONS[INDEX.value + 1] ?? null)
const DONE = computed(() => WATCHED.value.length)
const PERCENT = computed(() => Math.round((DONE.value / LESSONS.length) * 100))

watch(LESSON, () => {
  VIDEO_FAILED.value = false
})

function open(lesson, play = false) {
  router.push(`/tutorials/${lesson.id}`)
  if (play) nextTick(() => PLAYER.value?.play?.()?.catch?.(() => {}))
}

function ended() {
  markWatched(LESSON.value.id)
}
</script>

<template>
  <main class="mx-auto max-w-6xl px-6 py-10">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold">Tutorials</h1>
        <p class="mt-1 max-w-2xl text-ink/80">
          Short videos that show how to use the workbench, recorded from the real site. Start at the
          top, or jump to what you need.
        </p>
      </div>
      <div class="w-full max-w-xs" data-testid="tutorial-progress">
        <p class="text-sm font-semibold">{{ DONE }} of {{ LESSONS.length }} watched</p>
        <div
          class="mt-1 h-2 overflow-hidden rounded-full bg-card"
          role="progressbar"
          :aria-valuenow="DONE"
          aria-valuemin="0"
          :aria-valuemax="LESSONS.length"
          aria-label="Tutorials watched"
        >
          <div
            class="h-full rounded-full bg-bar transition-[width]"
            :style="{ width: `${PERCENT}%` }"
          />
        </div>
      </div>
    </div>

    <div class="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section class="min-w-0" aria-labelledby="lesson-h" data-testid="lesson">
        <div class="overflow-hidden rounded-2xl bg-ink shadow-sm">
          <video
            v-if="!VIDEO_FAILED"
            ref="PLAYER"
            :key="LESSON.id"
            class="aspect-[16/10] w-full bg-ink"
            :src="videoUrl(LESSON)"
            :poster="posterUrl(LESSON)"
            controls
            playsinline
            preload="metadata"
            :aria-label="`Video: ${LESSON.title}`"
            data-testid="lesson-video"
            @ended="ended"
            @error="VIDEO_FAILED = true"
          />
          <div
            v-else
            class="flex aspect-[16/10] w-full items-center justify-center p-6 text-center text-page"
            role="alert"
            data-testid="lesson-video-missing"
          >
            This video could not be loaded. The steps below show what it covers.
          </div>
        </div>

        <p class="mt-5 text-sm font-semibold tracking-wide text-ink/80 uppercase">
          {{ LESSON.section }} · lesson {{ INDEX + 1 }} of {{ LESSONS.length }}
        </p>
        <h2 id="lesson-h" class="mt-1 text-2xl font-bold">{{ LESSON.title }}</h2>
        <p class="mt-2 max-w-2xl text-lg">{{ LESSON.summary }}</p>

        <h3 class="mt-6 font-bold">In this video</h3>
        <ol class="mt-2 max-w-2xl list-decimal space-y-1.5 pl-6" data-testid="lesson-steps">
          <li v-for="step in LESSON.steps" :key="step">{{ step }}</li>
        </ol>

        <div class="mt-6 flex flex-wrap items-center gap-3">
          <RouterLink
            :to="LESSON.tryIt.to"
            class="inline-flex min-h-10 items-center rounded-lg bg-bar px-5 py-2 font-semibold hover:brightness-95"
            data-testid="try-it"
            >{{ LESSON.tryIt.label }}</RouterLink
          >
          <button
            v-if="!WATCHED.includes(LESSON.id)"
            type="button"
            class="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-ink/30 px-4 py-2 hover:bg-card"
            data-testid="mark-watched"
            @click="markWatched(LESSON.id)"
          >
            Mark as watched
          </button>
          <span
            v-else
            class="inline-flex min-h-10 items-center gap-1.5 text-better"
            data-testid="watched"
          >
            <svg class="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="m5 12.5 4.5 4.5L19 7"
              />
            </svg>
            Watched
          </span>
          <button
            v-if="NEXT"
            type="button"
            class="ml-auto inline-flex min-h-10 cursor-pointer items-center rounded-lg px-4 py-2 font-semibold underline hover:bg-card"
            data-testid="next-lesson"
            @click="open(NEXT, true)"
          >
            Next: {{ NEXT.title }} →
          </button>
        </div>
      </section>

      <nav aria-label="Lessons" class="rounded-2xl bg-card p-4" data-testid="lesson-list">
        <div v-for="section in SECTIONS" :key="section.title" class="mb-4 last:mb-0">
          <h2 class="px-2 text-sm font-bold tracking-wide text-ink/80 uppercase">
            {{ section.title }}
          </h2>
          <ul class="mt-1">
            <li v-for="lesson in section.lessons" :key="lesson.id">
              <RouterLink
                :to="`/tutorials/${lesson.id}`"
                class="flex min-h-10 items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-bar/40"
                :class="{ 'bg-bar font-semibold': lesson.id === LESSON.id }"
                :aria-current="lesson.id === LESSON.id ? 'true' : undefined"
                data-testid="lesson-link"
              >
                <span
                  class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs"
                  :class="
                    WATCHED.includes(lesson.id)
                      ? 'border-better bg-better text-white'
                      : 'border-ink/40'
                  "
                  :aria-label="WATCHED.includes(lesson.id) ? 'Watched' : undefined"
                >
                  <svg
                    v-if="WATCHED.includes(lesson.id)"
                    class="h-3.5 w-3.5"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="3"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="m5 12.5 4.5 4.5L19 7"
                    />
                  </svg>
                  <span v-else aria-hidden="true">{{
                    LESSONS.indexOf(LESSONS.find((l) => l.id === lesson.id)) + 1
                  }}</span>
                </span>
                <span>{{ lesson.title }}</span>
              </RouterLink>
            </li>
          </ul>
        </div>
      </nav>
    </div>
  </main>
</template>
