import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import VersionOverlay from '../components/versions/VersionOverlay.vue'
import { useGlyphActivity } from '../composables/useGlyphActivity'
import { SHOW_ACTIVITY } from '../state/preferences'
import { forgetSession, loadSession } from '../state/session'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const SESSION = { user: { id: 7, username: 'dev', email: 'd@x.co' }, csrf_token: 'csrf' }

let wrapper

afterEach(() => {
  wrapper?.unmount()
  SHOW_ACTIVITY.value = false
  forgetSession()
  vi.unstubAllGlobals()
})

function serve() {
  const fetch = vi.fn((url, options = {}) => {
    if (url === '/api/users/me') return json(SESSION)
    if (url === '/api/tablets/HT-13/glyph-activity')
      return json({ tablet: 'HT-13', counts: { 3: 2, 7: 120 } })
    if (url === '/api/glyphs/seen' && options.method === 'POST')
      return Promise.resolve({ ok: true, status: 204 })
    return json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function host(slug) {
  let api
  wrapper = mount(
    defineComponent({
      setup() {
        api = useGlyphActivity(slug)
        return () => h('p', JSON.stringify(api.COUNTS.value))
      },
    }),
  )
  return () => api
}

describe('glyph activity', () => {
  it('loads nothing until the bubbles are switched on, then remembers the choice', async () => {
    const fetch = serve()
    await loadSession()
    host(ref('HT-13'))
    await flushPromises()
    expect(fetch.mock.calls.some(([url]) => url.includes('glyph-activity'))).toBe(false)
    SHOW_ACTIVITY.value = true
    await flushPromises()
    expect(wrapper.text()).toBe('{"3":2,"7":120}')
    expect(localStorage.getItem('ase3.show-glyph-activity')).toBe('1')
  })

  it('clears a bubble when its glyph is opened, and tells the server', async () => {
    const fetch = serve()
    await loadSession()
    SHOW_ACTIVITY.value = true
    const api = host(ref('HT-13'))
    await flushPromises()
    await api().seen(3)
    await nextTick()
    expect(wrapper.text()).toBe('{"7":120}')
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/glyphs/seen')
    expect(JSON.parse(options.body)).toEqual({ tablet: 'HT-13', position: 3 })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    await api().seen(99) // nothing new there: no request
    expect(fetch.mock.calls.filter(([url]) => url === '/api/glyphs/seen')).toHaveLength(1)
  })

  it('stays empty for logged-out visitors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => json({ detail: 'Please log in.' }, 401)),
    )
    SHOW_ACTIVITY.value = true
    host(ref('HT-13'))
    await flushPromises()
    expect(wrapper.text()).toBe('{}')
  })
})

describe('activity bubbles on tablets', () => {
  const sign = (id, x) => ({
    id,
    sign: 'AB81',
    label: 'AB81 (ku)',
    reading: 'ku',
    role: 'syllabogram',
    confidence: 100,
    detection_confidence: 100,
    box: { x, y: 0.2, w: 0.1, h: 0.1 },
    candidates: [],
  })

  it('draws a count at the top-right corner of each glyph with news', () => {
    wrapper = mount(TabletOverlay, {
      props: { signs: [sign(3, 0.1), sign(4, 0.5), sign(7, 0.7)], badges: { 3: 2, 7: 120 } },
    })
    const badges = wrapper.findAll('[data-testid="glyph-badge"]')
    expect(badges.map((badge) => badge.text())).toEqual(['2', '99+'])
    expect(badges[0].attributes('style')).toContain('left: 20%')
    expect(badges[0].attributes('style')).toContain('top: 20%')
    expect(badges[0].attributes('aria-label')).toBe('2 new')
  })

  it('marks places on the compare and merge pages', () => {
    const place = {
      box: { x: 0.4, y: 0.1, w: 0.2, h: 0.1 },
      members: { scholar: { id: 3, box: { x: 0.4, y: 0.1, w: 0.2, h: 0.1 }, sign: 'AB81' } },
      status: 'agree',
    }
    wrapper = mount(VersionOverlay, {
      props: { clusters: [place, place], keys: ['scholar'], badges: { 1: 5 } },
    })
    const badges = wrapper.findAll('[data-testid="glyph-badge"]')
    expect(badges.map((badge) => badge.text())).toEqual(['5'])
    expect(badges[0].attributes('style')).toContain('left: 60%')
  })
})
