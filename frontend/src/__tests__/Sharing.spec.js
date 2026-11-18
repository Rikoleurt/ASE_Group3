import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ShareDialog from '../components/boxes/ShareDialog.vue'
import BoxSetView from '../views/BoxSetView.vue'
import SharedView from '../views/SharedView.vue'
import { forgetSession } from '../state/session'

const SESSION = { user: { id: 8, username: 'u8', email: 'u8@ase3.com' }, csrf_token: 'csrf' }
const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })
const box = { id: 1, box: { x: 0.1, y: 0.1, w: 0.1, h: 0.1 }, sign: 'AB81', origin: 'model', model_sign: 'AB81', model_confidence: 80,
  candidates: [{ sign: 'AB02', label: 'AB02 (ro)', roles: [], probability: 20 }], changed: false }
const copy = (permission, extra = {}) => ({
  id: 5, owner: 'anouk', permission, everyone: 'none', source: { kind: 'analysis', analysis_id: 12, tablet: null, filename: 'tablet.png' },
  start: 'model', version: 0, width: 100, height: 100, image_url: '/box-sets/5/image', created_at: '2026-11-18T09:00:00Z',
  updated_at: '2026-11-18T09:00:00Z', boxes: [box],
  reading: { symbol_interpretation: 'ku', summary: '1 sign.', lines: [], formulas: [], signs: [{ id: 1, sign: 'AB81', label: 'AB81 (ku)', role: 'syllabogram', box: box.box, confidence: 80, candidates: [] }] },
  ...extra,
})

let wrapper

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  forgetSession()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function stubServer(routes) {
  const fetch = vi.fn((url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (url === '/api/users/me') return json(SESSION)
    if (url === '/api/corrections/catalogue') return json([])
    return routes[key] ? routes[key](options) : json({ detail: `unexpected ${key}` }, 500)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('Share dialog', () => {
  const SHARING = { everyone: 'none', shares: [{ user: { id: 9, username: 'ahmed' }, permission: 'view' }] }

  async function render() {
    wrapper = mount(ShareDialog, { props: { setId: 5 } })
    await flushPromises()
  }

  it('lists people with access and changes a level', async () => {
    const fetch = stubServer({
      'GET /api/box-sets/5/shares': () => json(SHARING),
      'PUT /api/box-sets/5/shares/9': (options) => json({ ...SHARING, shares: [{ ...SHARING.shares[0], permission: JSON.parse(options.body).permission }] }),
    })
    await render()
    const row = wrapper.get('[data-testid="share-row"]')
    expect(row.text()).toContain('ahmed')
    await row.get('select').setValue('edit')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/box-sets/5/shares/9')
    expect(JSON.parse(options.body)).toEqual({ permission: 'edit' })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('finds people by username and adds them at the chosen level', async () => {
    const fetch = stubServer({
      'GET /api/box-sets/5/shares': () => json(SHARING),
      'GET /api/users/search?q=an': () => json([{ id: 9, username: 'ahmed' }, { id: 10, username: 'anouk' }]),
      'PUT /api/box-sets/5/shares/10': () => json({ ...SHARING, shares: [...SHARING.shares, { user: { id: 10, username: 'anouk' }, permission: 'comment' }] }),
    })
    await render()
    await wrapper.get('#share-search').setValue('a')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(fetch.mock.calls.some(([url]) => url.startsWith('/api/users/search'))).toBe(false) // one letter is not enough
    await wrapper.get('#share-search').setValue('an')
    vi.advanceTimersByTime(300)
    await flushPromises()
    // ahmed already has access, so only anouk is offered.
    const matches = wrapper.findAll('[data-testid="user-matches"] button')
    expect(matches.map((button) => button.text())).toEqual(['anouk'])
    await wrapper.get('[data-testid="new-level"]').setValue('comment')
    await matches[0].trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/box-sets/5/shares/10')
    expect(JSON.parse(options.body)).toEqual({ permission: 'comment' })
    expect(wrapper.findAll('[data-testid="share-row"]')).toHaveLength(2)
  })

  it('removes someone and sets the level for everyone', async () => {
    stubServer({
      'GET /api/box-sets/5/shares': () => json(SHARING),
      'DELETE /api/box-sets/5/shares/9': () => Promise.resolve({ ok: true, status: 204, json: async () => null }),
      'PUT /api/box-sets/5/everyone': () => json({ everyone: 'view', shares: [] }),
    })
    await render()
    await wrapper.get('[aria-label="Remove ahmed"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="share-row"]')).toHaveLength(0)
    await wrapper.get('#share-everyone').setValue('view')
    await flushPromises()
    expect(wrapper.emitted('changed').at(-1)[0].everyone).toBe('view')
    expect(wrapper.findAll('#share-everyone option').map((o) => o.attributes('value'))).not.toContain('manage')
  })

  it('shows why a change was refused', async () => {
    stubServer({
      'GET /api/box-sets/5/shares': () => json(SHARING),
      'PUT /api/box-sets/5/shares/9': () => json({ detail: 'You cannot change your own access.' }, 409),
    })
    await render()
    await wrapper.get('[data-testid="share-row"] select').setValue('manage')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('You cannot change your own access.')
  })
})

async function renderPage(component, path, routePath) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: routePath, component },
    { path: '/box-sets/:id', component: { template: '<p>Editor</p>' } },
    { path: '/profile/history/:id', component: { template: '<p>History</p>' } },
    { path: '/login', component: { template: '<p>Login</p>' } },
  ] })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('A shared copy in the editor', () => {
  it('is read only below edit, and says whose it is', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(copy('comment')) })
    await renderPage(BoxSetView, '/box-sets/5', '/box-sets/:id')
    expect(wrapper.get('[data-testid="copy-owner"]').text()).toContain("anouk's corrected copy, shared with you: you can view and comment")
    expect(wrapper.find('[role="toolbar"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="share"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="read-only"]').exists()).toBe(true)
    await wrapper.get('[data-testid="box-row"]').trigger('click')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('AB81')
    expect(wrapper.find('[data-testid="delete-box"]').exists()).toBe(false)
    expect(wrapper.find('#sign-search').exists()).toBe(false)
    expect(wrapper.find('[data-testid="candidate"]').exists()).toBe(false)
  })

  it('lets editors edit but not share, and managers share', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(copy('edit')) })
    await renderPage(BoxSetView, '/box-sets/5', '/box-sets/:id')
    expect(wrapper.find('[role="toolbar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="share"]').exists()).toBe(false)
    wrapper.unmount()
    stubServer({ 'GET /api/box-sets/5': () => json(copy('manage', { everyone: 'view' })), 'GET /api/box-sets/5/shares': () => json({ everyone: 'view', shares: [] }) })
    await renderPage(BoxSetView, '/box-sets/5', '/box-sets/:id')
    const share = wrapper.get('[data-testid="share"]')
    expect(share.text()).toBe('Share (everyone can view)')
    await share.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="share-dialog"]').exists()).toBe(true)
  })

  it('shows the owner their own copy as theirs', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(copy('owner')) })
    await renderPage(BoxSetView, '/box-sets/5', '/box-sets/:id')
    expect(wrapper.get('[data-testid="copy-owner"]').text()).toContain('your corrected copy')
    expect(wrapper.find('[data-testid="share"]').exists()).toBe(true)
  })
})

