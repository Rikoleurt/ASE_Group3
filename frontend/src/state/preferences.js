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

// The tablets opened most recently in this browser, newest first (workbench, story K).
const RECENT_KEY = 'ase3.recent-tablets'
const RECENT_MAX = 8

function readRecent() {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(list)
      ? list.filter((slug) => typeof slug === 'string').slice(0, RECENT_MAX)
      : []
  } catch {
    return []
  }
}

export const RECENT_TABLETS = ref(readRecent())

export function openedTablet(slug) {
  if (!slug) return
  RECENT_TABLETS.value = [slug, ...RECENT_TABLETS.value.filter((item) => item !== slug)].slice(
    0,
    RECENT_MAX,
  )
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(RECENT_TABLETS.value))
  } catch {
    // Remembered until the page is reloaded.
  }
}
