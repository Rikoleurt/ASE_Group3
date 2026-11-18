import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import CommunityView from '../views/CommunityView.vue'
import DiscussionView from '../views/DiscussionView.vue'
import ShareAnalysis from '../components/ShareAnalysis.vue'
import { acceptSession, forgetSession } from '../state/session'
import { analysis } from './analysisFixture'

let wrapper
const session = { user: { id: 7, username: 'owner', email: 'owner@ase3.com' }, csrf_token: 'csrf' }
const summary = { id: 3, analysis_id: 12, title: 'HT13 discussion', author_username: 'owner', created_at: '2026-11-10T12:00:00Z' }
const detail = { ...summary, image_url: '/api/community/discussions/3/image', result: analysis }
const comment = { id: 1, discussion_id: 3, author_username: 'reader', created_at: summary.created_at, body: '<script>alert(1)</script>\nA reading?' }
const ok = (data, status = 200) => ({ ok: true, status, json: async () => data })
afterEach(() => { wrapper?.unmount(); forgetSession(); vi.unstubAllGlobals() })

async function render(path = '/community', component) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/community', component: CommunityView },
    { path: '/community/:id', component: DiscussionView },
    { path: '/analysis', component: { template: '<p>Analyze</p>' } },
    { path: '/login', component: { template: '<p>Login</p>' } },
  ] })
  await router.push(path)
  await router.isReady()
  wrapper = mount(component || { template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

it('allows an anonymous visitor to open a shared tablet and read its thread', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url) => ok(url.includes('?') ? { items: [summary], next_before: null }
    : url.endsWith('/comments') ? [comment] : detail)))
  const router = await render()
  await wrapper.get('a[href="/community/3"]').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/community/3')
  expect(wrapper.get('h1').text()).toBe('HT13 discussion')
  expect(wrapper.get('img').attributes('src')).toBe(detail.image_url)
  expect(wrapper.text()).toContain(analysis.summary)
  expect(wrapper.text()).toContain('reader')
  expect(wrapper.text()).toContain(comment.body)
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.find('textarea').exists()).toBe(false)
  expect(wrapper.get('a[href="/login?redirect=/community/3"]').text()).toContain('Log in')
})

it('paginates forum rows and retries a failed load', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ detail: 'Try later' }) })
    .mockResolvedValueOnce(ok({ items: [summary], next_before: 3 }))
    .mockResolvedValueOnce(ok({ items: [{ ...summary, id: 2 }], next_before: null }))
  vi.stubGlobal('fetch', fetch)
  await render()
  expect(wrapper.get('[role="alert"]').text()).toBe('Try later')
  await wrapper.get('button').trigger('click'); await flushPromises()
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.findAll('li')).toHaveLength(2)
  expect(fetch).toHaveBeenLastCalledWith('/api/community/discussions?limit=20&before=3', { cache: 'no-store' })
})

it('keeps the draft on failure and posts a comment with session CSRF', async () => {
  acceptSession(session)
  let fail = true
  const fetch = vi.fn(async (url, options) => {
    if (url === '/api/users/me') return ok(session)
    if (options?.method === 'POST') return fail
      ? { ok: false, status: 503, json: async () => ({ detail: 'Please retry' }) }
      : ok({ ...comment, body: 'My reading' }, 201)
    return ok(url.endsWith('/comments') ? [] : detail)
  })
  vi.stubGlobal('fetch', fetch)
  await render('/community/3')
  await wrapper.get('textarea').setValue('My reading')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('textarea').element.value).toBe('My reading')
  expect(wrapper.get('[role="alert"]').text()).toBe('Please retry')
  fail = false
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('textarea').element.value).toBe('')
  expect(wrapper.get('ol[aria-label="Comments"]').text()).toContain('My reading')
  expect(fetch).toHaveBeenCalledWith('/api/community/discussions/3/comments', expect.objectContaining({
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'csrf' },
    body: JSON.stringify({ body: 'My reading' }),
  }))
})

it('requires explicit publication and changes to a discussion link on success', async () => {
  const fetch = vi.fn(async (url) => ok(url === '/api/users/me' ? session : summary))
  vi.stubGlobal('fetch', fetch)
  await render('/analysis', { components: { ShareAnalysis }, template: '<ShareAnalysis :analysis-id="12" filename="tablet.png" />' })
  expect(fetch).not.toHaveBeenCalled()
  await wrapper.get('button').trigger('click')
  expect(wrapper.text()).toContain('will be public')
  await wrapper.get('input').setValue('Reading?')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(fetch).toHaveBeenCalledWith('/api/community/discussions', expect.objectContaining({
    body: JSON.stringify({ analysis_id: 12, title: 'Reading?' }),
  }))
  expect(wrapper.get('a[href="/community/3"]').text()).toContain('View discussion')
})

it('shows an existing discussion without republishing', async () => {
  vi.stubGlobal('fetch', vi.fn())
  await render('/analysis', { components: { ShareAnalysis }, template: '<ShareAnalysis :analysis-id="12" :discussion-id="3" />' })
  expect(wrapper.find('button').exists()).toBe(false)
  expect(wrapper.get('a').attributes('href')).toBe('/community/3')
  expect(fetch).not.toHaveBeenCalled()
})

it('redirects an expired session to login when posting', async () => {
  acceptSession(session)
  vi.stubGlobal('fetch', vi.fn(async (url) => url === '/api/users/me'
    ? { ok: false, status: 401 } : ok(url.endsWith('/comments') ? [] : detail)))
  const router = await render('/community/3')
  await wrapper.get('textarea').setValue('Comment')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(router.currentRoute.value.path).toBe('/login')
  expect(router.currentRoute.value.query.redirect).toBe('/community/3')
})

it('does not leak a previous discussion when navigating to a missing one', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url) => url.includes('/999')
    ? { ok: false, status: 404, json: async () => ({ detail: 'Discussion not found.' }) }
    : ok(url.endsWith('/comments') ? [comment] : detail)))
  const router = await render('/community/3')
  await router.push('/community/999'); await flushPromises()
  expect(wrapper.text()).not.toContain('HT13 discussion')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.get('[role="alert"]').text()).toBe('Discussion not found.')
})
