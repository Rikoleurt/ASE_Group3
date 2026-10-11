import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import { clearCurrentUserId, getCurrentUserId } from '../state/currentUser'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  clearCurrentUserId()
  vi.unstubAllGlobals()
})

async function render(path = '/login') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/signup', component: SignupView },
      { path: '/profile', component: { template: '<h1>Profile</h1>' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  return router
}

async function submit() {
  const email = wrapper.find('input[name="email"]')
  if (email.exists()) await email.setValue('dev@ase3.com')
  await wrapper.get('input[name="username"]').setValue('  Developer  ')
  await wrapper.get('input[name="password"]').setValue('dev')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('Authentication forms', () => {
  it('logs in through the API and opens the profile using only the user ID', async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: true, user: { id: 1, email: 'dev@ase3.com' } }),
    })
    vi.stubGlobal('fetch', fetch)
    const router = await render()
    expect(wrapper.find('input[name="email"]').exists()).toBe(false)
    expect(wrapper.get('input[name="username"]').attributes('placeholder')).toBe('Username')
    await submit()
    expect(fetch).toHaveBeenCalledWith('/api/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'Developer', password: 'dev' }),
    })
    expect(router.currentRoute.value.path).toBe('/profile')
    expect(getCurrentUserId()).toBe(1)
    expect(sessionStorage.getItem('ase.profileUserId')).toBe('1')
    expect(wrapper.find('input[name="password"]').exists()).toBe(false)
  })

  it('registers through the API and returns to the existing login page', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 2, email: 'dev@ase3.com', username: 'Developer' }) })
    vi.stubGlobal('fetch', fetch)
    const router = await render('/signup')
    expect(wrapper.get('input[name="username"]').attributes('required')).toBeDefined()
    expect(wrapper.get('input[name="username"]').attributes('maxlength')).toBe('255')
    await submit()
    expect(fetch).toHaveBeenCalledWith('/api/users/register', expect.objectContaining({
      body: JSON.stringify({ username: 'Developer', password: 'dev', email: 'dev@ase3.com' }),
    }))
    expect(wrapper.get('h1').text()).toBe('LOGIN')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it.each([
    ['/login', 401, 'Incorrect username or password.'],
    ['/signup', 409, 'An account with this email already exists'],
    ['/signup', 422, 'Please check your details'],
    ['/login', 503, 'The service is unavailable'],
  ])('handles %s returning %s', async (path, status, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }))
    await render(path)
    await submit()
    expect(wrapper.get('[role="alert"]').text()).toContain(message)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.get('button[type="submit"]').element.disabled).toBe(false)
  })

  it('handles an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await render()
    await submit()
    expect(wrapper.get('[role="alert"]').text()).toContain('Unable to reach the server')
  })

  it('requires a non-blank username for registration', async () => {
    await render('/signup')
    const username = wrapper.get('input[name="username"]')
    expect(username.element.checkValidity()).toBe(false)
    await username.setValue('   ')
    expect(username.element.checkValidity()).toBe(false)
    await username.setValue('Developer')
    expect(username.element.checkValidity()).toBe(true)
  })

  it('prevents duplicate submissions while the request is pending', async () => {
    let resolve
    const fetch = vi.fn().mockReturnValue(new Promise((done) => { resolve = done }))
    vi.stubGlobal('fetch', fetch)
    await render()
    await submit()
    expect(wrapper.get('button[type="submit"]').element.disabled).toBe(true)
    await wrapper.get('form').trigger('submit')
    expect(fetch).toHaveBeenCalledTimes(1)
    resolve({ ok: false, status: 401 })
    await flushPromises()
    expect(wrapper.get('button[type="submit"]').element.disabled).toBe(false)
  })
})
