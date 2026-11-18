import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import AdminView from '../views/AdminView.vue'
import TopBar from '../components/TopBar.vue'
import { forgetSession } from '../state/session'

const user = (id, username, extra = {}) => ({
  id, username, email: `${username}@ase3.com`, admin: false, reviewer: false, reviewer_from_env: false, ...extra,
})
const USERS = [user(1, 'dev', { admin: true, reviewer: true }), user(2, 'anouk'), user(3, 'legacy', { reviewer_from_env: true })]
const ADMIN = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf', reviewer: true, admin: true }

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })

function stubServer(routes, session = ADMIN) {
  const fetch = vi.fn((url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (url === '/api/users/me') return json(session)
    return routes[key] ? routes[key](options) : json({ detail: `unexpected ${key}` }, 500)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function render(component = AdminView) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', component: { template: '<p>Home</p>' } },
    { path: '/admin', component: AdminView },
    { path: '/login', component: { template: '<p>Login</p>' } },
    { path: '/:other(.*)', component: { template: '<p>Other</p>' } },
  ] })
  await router.push('/admin')
  await router.isReady()
  wrapper = mount(component, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

const LIST = '/api/admin/users?q=&limit=50&offset=0'
const rows = () => wrapper.findAll('[data-testid="admin-user"]')
const box = (row, role) => rows()[row].get(`[data-testid="role-${role}"]`)

describe('Admin page', () => {
  it('lists users with their roles', async () => {
    stubServer({ [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }) })
    await render()
    expect(rows().map((row) => row.get('th span').text())).toEqual(['dev', 'anouk', 'legacy'])
    expect(rows()[0].text()).toContain('(you)')
    expect(rows()[1].text()).not.toContain('(you)')
    expect(rows()[1].text()).toContain('anouk@ase3.com')
    expect(rows().map((_, i) => [box(i, 'admin').element.checked, box(i, 'reviewer').element.checked]))
      .toEqual([[true, true], [false, false], [false, true]])
  })

  it('locks your own admin role and reviewers named in SIGN_REVIEWERS, and says why', async () => {
    stubServer({ [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }) })
    await render()
    expect(box(0, 'admin').attributes('disabled')).toBeDefined()
    expect(box(0, 'admin').attributes('title')).toBe('You cannot remove your own admin role.')
    expect(box(0, 'reviewer').attributes('disabled')).toBeUndefined()
    expect(box(2, 'reviewer').attributes('disabled')).toBeDefined()
    expect(box(2, 'reviewer').attributes('title')).toContain('SIGN_REVIEWERS')
  })

  it('grants a role and says so', async () => {
    const fetch = stubServer({
      [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }),
      'PATCH /api/admin/users/2': () => json({ ...USERS[1], reviewer: true }),
    })
    await render()
    await box(1, 'reviewer').setValue(true)
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/admin/users/2')
    expect(JSON.parse(options.body)).toEqual({ reviewer: true })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(box(1, 'reviewer').element.checked).toBe(true)
    expect(wrapper.get('[role="status"]').text()).toBe('anouk is now a reviewer.')
  })

  it('shows the server reason and resets the box when a change is refused', async () => {
    stubServer({
      [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }),
      'PATCH /api/admin/users/2': () => json({ detail: 'User not found.' }, 404),
    })
    await render()
    await box(1, 'admin').setValue(true)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('User not found.')
    expect(box(1, 'admin').element.checked).toBe(false)
  })

  it('searches and pages through the results', async () => {
    const many = Array.from({ length: 50 }, (_, i) => user(i + 10, `user${i}`))
    const fetch = stubServer({
      [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }),
      'GET /api/admin/users?q=user&limit=50&offset=0': () => json({ items: many, total: 51 }),
      'GET /api/admin/users?q=user&limit=50&offset=50': () => json({ items: [user(99, 'user50')], total: 51 }),
    })
    await render()
    await wrapper.get('#user-search').setValue('  user ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(rows()).toHaveLength(50)
    expect(wrapper.text()).toContain('1–50 of 51')
    await wrapper.findAll('nav[aria-label="Pages"] button')[1].trigger('click')
    await flushPromises()
    expect(rows().map((row) => row.get('th span').text())).toEqual(['user50'])
    expect(wrapper.text()).toContain('51–51 of 51')
    expect(fetch.mock.calls.some(([url]) => url === '/api/admin/users?q=user&limit=50&offset=50')).toBe(true)
  })

  it('tells non-admins the page is not for them', async () => {
    stubServer({ [`GET ${LIST}`]: () => json({ detail: 'Only admins can do this.' }, 403) })
    await render()
    expect(wrapper.get('[role="alert"]').text()).toBe('Only admins can see this page.')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('sends logged-out visitors to the login page', async () => {
    stubServer({ [`GET ${LIST}`]: () => json({ detail: 'Please log in.' }, 401) })
    const router = await render()
    expect(router.currentRoute.value.fullPath).toBe('/login?redirect=/admin')
  })
})

describe('Training export', () => {
  it('downloads the corrections as JSON and as a YOLO zip', async () => {
    const fetch = stubServer({
      [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }),
      'GET /api/admin/export/corrections': () => json({ copies: [{ copy_id: 1 }], label_corrections: [] }),
      'GET /api/admin/export/corrections.zip': () => Promise.resolve({ ok: true, status: 200, blob: async () => new Blob(['zip']) }),
    })
    URL.createObjectURL = vi.fn(() => 'blob:export')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await render()
    await wrapper.get('[data-testid="export-json"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="export-zip"]').trigger('click')
    await flushPromises()
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(expect.arrayContaining(['/api/admin/export/corrections', '/api/admin/export/corrections.zip']))
    expect(click).toHaveBeenCalledTimes(2)
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    click.mockRestore()
  })

  it('shows why an export failed', async () => {
    stubServer({
      [`GET ${LIST}`]: () => json({ items: USERS, total: 3 }),
      'GET /api/admin/export/corrections': () => json({ detail: 'Correction storage is unavailable.' }, 503),
    })
    await render()
    await wrapper.get('[data-testid="export-json"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Correction storage is unavailable.')
  })
})

describe('Top bar', () => {
  it('links to the admin page for admins only', async () => {
    stubServer({}, ADMIN)
    await render(TopBar)
    expect(wrapper.find('a[href="/admin"]').exists()).toBe(true)
    wrapper.unmount()
    forgetSession()
    stubServer({}, { ...ADMIN, admin: false })
    await render(TopBar)
    expect(wrapper.find('a[href="/admin"]').exists()).toBe(false)
  })
})
