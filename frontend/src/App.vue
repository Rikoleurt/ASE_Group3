<script setup>
import { onMounted, ref } from 'vue'

const loading = ref(true)
const backendStatus = ref('')
const backendMessage = ref('')
const errorMessage = ref('')

onMounted(async () => {
  try {
    const response = await fetch('/api/health')

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`)
    }

    const data = await response.json()

    backendStatus.value = data.status
    backendMessage.value = data.message
  } catch (error) {
    console.error(error)
    errorMessage.value = 'No connexion between backend and frontend'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main>
    <h1>ASE Group 3</h1>

    <p v-if="loading">
      Connexion test
    </p>

    <div v-else-if="errorMessage">
      {{ errorMessage }}
    </div>

    <div v-else>
      <p>Frontend connected to backend</p>
      <p>Status : {{ backendStatus }}</p>
      <p>Message : {{ backendMessage }}</p>
    </div>
  </main>
</template>
