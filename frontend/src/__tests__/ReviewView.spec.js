import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ReviewView from '../views/ReviewView.vue'
import TopBar from '../components/TopBar.vue'
import { forgetSession } from '../state/session'

const correction = (id, extra = {}) => ({
  id, analysis_id: 12, sign_id: 3, created_at: '2026-11-18T09:00:00Z', box: { x: 0.1, y: 0.2, w: 0.05, h: 0.06 },
  original_sign: 'AB59', original_label: 'AB59 (ta)', original_confidence: 41.5, model_version: 'linear_a_signs.pt@abc',
  proposed_sign: 'AB81', uncertain: false, note: null, status: 'pending', ...extra,
})
const QUEUE = [
  correction(1),
  correction(2, { proposed_sign: null, uncertain: true, note: 'worn' }),
  correction(3, { analysis_id: 13, sign_id: 1, proposed_sign: 'AB02' }),
]
const CATALOGUE = [{ sign: 'AB59', name: 'AB59', glyph: '\u{1062B}' }, { sign: 'AB81', name: 'AB81', glyph: '\u{10642}' }]
const SESSION = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf', reviewer: true }

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })

function stubServer(routes) {
  const fetch = vi.fn((url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (url === '/api/users/me') return json(SESSION)
    if (url === '/api/corrections/catalogue') return json(CATALOGUE)
    return routes[key] ? routes[key](options) : json({ detail: `unexpected ${key}` }, 500)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function render(component = ReviewView) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', component: { template: '<p>Home</p>' } },
    { path: '/review', component: ReviewView },
    { path: '/login', component: { template: '<p>Login</p>' } },
    { path: '/:other(.*)', component: { template: '<p>Other</p>' } },
  ] })
  await router.push('/review')
  await router.isReady()
  wrapper = mount(component, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

const groups = () => wrapper.findAll('[data-testid="review-group"]')

describe('Review page', () => {
  it('groups corrections by sign and points out disagreement', async () => {
    stubServer({ 'GET /api/corrections?status=pending&limit=200': () => json(QUEUE) })
    await render()

    expect(groups()).toHaveLength(2)
    expect(groups()[0].text()).toContain('AB59 (ta)')
    expect(groups()[0].text()).toContain('Analysis 12 · sign 3')
    expect(groups()[0].findAll('[data-testid="proposal"]').map((item) => item.text())).toEqual(['\u{10642}AB81', 'Flagged as uncertain'])
    expect(groups()[0].text()).toContain('“worn”')
    expect(groups()[0].find('[data-testid="conflict"]').exists()).toBe(true)
    expect(groups()[1].find('[data-testid="conflict"]').exists()).toBe(false)
  })

  it('approves one correction with the CSRF token and takes it off the queue', async () => {
    const fetch = stubServer({
      'GET /api/corrections?status=pending&limit=200': () => json(QUEUE),
      'POST /api/corrections/1/review': () => json(correction(1, { status: 'approved' })),
    })
    await render()
    await groups()[0].findAll('button').find((button) => button.text() === 'Approve').trigger('click')
    await flushPromises()

    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/corrections/1/review')
    expect(JSON.parse(options.body)).toEqual({ decision: 'approved' })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(wrapper.findAll('[data-testid="review-item"]')).toHaveLength(2)
    expect(wrapper.get('[role="status"]').text()).toBe('Approved: AB81 for sign 3 of analysis 12.')
  })

  it('shows why a decision was refused, next to that correction', async () => {
    stubServer({
      'GET /api/corrections?status=pending&limit=200': () => json(QUEUE),
      'POST /api/corrections/3/review': () => json({ detail: 'You cannot review your own correction.' }, 403),
    })
    await render()
    await groups()[1].findAll('button').find((button) => button.text() === 'Reject').trigger('click')
    await flushPromises()

    expect(groups()[1].get('[role="alert"]').text()).toBe('You cannot review your own correction.')
    expect(wrapper.findAll('[data-testid="review-item"]')).toHaveLength(3)
  })

  it('lists decided corrections without buttons', async () => {
    stubServer({
      'GET /api/corrections?status=pending&limit=200': () => json([]),
      'GET /api/corrections?status=approved&limit=200': () => json([correction(1, { status: 'approved' })]),
    })
    await render()
    expect(wrapper.text()).toContain('Nothing here.')
    await wrapper.findAll('button').find((button) => button.text() === 'Approved').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="review-item"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="review-item"] button').exists()).toBe(false)
  })

  it('downloads the approved corrections as JSON', async () => {
    const exported = [{ analysis_id: 12, filename: 'tablet.png', width: 10, height: 10, signs: [] }]
    stubServer({
      'GET /api/corrections?status=pending&limit=200': () => json([]),
      'GET /api/corrections/export': () => json(exported),
    })
    URL.createObjectURL = vi.fn(() => 'blob:export')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await render()
    await wrapper.findAll('button').find((button) => button.text() === 'Export approved (JSON)').trigger('click')
    await flushPromises()

    const blob = URL.createObjectURL.mock.calls[0][0]
    expect(JSON.parse(await blob.text())).toEqual(exported)
    expect(click.mock.contexts[0].download).toBe('sign-corrections.json')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:export')
  })

  it('tells other users the page is for reviewers', async () => {
    stubServer({ 'GET /api/corrections?status=pending&limit=200': () => json({ detail: 'Only reviewers can do this.' }, 403) })
    await render()
    expect(wrapper.get('[role="alert"]').text()).toBe('Only reviewers can see this page.')
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('sends logged-out visitors to the login page', async () => {
    stubServer({ 'GET /api/corrections?status=pending&limit=200': () => json({ detail: 'Please log in.' }, 401) })
    const router = await render()
    expect(router.currentRoute.value.fullPath).toBe('/login?redirect=/review')
  })
})

describe('Top bar', () => {
  it('links to the review page for reviewers only', async () => {
    stubServer({})
    await render(TopBar)
    expect(wrapper.find('a[href="/review"]').exists()).toBe(true)

    wrapper.unmount()
    forgetSession()
    SESSION.reviewer = false
    await render(TopBar)
    expect(wrapper.find('a[href="/review"]').exists()).toBe(false)
    SESSION.reviewer = true
  })
})
