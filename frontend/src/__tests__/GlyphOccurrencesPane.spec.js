import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import GlyphOccurrencesPane from '../components/glyphs/GlyphOccurrencesPane.vue'
import { acceptSession, forgetSession } from '../state/session'

let wrapper

const credit = { licence: 'CC BY-NC-SA 4.0', url: 'https://creativecommons.org/licenses/by-nc-sa/4.0/', text: 'From SigLA.' }
const occurrence = (tablet, position, extra = {}) => ({
  tablet, title: tablet.replace('-', ' '), position, sign: 'AB77', reading: 'ka', role: 'syllabogram',
  similarity: 0.9, outlier: false, outlier_score: 0.5,
  crop_url: `/tablets/${tablet}/signs/${position}.png`,
  thumbnail_url: `/tablets/${tablet}/thumbnail.png?position=${position}`,
  box: { x: 0.1, y: 0.1, w: 0.1, h: 0.1 }, ...extra,
})
const page = (items, extra = {}) => ({ sign: 'AB77', total: items.length, limit: 30, offset: 0, ranked_by: 'glyph', items, credit, ...extra })
const ITEMS = [occurrence('HT-1', 1), occurrence('HT-2', 4, { similarity: 0.4, outlier: true }), occurrence('KN-Zb-5', 3, { crop_url: null, similarity: null })]
const comment = (id, authorId = 1) => ({
  id, sign: 'AB77', body: `note ${id}`, created_at: '2026-11-01T12:00:00Z',
  author: { id: authorId, username: authorId === 1 ? 'me' : 'other' }, targets: [{ tablet: 'HT-1', position: 1 }],
})

const selection = {
  sign: 'AB77', crop: 'data:image/png;base64,iVBORw0KGgo=',
  candidates: [
    { sign: 'AB77', label: 'ka', probability: 81 }, { sign: 'AB78', label: 'qe', probability: 12 },
    { sign: 'AB79', label: 'x', probability: 3 }, { sign: 'AB80', label: 'y', probability: 1 },
  ],
}

function json(data, status = 200) {
  return { ok: status < 400, status, json: async () => data }
}

function api(overrides = {}) {
  return vi.fn(async (url, options = {}) => {
    for (const [pattern, handler] of Object.entries(overrides)) {
      if (`${options.method ?? 'GET'} ${url}`.includes(pattern)) return handler(url, options)
    }
    if (url === '/api/users/me') return json({ user: { id: 1, username: 'me', email: 'm@x.io' }, csrf_token: 'csrf' })
    if (url.includes('/occurrences')) return json(page(ITEMS))
    if (url.includes('/annotations')) return json({ items: [comment(9), comment(8, 2)], next_before: null })
    throw new Error(`unexpected ${url}`)
  })
}

