import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import HistoryView from '../views/HistoryView.vue'
import HistoryDetailView from '../views/HistoryDetailView.vue'
import { analysis } from './analysisFixture'
import { loginDestination } from '../state/session'

let wrapper
const metadata = { id: 12, filename: 'tablet.png', format: 'PNG', size_bytes: 2048, created_at: '2026-11-10T12:00:00Z', result_schema_version: 1 }
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals() })
async function render(path = '/profile/history') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/profile/history', component: HistoryView },
    { path: '/profile/history/:id', component: HistoryDetailView },
    { path: '/profile', component: { template: '<p>Profile</p>' } },
    { path: '/analysis', component: { template: '<p>Analyze</p>' } },
    { path: '/login', component: { template: '<p>Login</p>' } },
  ] })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}
it('loads rows and opens the saved result without uploading or running inference', async () => {
  const fetch = vi.fn(async (url) => ({ ok: true, json: async () => url.includes('?')
    ? { items: [metadata], next_cursor: null }
    : { ...metadata, result: analysis } }))
  vi.stubGlobal('fetch', fetch)
  const router = await render()
  const row = wrapper.get('a[href="/profile/history/12"]')
  expect(row.text()).toContain('tablet.png')
  expect(row.text()).toContain('PNG · 2.0 KiB')
  expect(row.classes()).toContain('hover:bg-bar')
  expect(row.classes()).toContain('focus-visible:bg-bar')
  await row.trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/profile/history/12')
  expect(wrapper.text()).toContain(analysis.symbol_interpretation)
  expect(wrapper.text()).toContain('83%')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.get('[data-testid="verdict"]').text()).toContain('off by ½')
  expect(fetch.mock.calls.every(([url]) => url.startsWith('/api/users/me/analyses'))).toBe(true)
})
it('paginates without replacing previous rows', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ items: [metadata], next_cursor: 'next=' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ ...metadata, id: 11, filename: 'older.jpg' }], next_cursor: null }) })
  vi.stubGlobal('fetch', fetch)
  await render()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(fetch.mock.calls[1][0]).toContain('cursor=next%3D')
  expect(wrapper.findAll('li')).toHaveLength(2)
  expect(wrapper.find('button').exists()).toBe(false)
})
it('offers a first upload for an empty history', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], next_cursor: null }) }))
  await render()
  expect(wrapper.text()).toContain('No analyses yet')
  expect(wrapper.get('a[href="/analysis"]').exists()).toBe(true)
})
it('shows loading and allows retrying errors', async () => {
  let resolve
  const fetch = vi.fn().mockReturnValueOnce(new Promise((done) => { resolve = done }))
  vi.stubGlobal('fetch', fetch)
  await render()
  expect(wrapper.get('[role="status"]').text()).toContain('Loading')
  resolve({ ok: false, status: 503 })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('could not be loaded')
  fetch.mockResolvedValue({ ok: true, json: async () => ({ items: [], next_cursor: null }) })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
})
it.each(['/profile/history', '/profile/history/12'])('redirects an expired session from %s', async (path) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))
  const router = await render(path)
  expect(router.currentRoute.value.path).toBe('/login')
  expect(router.currentRoute.value.query.redirect).toBe(path)
})
it('does not expose a missing or foreign result', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
  await render('/profile/history/12')
  expect(wrapper.get('[role="alert"]').text()).toBe('Analysis not found.')
  expect(wrapper.text()).not.toContain('tablet.png')
})
it('restricts post-login destinations to local paths', () => {
  expect(loginDestination({ query: { redirect: '/profile/history/12' } })).toBe('/profile/history/12')
  for (const redirect of ['https://example.com', '//example.com', '/\\example.com']) {
    expect(loginDestination({ query: { redirect } })).toBe('/profile')
  }
})
