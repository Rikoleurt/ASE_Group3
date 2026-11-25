import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationBell from '../components/NotificationBell.vue'
import { forgetSession, loadSession } from '../state/session'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const note = (id, extra = {}) => ({
  id,
  kind: 'share',
  actor: 'anouk',
  message: `note ${id}`,
  link: `/box-sets/${id}`,
  tablet: 'HT-13',
  created_at: '2026-11-25T09:00:00Z',
  read: false,
  ...extra,
})

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

function serve() {
  let unread = 2
  const fetch = vi.fn((url, options = {}) => {
    if (url === '/api/users/me')
      return json({ user: { id: 7, username: 'dev', email: 'd@x.co' }, csrf_token: 'csrf' })
    if (url === '/api/notifications/unread-count') return json({ unread })
    if (url.startsWith('/api/notifications?'))
      return json({ items: [note(3), note(2), note(1, { read: true })], next_before: null, unread })
    if (url === '/api/notifications/read' && options.method === 'POST') {
      const body = JSON.parse(options.body)
      unread = body.ids ? unread - body.ids.length : 0
      return json({ unread })
    }
    return json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function render() {
  await loadSession()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<p />' } },
      { path: '/box-sets/:id', component: { template: '<p>Copy</p>' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  wrapper = mount(NotificationBell, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('Notification bell', () => {
  it('shows the unread count and lists the notifications, unread first marked', async () => {
    serve()
    await render()
    expect(wrapper.get('[data-testid="unread"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="bell"]').attributes('aria-label')).toBe(
      'Notifications: 2 unread',
    )
    await wrapper.get('[data-testid="bell"]').trigger('click')
    await flushPromises()
    const items = wrapper.findAll('[data-testid="notification"]')
    expect(items.map((item) => item.text().slice(0, 6))).toEqual(['note 3', 'note 2', 'note 1'])
    expect(items[0].classes()).toContain('font-semibold')
    expect(items[2].classes()).not.toContain('font-semibold')
  })

  it('opening a notification marks it read and goes to its page', async () => {
    const fetch = serve()
    const router = await render()
    await wrapper.get('[data-testid="bell"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('[data-testid="notification"]')[0].trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/notifications/read')
    expect(JSON.parse(options.body)).toEqual({ ids: [3] })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(router.currentRoute.value.path).toBe('/box-sets/3')
    expect(wrapper.get('[data-testid="unread"]').text()).toBe('1')
    expect(wrapper.find('[data-testid="notifications"]').exists()).toBe(false)
  })

  it('marks everything read', async () => {
    serve()
    await render()
    await wrapper.get('[data-testid="bell"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="read-all"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="unread"]').exists()).toBe(false)
    expect(
      wrapper
        .findAll('[data-testid="notification"]')
        .every((item) => !item.classes().includes('font-semibold')),
    ).toBe(true)
  })
})