async function render(fetch, props = { selection }, loggedIn = true) {
  vi.stubGlobal('fetch', fetch)
  if (loggedIn) acceptSession({ user: { id: 1, username: 'me' }, csrf_token: 'csrf' })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  wrapper = mount(GlyphOccurrencesPane, { props, global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

const cards = () => wrapper.findAll('[data-testid="glyph-card"]')
const boxes = () => cards().map((card) => card.get('input[type="checkbox"]'))

beforeEach(() => forgetSession())
afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
  forgetSession()
})

describe('Glyph occurrences pane', () => {
  it('does nothing until a glyph is selected', async () => {
    const fetch = api()
    await render(fetch, { selection: null })
    expect(wrapper.find('[data-testid="glyph-pane"]').exists()).toBe(false)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('searches by the selected crop and shows one card per occurrence, all ticked', async () => {
    const fetch = api()
    await render(fetch)
    const search = fetch.mock.calls.find(([url]) => url.includes('/occurrences/search'))
    expect(search[0]).toBe('/api/glyphs/AB77/occurrences/search')
    expect(search[1].method).toBe('POST')
    expect(search[1].headers['X-CSRF-Token']).toBe('csrf')
    expect(search[1].body.get('file').type).toBe('image/png')
    expect(search[1].body.get('limit')).toBe('30')
    expect(cards()).toHaveLength(3)
    expect(boxes().every((box) => box.element.checked)).toBe(true)
    expect(wrapper.get('[data-testid="glyph-count"]').text()).toContain('3 occurrences of AB77, most similar to your glyph first')
    const first = cards()[0]
    expect(first.text()).toContain('HT 1')
    expect(first.text()).toContain('Similarity 0.90')
    const images = first.findAll('img')
    expect(images.map((img) => img.attributes('src'))).toEqual(['/api/tablets/HT-1/signs/1.png', '/api/tablets/HT-1/thumbnail.png?position=1'])
    expect(images.every((img) => img.attributes('loading') === 'lazy' && img.attributes('alt'))).toBe(true)
    expect(cards()[2].text()).toContain('No drawing of this sign')
    expect(cards()[2].text()).toContain('Similarity unavailable')
  })

  it('labels guesses once and never shows a small probability as 0%', async () => {
    await render(api(), { selection: { sign: 'AB45', candidates: [
      { sign: 'AB45', label: 'AB45 (de)', probability: 99.7 }, { sign: 'AB47', label: 'AB47', probability: 0.2 },
      { sign: 'A343', label: 'A343', probability: 0 },
    ] } })
    const tabs = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(tabs).toEqual(['AB45 (de) · 100%', 'AB47 · <1%', 'A343 · 0%'])
  })

  it('badges outliers in words, not only colour', async () => {
    await render(api())
    const badges = wrapper.findAll('[data-testid="outlier-badge"]')
    expect(badges).toHaveLength(1)
    expect(badges[0].text()).toBe('Possible mislabel')
    expect(cards()[1].find('[data-testid="outlier-badge"]').exists()).toBe(true)
  })

  it('is a horizontally scrolling, snapping, keyboard-reachable strip', async () => {
    await render(api())
    const strip = wrapper.get('[data-testid="glyph-strip"]')
    expect(strip.classes()).toEqual(expect.arrayContaining(['overflow-x-auto', 'snap-x']))
    expect(strip.attributes('tabindex')).toBe('0')
    expect(cards()[0].classes()).toContain('snap-start')
  })

  it('does not upload the crop for a logged-out reader: corpus order instead', async () => {
    const fetch = api({ '/api/users/me': () => json({}, 401) })
    await render(fetch, { selection }, false)
    expect(fetch.mock.calls.some(([url]) => url.includes('/occurrences/search'))).toBe(false)
    expect(fetch.mock.calls.some(([url]) => url === '/api/glyphs/AB77/occurrences?limit=30&offset=0')).toBe(true)
    expect(cards()).toHaveLength(3)
  })

  it('falls back to corpus order when the session has lapsed at search time', async () => {
    const fetch = api({ 'POST /api/glyphs/AB77/occurrences/search': () => json({ detail: 'Please log in.' }, 401) })
    await render(fetch)
    expect(fetch.mock.calls.some(([url]) => url === '/api/glyphs/AB77/occurrences?limit=30&offset=0')).toBe(true)
    expect(cards()).toHaveLength(3)
  })

  it('says so plainly when the crop is not a data URL', async () => {
    await render(api(), { selection: { sign: 'AB77', crop: 'https://example.com/x.png' } })
    expect(wrapper.get('[role="alert"]').text()).toContain('cannot be used for the comparison')
  })

  it('searches by a corpus reference glyph when there is no crop', async () => {
    const fetch = api()
    await render(fetch, { selection: { sign: 'AB77', reference: { tablet: 'HT-13', position: 9 } } })
    const url = fetch.mock.calls.find(([u]) => u.includes('/occurrences'))[0]
    expect(url).toBe('/api/glyphs/AB77/occurrences?limit=30&offset=0&ref_tablet=HT-13&ref_position=9')
  })

  it('shows tabs for the top three guesses and reloads for the one you open', async () => {
    const fetch = api({
      '/glyphs/AB78/occurrences': () => json(page([occurrence('HT-3', 2, { sign: 'AB78' })], { sign: 'AB78' })),
    })
    await render(fetch)
    const tabs = wrapper.findAll('[data-testid="glyph-tab"]')
    expect(tabs.map((tab) => tab.text())).toEqual(['AB77 (ka) · 81%', 'AB78 (qe) · 12%', 'AB79 (x) · 3%'])
    expect(tabs.map((tab) => tab.attributes('aria-selected'))).toEqual(['true', 'false', 'false'])
    await tabs[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="glyph-count"]').text()).toContain('1 occurrence of AB78')
    expect(cards()).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="glyph-tab"]')[1].attributes('aria-selected')).toBe('true')
    expect(wrapper.get('form').text()).toContain('Comment on 1 occurrence')
    expect(fetch.mock.calls.some(([url]) => url === '/api/glyphs/AB78/annotations')).toBe(true)
  })

  it('moves between tabs with the arrow keys', async () => {
    const fetch = api()
    await render(fetch)
    await wrapper.findAll('[data-testid="glyph-tab"]')[0].trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-tab"]')[1].attributes('aria-selected')).toBe('true')
    expect(fetch.mock.calls.some(([url]) => url.includes('/glyphs/AB78/occurrences'))).toBe(true)
  })

  it('selects all, none, and single occurrences, and counts them on the button', async () => {
    await render(api())
    const submit = () => wrapper.get('form button[type="submit"]')
    expect(submit().text()).toBe('Comment on 3 occurrences')
    await boxes()[1].setValue(false)
    expect(submit().text()).toBe('Comment on 2 occurrences')
    const [all, none] = wrapper.findAll('button').filter((b) => ['Select all', 'Select none'].includes(b.text()))
    await none.trigger('click')
    expect(boxes().some((box) => box.element.checked)).toBe(false)
    expect(submit().text()).toBe('Comment on 0 occurrences')
    await wrapper.get('textarea').setValue('text')
    expect(submit().attributes('disabled')).toBeDefined()
    await all.trigger('click')
    expect(submit().attributes('disabled')).toBeUndefined()
  })

  it('saves one comment against every ticked occurrence', async () => {
    const created = comment(77)
    const fetch = api({ 'POST /api/glyphs/AB77/annotations': () => json(created, 201) })
    await render(fetch)
    await boxes()[1].setValue(false)
    await wrapper.get('textarea').setValue('  same ductus  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const post = fetch.mock.calls.find(([, options]) => options?.method === 'POST' && options.headers?.['Content-Type'])
    expect(post[0]).toBe('/api/glyphs/AB77/annotations')
    expect(post[1].headers['X-CSRF-Token']).toBe('csrf')
    expect(JSON.parse(post[1].body)).toEqual({
      body: 'same ductus', targets: [{ tablet: 'HT-1', position: 1 }, { tablet: 'KN-Zb-5', position: 3 }],
    })
    expect(wrapper.get('textarea').element.value).toBe('')
    expect(wrapper.text()).toContain('Saved on 2 occurrences.')
    expect(wrapper.findAll('[data-testid="glyph-comment"]')[0].text()).toContain('note 77')
  })

  it('shows the server message when a comment is refused', async () => {
    const fetch = api({ 'POST /api/glyphs/AB77/annotations': () => json({ detail: 'Not occurrences of AB77: HT-1#2' }, 422) })
    await render(fetch)
    await wrapper.get('textarea').setValue('x')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Not occurrences of AB77: HT-1#2')
    expect(wrapper.get('textarea').element.value).toBe('x')
  })

  it('asks logged-out readers to log in instead of showing the form', async () => {
    await render(api({ '/api/users/me': () => json({}, 401) }), { selection }, false)
    expect(wrapper.find('textarea').exists()).toBe(false)
    const link = wrapper.get('[data-testid="glyph-login-link"]')
    expect(link.attributes('href')).toContain('/login?redirect=')
    expect(cards()).toHaveLength(3)
  })

  it('lists earlier comments and lets only the author delete', async () => {
    const fetch = api({ 'DELETE /api/glyphs/annotations/9': () => ({ ok: true, status: 204 }) })
    await render(fetch)
    const list = wrapper.findAll('[data-testid="glyph-comment"]')
    expect(list).toHaveLength(2)
    expect(list[0].text()).toContain('me · 2026-11-01')
    expect(list[0].text()).toContain('Delete')
    expect(list[1].text()).not.toContain('Delete')
    await list[0].get('button').trigger('click')
    await flushPromises()
    const remove = fetch.mock.calls.find(([, options]) => options?.method === 'DELETE')
    expect(remove[0]).toBe('/api/glyphs/annotations/9')
    expect(remove[1].headers['X-CSRF-Token']).toBe('csrf')
    expect(wrapper.findAll('[data-testid="glyph-comment"]')).toHaveLength(1)
  })

  it('loads more occurrences and ticks the new ones too', async () => {
    const fetch = api({
      'offset=0': () => json(page(ITEMS.slice(0, 2), { total: 3 })),
      'offset=2': () => json(page(ITEMS.slice(2), { total: 3, offset: 2 })),
    })
    await render(fetch, { selection: { sign: 'AB77' } })
    await boxes()[0].setValue(false)
    await wrapper.findAll('button').find((b) => b.text().startsWith('Load more')).trigger('click')
    await flushPromises()
    expect(cards()).toHaveLength(3)
    expect(boxes().map((box) => box.element.checked)).toEqual([false, true, true])
  })

  it('reports load failures with a retry, and unknown signs', async () => {
    let fail = true
    const fetch = api({ '/occurrences': () => (fail ? json({ detail: 'The cached lineara.eu corpus is not installed on this server.' }, 503) : json(page(ITEMS))) })
    await render(fetch, { selection: { sign: 'AB77' } })
    expect(wrapper.get('[role="alert"]').text()).toContain('corpus is not installed')
    fail = false
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(cards()).toHaveLength(3)
    wrapper.unmount()
    await render(api({ '/occurrences': () => json({ detail: 'No corpus tablet has this sign.' }, 404) }), { selection: { sign: 'ZZ99' } })
    expect(wrapper.text()).toContain('No corpus tablet has ZZ99.')
  })

  it('starts over when another glyph is selected', async () => {
    const fetch = api()
    await render(fetch, { selection: { sign: 'AB77' } })
    await wrapper.setProps({ selection: { sign: 'AB01' } })
    await flushPromises()
    expect(fetch.mock.calls.some(([url]) => url.includes('/glyphs/AB01/occurrences'))).toBe(true)
    expect(wrapper.findAll('[data-testid="glyph-tab"]')).toHaveLength(1)
  })

  it('ignores a slow comment list from the tab you left, success or failure', async () => {
    const pending = {}
    const fetch = api({
      '/glyphs/AB77/annotations': () => new Promise((resolve) => { pending.first = resolve }),
      '/glyphs/AB78/annotations': () => json({ items: [comment(50)], next_before: null }),
    })
    await render(fetch)
    await wrapper.findAll('[data-testid="glyph-tab"]')[1].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-comment"]').map((c) => c.text())).toEqual([expect.stringContaining('note 50')])
    pending.first(json({ items: [comment(1)], next_before: null }))
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-comment"]').map((c) => c.text())).toEqual([expect.stringContaining('note 50')])
    expect(wrapper.text()).not.toContain('Comments could not be loaded')
  })

  it('ignores a failing comment list from the tab you left', async () => {
    const pending = {}
    const fetch = api({
      '/glyphs/AB77/annotations': () => new Promise((resolve) => { pending.first = resolve }),
      '/glyphs/AB78/annotations': () => json({ items: [comment(50)], next_before: null }),
    })
    await render(fetch)
    await wrapper.findAll('[data-testid="glyph-tab"]')[1].trigger('click')
    await flushPromises()
    pending.first(json({ detail: 'down' }, 503))
    await flushPromises()
    expect(wrapper.find('[data-testid="glyph-comments"] [role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="glyph-comment"]')).toHaveLength(1)
  })

  it('locks the tabs while a comment is being saved and files it under the sign it was written for', async () => {
    let finish
    const fetch = api({ 'POST /api/glyphs/AB77/annotations': () => new Promise((resolve) => { finish = resolve }) })
    await render(fetch)
    await wrapper.get('textarea').setValue('slow note')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-tab"]').every((tab) => tab.attributes('disabled') !== undefined)).toBe(true)
    finish(json(comment(77), 201))
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-tab"]').every((tab) => tab.attributes('disabled') === undefined)).toBe(true)
    expect(wrapper.findAll('[data-testid="glyph-comment"]')[0].text()).toContain('note 77')
  })

  it('does not show a saved comment on another sign if the selection changed meanwhile', async () => {
    let finish
    const fetch = api({ 'POST /api/glyphs/AB77/annotations': () => new Promise((resolve) => { finish = resolve }) })
    await render(fetch)
    await wrapper.get('textarea').setValue('slow note')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await wrapper.setProps({ selection: { sign: 'AB01' } })
    await flushPromises()
    finish(json(comment(77), 201))
    await flushPromises()
    expect(wrapper.findAll('[data-testid="glyph-comment"]').map((c) => c.text()).join()).not.toContain('note 77')
  })

  it('drops answers that arrive after the selection was cleared', async () => {
    let finish
    const fetch = api({ '/occurrences': () => new Promise((resolve) => { finish = resolve }) })
    await render(fetch, { selection: { sign: 'AB77' } })
    await wrapper.setProps({ selection: null })
    finish(json(page(ITEMS)))
    await flushPromises()
    expect(wrapper.find('[data-testid="glyph-pane"]').exists()).toBe(false)
    expect(cards()).toHaveLength(0)
  })
})
