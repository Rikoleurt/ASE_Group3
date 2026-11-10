import { afterEach, describe, it, expect, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../App.vue'
import LoginView from '../views/LoginView.vue'
import ProfileView from '../views/ProfileView.vue'
import { getCurrentUserId } from '../state/currentUser'
import { forgetSession } from '../state/session'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

describe('App navigation', () => {
  it('updates navigation after login, restores the session and logs out from the header', async () => {
    const fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ authenticated: true, user: { id: 7, username: 'Developer', email: 'dev@ase3.com' }, csrf_token: 'csrf' }),
    }))
    fetch.mockResolvedValueOnce({ ok: false, status: 401 })
    vi.stubGlobal('fetch', fetch)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<h1>Home</h1>' } },
        { path: '/tablet-demo', component: { template: '<h1>Demo</h1>' } },
        { path: '/analysis', component: { template: '<h1>Analysis</h1>' } },
        { path: '/signup', component: { template: '<h1>Signup</h1>' } },
        { path: '/login', component: LoginView },
        { path: '/profile', component: ProfileView },
        { path: '/profile/history', component: { template: '<p>History</p>' } },
        { path: '/tablet-reading', component: { template: '<p>Reading</p>' } },
      ],
    })
    await router.push('/login')
    wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.get('header a[href="/login"]').exists()).toBe(true)
    expect(wrapper.get('header a[href="/signup"]').exists()).toBe(true)
    expect(wrapper.find('header button').exists()).toBe(false)
    await wrapper.get('input[name="username"]').setValue('dev')
    await wrapper.get('input[name="password"]').setValue('dev')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/profile')
    expect(wrapper.get('h1').text()).toBe('Developer')
    expect(wrapper.text()).toContain('dev@ase3.com')
    expect(wrapper.find('header a[href="/login"]').exists()).toBe(false)
    expect(wrapper.find('header a[href="/signup"]').exists()).toBe(false)
    expect(wrapper.get('header button').text()).toBe('Log out')

    // A fresh app on a public page must recover the server session too.
    wrapper.unmount()
    forgetSession()
    await router.push('/')
    wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.find('header a[href="/login"]').exists()).toBe(false)
    expect(wrapper.get('header button').text()).toBe('Log out')

    fetch.mockResolvedValueOnce({ ok: false, status: 503 })
    await wrapper.get('header button').trigger('click')
    await flushPromises()
    expect(wrapper.get('header [role="alert"]').text()).toContain('Unable to log out')
    expect(wrapper.get('header button').text()).toBe('Log out')
    expect(router.currentRoute.value.path).toBe('/')

    await wrapper.get('header button').trigger('click')
    await flushPromises()
    expect(fetch).toHaveBeenCalledWith('/api/users/logout', expect.objectContaining({
      method: 'POST', headers: { 'X-CSRF-Token': 'csrf' },
    }))
    expect(getCurrentUserId()).toBeNull()
    expect(sessionStorage.getItem('ase.profileUserId')).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(wrapper.get('header a[href="/login"]').exists()).toBe(true)
    expect(wrapper.get('header a[href="/signup"]').exists()).toBe(true)
    expect(wrapper.find('header button').exists()).toBe(false)
  })
})
