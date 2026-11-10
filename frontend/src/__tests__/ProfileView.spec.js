import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProfileView from '../views/ProfileView.vue'
import { forgetSession } from '../state/session'

let wrapper
const session = { user: { id: 42, username: 'Developer', email: 'dev@ase3.com' }, csrf_token: 'csrf' }
afterEach(() => { wrapper?.unmount(); forgetSession(); vi.unstubAllGlobals() })
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/profile', component: ProfileView },
    { path: '/login', component: { template: '<p>Login</p>' } },
    { path: '/profile/history', component: { template: '<p>History</p>' } },
  ] })
  await router.push('/profile')
  await router.isReady()
  wrapper = mount(ProfileView, { global: { plugins: [router] } })
  await flushPromises()
  return router
}
it('loads the account from the server and links to History', async () => {
  sessionStorage.setItem('ase.profileUserId', '999')
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => session })
  vi.stubGlobal('fetch', fetch)
  await render()
  expect(fetch).toHaveBeenCalledWith('/api/users/me', { cache: 'no-store' })
  expect(wrapper.text()).toContain('Developer')
  expect(wrapper.get('a[href="/profile/history"]').text()).toContain('History')
})
it('offers login when the server session has expired', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))
  await render()
  expect(wrapper.get('[role="alert"]').text()).toContain('expired')
  expect(wrapper.get('a[href="/login"]').exists()).toBe(true)
})
it('retries a failed account request', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 })
  vi.stubGlobal('fetch', fetch)
  await render()
  expect(wrapper.find('dl').exists()).toBe(false)
  fetch.mockResolvedValue({ ok: true, json: async () => session })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Developer')
})
it('revokes the server session on logout', async () => {
  const fetch = vi.fn().mockImplementation((url) => Promise.resolve(url.endsWith('/logout') ? { ok: true } : { ok: true, json: async () => session }))
  vi.stubGlobal('fetch', fetch)
  const router = await render()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(fetch).toHaveBeenCalledWith('/api/users/logout', expect.objectContaining({ method: 'POST', headers: { 'X-CSRF-Token': 'csrf' } }))
  expect(router.currentRoute.value.path).toBe('/login')
})
