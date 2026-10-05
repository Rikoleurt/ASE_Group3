<script setup>
import { ref } from 'vue'

const originalUrl = '/api/tablet-demo/ht13?annotated=false'
const annotatedUrl = '/api/tablet-demo/ht13'
const loading = ref(true)
const failed = ref(false)

function imageFailed() {
  loading.value = false
  failed.value = true
}
</script>

<template>
  <main lang="en" class="mx-auto max-w-5xl px-5 py-10">
    <h1 class="text-3xl font-bold">HT13 tablet demo</h1>
    <p class="mt-3">Sprint 1: generic pretrained YOLO baseline (yolo26n.pt).</p>
    <p class="mt-2">
      This model is not trained to recognize Linear A characters. Predictions may be incorrect or
      empty; they are not validated character detections.
    </p>
    <p class="mt-2 text-sm">
      Inference size: 640 · Confidence threshold: 0.25. No boxes means no detections above this
      threshold.
    </p>
    <p v-if="failed" role="alert" class="mt-4 text-red-900">
      The tablet image could not be loaded. Check that the backend is running and reload this page.
    </p>
    <p v-else-if="loading" role="status" class="mt-4">Running YOLO inference…</p>

    <div class="mt-6 grid gap-6 sm:grid-cols-2">
      <figure class="rounded-xl border border-ink/15 bg-card p-4">
        <figcaption class="mb-3 font-semibold">Original HT13</figcaption>
        <img
          :src="originalUrl"
          alt="Original HT13 tablet drawing"
          width="1367"
          height="2253"
          class="h-auto w-full rounded bg-white"
          @error="imageFailed"
        />
      </figure>
      <figure class="rounded-xl border border-ink/15 bg-card p-4">
        <figcaption class="mb-3 font-semibold">Generic YOLO predictions — baseline only</figcaption>
        <img
          :src="annotatedUrl"
          alt="HT13 result from generic pretrained YOLO; predictions may be incorrect or absent"
          width="1367"
          height="2253"
          class="h-auto w-full rounded bg-white"
          @load="loading = false"
          @error="imageFailed"
        />
      </figure>
    </div>
  </main>
</template>
