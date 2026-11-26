import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TopBar from '../components/TopBar.vue'
import { forgetSession } from '../state/session'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

async function render(session) {
  vi.stubGlobal('fetch', vi.fn(async () => (session
    ? { ok: true, status: 200, json: async () => session }
    : { ok: false, status: 401, json: async () => ({ detail: 'Please log in.' }) })))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:any(.*)', component: { template: '<p/>' } }] })
  await router.push('/')
  await router.isReady()
  wrapper = mount(TopBar, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return router
}

const visible = (selector) => wrapper.get(selector).isVisible()

describe('Top bar', () => {
  it('lists each main page once, and the HT 13 demos under a menu', async () => {
    await render(null)
    const main = wrapper.findAll('nav[aria-label="Main"] > a').map((a) => a.attributes('href'))
    expect(main).toEqual(['/', '/analysis', '/tablets', '/signs', '/community', '/benchmarks', '/tutorials'])
    expect(wrapper.find('a[href="/tablet-demo"]').isVisible()).toBe(false)
    await wrapper.get('[data-testid="demos-menu"]').trigger('click')
    expect(visible('a[href="/tablet-demo"]')).toBe(true)
    expect(wrapper.get('[data-testid="demos-menu"]').attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('Log in')
    expect(wrapper.find('[data-testid="account-menu"]').exists()).toBe(false)
  })

  it('keeps account pages under the profile button, by role', async () => {
    await render({ user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'c', reviewer: true, admin: false })
    expect(wrapper.get('[data-testid="account-menu"]').text()).toContain('dev')
    expect(visible('a[href="/shared"]')).toBe(false)
    await wrapper.get('[data-testid="account-menu"]').trigger('click')
    expect(visible('a[href="/shared"]')).toBe(true)
    expect(wrapper.find('a[href="/review"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/admin"]').exists()).toBe(false)
    expect(visible('[data-testid="logout"]')).toBe(true)
  })

  it('closes a menu on Escape, a click elsewhere, or a page change', async () => {
    const router = await render(null)
    const menu = () => wrapper.get('[data-testid="demos-menu"]').attributes('aria-expanded')
    await wrapper.get('[data-testid="demos-menu"]').trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(menu()).toBe('false')
    await wrapper.get('[data-testid="demos-menu"]').trigger('click')
    document.body.click()
    await flushPromises()
    expect(menu()).toBe('false')
    await wrapper.get('[data-testid="demos-menu"]').trigger('click')
    await router.push('/tablets')
    await flushPromises()
    expect(menu()).toBe('false')
  })
})
