import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProfileView from '../views/ProfileView.vue'
import { clearCurrentUserId, getCurrentUserId, rememberUserId } from '../state/currentUser'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  clearCurrentUserId()
  vi.unstubAllGlobals()
})

async function render() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/profile', component: ProfileView },
      { path: '/login', component: { template: '<h1>Log in</h1>' } },
    ],
  })
  await router.push('/profile')
  await router.isReady()
  wrapper = mount(ProfileView, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

function profileResponse(url) {
  return Promise.resolve({
    ok: true,
    json: async () => url.endsWith('/username') ? { username: 'Developer' } : { email: 'dev@ase3.com' },
  })
}

describe('Profile', () => {
  it('offers login without querying the API when no account is selected', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    const router = await render()
    expect(wrapper.text()).toContain('Log in to view your profile.')
    expect(fetch).not.toHaveBeenCalled()
    await wrapper.get('a[href="/login"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('loads only username and email using the ID retained across page reloads', async () => {
    sessionStorage.setItem('ase.profileUserId', '42')
    const fetch = vi.fn(profileResponse)
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(fetch).toHaveBeenCalledWith('/api/users/42/username')
    expect(fetch).toHaveBeenCalledWith('/api/users/42/email')
    expect(wrapper.findAll('dt').map((item) => item.text())).toEqual(['Username', 'Email'])
    expect(wrapper.findAll('dd').map((item) => item.text())).toEqual(['Developer', 'dev@ase3.com'])
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('shows a loading state while requests are pending', async () => {
    rememberUserId(1)
    let resolve
    const response = new Promise((done) => { resolve = done })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(response))
    await render()
    expect(wrapper.get('[role="status"]').text()).toContain('Loading')
    resolve({ ok: true, json: async () => ({ username: 'dev', email: 'dev@ase3.com' }) })
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('clears a missing account and offers login again', async () => {
    rememberUserId(42)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('account could not be found')
    expect(wrapper.get('a[href="/login"]').exists()).toBe(true)
    expect(getCurrentUserId()).toBeNull()
  })

  it('allows retrying a server error without showing partial data', async () => {
    rememberUserId(42)
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 })
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('could not be loaded')
    expect(wrapper.find('dl').exists()).toBe(false)
    fetch.mockImplementation(profileResponse)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('dev@ase3.com')
  })

  it('handles an unreachable backend', async () => {
    rememberUserId(42)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('Unable to reach the server')
    expect(wrapper.get('button').text()).toBe('Try again')
  })

  it('ignores an invalid stored ID', async () => {
    sessionStorage.setItem('ase.profileUserId', '../users')
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(fetch).not.toHaveBeenCalled()
    expect(wrapper.get('a[href="/login"]').exists()).toBe(true)
  })
})
