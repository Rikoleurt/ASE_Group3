// Activity bubbles on a corpus tablet's glyphs (workbench, story I): per scholars' position, how
// much others commented on or changed since you last opened it. Loaded only while the bubbles
// are switched on and you are logged in; opening a glyph (`seen`) clears its bubble.
import { ref, watch } from 'vue'
import { SHOW_ACTIVITY } from '../state/preferences'
import { sessionFetch, sessionUser } from '../state/session'

export function useGlyphActivity(slug) {
  const COUNTS = ref({})
  let request = 0

  async function load() {
    const mine = ++request
    COUNTS.value = {}
    if (!SHOW_ACTIVITY.value || !sessionUser.value || !slug.value) return
    const response = await fetch(
      `/api/tablets/${encodeURIComponent(slug.value)}/glyph-activity`,
    ).catch(() => null)
    if (mine === request && response?.ok) COUNTS.value = (await response.json()).counts
  }
  watch([slug, SHOW_ACTIVITY, () => sessionUser.value?.id], load, { immediate: true })

  async function seen(position) {
    if (position == null || !sessionUser.value || !slug.value || !COUNTS.value[position]) return
    const { [position]: _cleared, ...rest } = COUNTS.value
    COUNTS.value = rest
    await sessionFetch('/api/glyphs/seen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tablet: slug.value, position: Number(position) }),
    }).catch(() => null) // the bubble comes back on the next load if this fails
  }

  return { COUNTS, seen, reload: load }
}
