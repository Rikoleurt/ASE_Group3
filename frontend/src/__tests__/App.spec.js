import { afterEach, describe, it, expect, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../App.vue'
import LoginView from '../views/LoginView.vue'
import ProfileView from '../views/ProfileView.vue'
import { clearCurrentUserId, getCurrentUserId } from '../state/currentUser'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  clearCurrentUserId()
  vi.unstubAllGlobals()
})

describe('App navigation', () => {
  it('connects login, profile loading and logout without changing navigation', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => url.endsWith('/login')
        ? { authenticated: true, user: { id: 7, email: 'dev@ase3.com' } }
        : url.endsWith('/username') ? { username: 'Developer' } : { email: 'dev@ase3.com' },
    })))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<h1>Home</h1>' } },
        { path: '/tablet-demo', component: { template: '<h1>Demo</h1>' } },
        { path: '/cluster', component: { template: '<h1>Cluster</h1>' } },
        { path: '/signup', component: { template: '<h1>Signup</h1>' } },
        { path: '/login', component: LoginView },
        { path: '/profile', component: ProfileView },
      ],
    })
    await router.push('/login')
    wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.get('header a[href="/login"]').exists()).toBe(true)
    await wrapper.get('input[name="username"]').setValue('dev')
    await wrapper.get('input[name="password"]').setValue('dev')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/profile')
    expect(wrapper.get('h1').text()).toBe('Developer')
    expect(wrapper.text()).toContain('dev@ase3.com')
    expect(wrapper.find('header a[href="/login"]').exists()).toBe(true)
    expect(wrapper.find('header a[href="/signup"]').exists()).toBe(true)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(getCurrentUserId()).toBeNull()
    expect(sessionStorage.getItem('ase.profileUserId')).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(wrapper.get('header a[href="/login"]').exists()).toBe(true)
  })
})
