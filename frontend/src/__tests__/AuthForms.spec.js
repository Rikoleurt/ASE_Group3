import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

async function render(path = '/login') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/signup', component: SignupView },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  return router
}

async function submit() {
  await wrapper.get('input[name="email"]').setValue('dev@ase3.com')
  await wrapper.get('input[name="password"]').setValue('dev')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('Authentication forms', () => {
  it('logs in through the API and clears the password', async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: true, user: { id: 1, email: 'dev@ase3.com' } }),
    })
    vi.stubGlobal('fetch', fetch)
    await render()
    await submit()
    expect(fetch).toHaveBeenCalledWith('/api/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'dev@ase3.com', password: 'dev' }),
    })
    expect(wrapper.get('[role="status"]').text()).toContain('Successfully logged in as dev@ase3.com')
    expect(wrapper.get('input[name="password"]').element.value).toBe('')
  })

  it('navigates to signup using the button below the login form', async () => {
    const router = await render()
    await wrapper.get('a[href="/signup"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/signup')
    expect(wrapper.get('h1').text()).toBe('Create an account')
    expect(wrapper.get('a[href="/login"]').exists()).toBe(true)
  })

  it('registers through the API and offers a return to login', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 2, email: 'dev@ase3.com' }) })
    vi.stubGlobal('fetch', fetch)
    const router = await render('/signup')
    await submit()
    expect(fetch).toHaveBeenCalledWith('/api/users/register', expect.objectContaining({
      body: JSON.stringify({ email: 'dev@ase3.com', password: 'dev' }),
    }))
    expect(wrapper.get('[role="status"]').text()).toContain('Your account has been created')
    await wrapper.get('a[href="/login"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it.each([
    ['/login', 401, 'Incorrect email or password.'],
    ['/signup', 409, 'An account with this email already exists'],
    ['/signup', 422, 'Please check your email'],
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
