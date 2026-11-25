// Runs before every test file: shared caches and per-browser preferences start empty in each test.
import { afterEach } from 'vitest'
import { forgetCatalogue } from './composables/useCatalogue'
import { RECENT_TABLETS, SHOW_ACTIVITY } from './state/preferences'

afterEach(() => {
  forgetCatalogue()
  SHOW_ACTIVITY.value = false
  RECENT_TABLETS.value = []
  try {
    localStorage.clear()
  } catch {
    // no storage in this environment
  }
})
