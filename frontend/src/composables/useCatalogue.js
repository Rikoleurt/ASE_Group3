// The sign catalogue ({ sign, name, glyph, reading, preview_url }), loaded once per page load
// and shared by every sign picker. A failed load is retried by the next picker that asks.
import { ref } from 'vue'

const CATALOGUE = ref([])
let loading = null

export function useCatalogue() {
  if (!loading) {
    loading = fetch('/api/corrections/catalogue')
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('catalogue'))))
      .then((signs) => {
        CATALOGUE.value = Array.isArray(signs) ? signs : []
        return CATALOGUE.value
      })
      .catch(() => {
        loading = null // without the catalogue, pickers offer the model's guesses only
        return []
      })
  }
  return CATALOGUE
}

// The loaded catalogue, waiting for it if it is still loading.
export async function catalogueReady() {
  useCatalogue()
  await loading
  return CATALOGUE.value
}

// For tests: forget the cached catalogue so each test loads its own.
export function forgetCatalogue() {
  CATALOGUE.value = []
  loading = null
}
