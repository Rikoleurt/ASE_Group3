// Small per-browser preferences, remembered in localStorage when it is available (it may not be,
// e.g. in a private window): the page works the same without it, the choice is just forgotten.
import { ref, watch } from 'vue'

const KEY = 'ase3.show-glyph-activity'

function read() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

// Whether glyphs show a bubble with new activity on them (workbench, story I). Off by default.
export const SHOW_ACTIVITY = ref(read())

watch(SHOW_ACTIVITY, (on) => {
  try {
    localStorage.setItem(KEY, on ? '1' : '0')
  } catch {
    // Not remembered; it still applies until the page is reloaded.
  }
})