describe('Shared with me', () => {
  it('lists copies with their owner and your level', async () => {
    stubServer({ 'GET /api/users/me/shared-copies': () => json([
      { id: 5, owner: 'anouk', kind: 'analysis', title: 'tablet.png', permission: 'edit', shared_with_everyone: false, updated_at: '2026-11-18T09:00:00Z' },
      { id: 6, owner: 'ahmed', kind: 'tablet', title: 'HT 13', permission: 'view', shared_with_everyone: true, updated_at: '2026-11-18T08:00:00Z' },
    ]) })
    await renderPage(SharedView, '/shared', '/shared')
    const rows = wrapper.findAll('[data-testid="shared-copy"]')
    expect(rows.map((row) => row.attributes('href'))).toEqual(['/box-sets/5', '/box-sets/6'])
    expect(rows[0].text()).toContain('Upload · by anouk')
    expect(rows[0].text()).toContain('Can edit')
    expect(rows[1].text()).toContain('Corpus tablet · by ahmed')
    expect(rows[1].text()).toContain('shared with everyone')
  })

  it('says when nothing is shared, and sends logged-out visitors to log in', async () => {
    stubServer({ 'GET /api/users/me/shared-copies': () => json([]) })
    await renderPage(SharedView, '/shared', '/shared')
    expect(wrapper.text()).toContain('Nothing has been shared with you yet.')
    wrapper.unmount()
    stubServer({ 'GET /api/users/me/shared-copies': () => json({ detail: 'Please log in.' }, 401) })
    const router = await renderPage(SharedView, '/shared', '/shared')
    expect(router.currentRoute.value.fullPath).toBe('/login?redirect=/shared')
  })
})
