import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import CommunityView from '../views/CommunityView.vue'
import DiscussionView from '../views/DiscussionView.vue'
import ShareAnalysis from '../components/ShareAnalysis.vue'
import { acceptSession, forgetSession } from '../state/session'
import { analysis } from './analysisFixture'

let wrapper
let restoreDialog
const session = { user: { id: 7, username: 'owner', email: 'owner@ase3.com' }, csrf_token: 'csrf' }
const summary = { id: 3, analysis_id: 12, author_id: 7, title: 'HT13 discussion', author_username: 'owner', created_at: '2026-11-10T12:00:00Z' }
const detail = { ...summary, image_url: '/api/community/discussions/3/image', result: analysis }
const comment = { id: 1, discussion_id: 3, author_username: 'reader', created_at: summary.created_at, body: '<script>alert(1)</script>\nA reading?' }
const ok = (data, status = 200) => ({ ok: true, status, json: async () => data })
afterEach(() => {
  wrapper?.unmount()
  restoreDialog?.()
  restoreDialog = undefined
  forgetSession()
  vi.unstubAllGlobals()
})

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
    .mockResolvedValueOnce(ok({ items: [{ ...summary, id: 2, analysis_id: 13 }], next_before: null }))
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

it.each([
  [{ id: 0, sign: null, label: 'object' }, 'symbol-0'],
  [{ id: 1, sign: 'AB81', reading: 'ku', label: 'AB81' }, 'ku'],
])('prefills an editable symbol title and publishes the occurrence ID', async (symbol, expected) => {
  const fetch = vi.fn(async (url) => ok(url === '/api/users/me' ? session : summary))
  vi.stubGlobal('fetch', fetch)
  const router = await render('/analysis', {
    components: { ShareAnalysis }, data: () => ({ symbol }),
    template: '<ShareAnalysis :analysis-id="12" :symbol="symbol" auto-open />',
  })
  expect(wrapper.get('input').element.value).toBe(expected)
  expect(fetch).not.toHaveBeenCalled()
  await wrapper.get('input').setValue('My custom title')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(fetch).toHaveBeenCalledWith('/api/community/discussions', expect.objectContaining({
    body: JSON.stringify({ analysis_id: 12, title: 'My custom title', sign_id: symbol.id }),
  }))
  expect(router.currentRoute.value.path).toBe('/community/3')
})

it('keeps the editable title after a duplicate-name conflict', async () => {
  const fetch = vi.fn(async (url) => url === '/api/users/me' ? ok(session)
    : { ok: false, status: 409, json: async () => ({ detail: 'A discussion with this title already exists. Choose another title.' }) })
  vi.stubGlobal('fetch', fetch)
  const router = await render('/analysis', {
    components: { ShareAnalysis },
    template: '<ShareAnalysis :analysis-id="12" :symbol="{ id: 0, sign: null }" auto-open />',
  })
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('Choose another title')
  expect(wrapper.get('input').element.value).toBe('symbol-0')
  expect(wrapper.get('input').attributes('disabled')).toBeUndefined()
  expect(router.currentRoute.value.path).toBe('/analysis')
})

it('shows the symbol crop, author and tablet tree independently of its custom title', async () => {
  const child = { ...summary, id: 4, title: 'What does this mean?', sign_id: 0, symbol_name: 'ku', tablet_filename: 'HT13.png' }
  const symbolDetail = { ...child, image_url: '/api/community/discussions/4/image',
    symbol: { ...analysis.signs[0], id: 0 }, parent_discussion: summary, symbol_discussions: [child] }
  vi.stubGlobal('fetch', vi.fn(async (url) => ok(url.endsWith('/comments') ? [] : symbolDetail)))
  await render('/community/4')
  expect(wrapper.get('h1').text()).toBe('What does this mean?')
  expect(wrapper.get('[data-testid="symbol-origin"]').text()).toContain('owner created a discussion about symbol ku from tablet HT13.png')
  expect(wrapper.get('img').attributes('src')).toBe(symbolDetail.image_url)
  expect(wrapper.get('nav a[href="/community/3"]').text()).toContain('HT13.png')
  expect(wrapper.get('nav a[aria-current="page"]').text()).toContain('ku')
  expect(wrapper.find('[data-testid="tablet-overlay"]').exists()).toBe(false)
  expect(wrapper.find('[data-testid="verdict"]').exists()).toBe(false)
})

it('shows symbol discussions beneath their tablet and in the community feed', async () => {
  const child = { ...summary, id: 4, sign_id: 1, symbol_name: 'ku', tablet_filename: 'HT13.png' }
  vi.stubGlobal('fetch', vi.fn(async (url) => ok(url.includes('?') ? { items: [child], next_before: null }
    : url.endsWith('/comments') ? [] : { ...detail, tablet_filename: 'HT13.png', parent_discussion: summary, symbol_discussions: [child] })))
  const router = await render()
  const group = wrapper.get('[data-analysis-id="12"]')
  expect(group.get('h2').text()).toBe('HT13.png')
  expect(group.get('ul a[href="/community/4"]').text()).toContain('Model reading: ku')
  await router.push('/community/3'); await flushPromises()
  expect(wrapper.get('nav a[href="/community/4"]').text()).toContain('Symbol ku')
})


it('opens and publishes a symbol discussion directly from the owner’s shared tablet', async () => {
  // jsdom does not implement the browser's modal-dialog API. Keep the real
  // dialog component and form, and simulate only this native DOM operation.
  const original = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')
  const showModal = vi.fn(function () { this.open = true })
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: showModal })
  restoreDialog = () => {
    if (original) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', original)
    else delete HTMLDialogElement.prototype.showModal
  }
  acceptSession(session)
  const child = { ...summary, id: 4, sign_id: analysis.signs[0].id, title: 'A closer look',
    tablet_filename: 'HT13.png', symbol_name: analysis.signs[0].reading }
  const fetch = vi.fn(async (url, options) => {
    if (url === '/api/users/me') return ok(session)
    if (options?.method === 'POST') return ok(child, 201)
    if (url.endsWith('/comments')) return ok([])
    if (url.endsWith('/4')) return ok({ ...child, symbol: analysis.signs[0], image_url: '/api/community/discussions/4/image' })
    return ok({ ...detail, tablet_filename: 'HT13.png' })
  })
  vi.stubGlobal('fetch', fetch)
  const router = await render('/community/3')
  await wrapper.findAll('[data-testid="sign-box"]')[0].trigger('mouseenter')
  await wrapper.get('[data-testid="sign-card"] button').trigger('click')
  const dialog = wrapper.get('dialog')
  expect(showModal).toHaveBeenCalledOnce()
  expect(dialog.element.open).toBe(true)
  expect(dialog.text()).toContain('From tablet HT13.png')
  expect(dialog.get('input').element.value).toBe(analysis.signs[0].reading)
  await dialog.get('input').setValue('A closer look')
  await dialog.get('form').trigger('submit'); await flushPromises()
  expect(fetch).toHaveBeenCalledWith('/api/community/discussions', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ analysis_id: 12, title: 'A closer look', sign_id: analysis.signs[0].id }),
  }))
  expect(router.currentRoute.value.path).toBe('/community/4')
  expect(wrapper.find('dialog').exists()).toBe(false)
  expect(wrapper.get('h1').text()).toBe('A closer look')
})

it.each([null, { ...session, user: { ...session.user, id: 8 } }])(
  'does not offer publication from someone else’s tablet or to an anonymous visitor', async (viewer) => {
    if (viewer) acceptSession(viewer)
    vi.stubGlobal('fetch', vi.fn(async (url) => ok(url.endsWith('/comments') ? [] : detail)))
    await render('/community/3')
    await wrapper.findAll('[data-testid="sign-box"]')[0].trigger('mouseenter')
    expect(wrapper.find('[data-testid="sign-card"] button').exists()).toBe(false)
    expect(wrapper.find('dialog').exists()).toBe(false)
  },
)


it('groups symbol threads beneath their own tablet, even when filenames match', async () => {
  const parent = { ...summary, tablet_filename: 'tablet.png' }
  const secondParent = { ...parent, id: 2, analysis_id: 13, title: 'Another tablet' }
  const child = { ...parent, id: 5, sign_id: 0, title: 'ri', symbol_name: 'ri' }
  const sibling = { ...child, id: 4, sign_id: 1, title: 'ki', symbol_name: 'ki' }
  const otherChild = { ...child, id: 6, analysis_id: 13, title: 'Other reading' }
  vi.stubGlobal('fetch', vi.fn(async () => ok({
    items: [otherChild, child, sibling, parent, secondParent], next_before: null,
  })))
  await render()
  const groups = wrapper.findAll('[data-analysis-id]')
  expect(groups.map((group) => group.attributes('data-analysis-id'))).toEqual(['13', '12'])
  const own = wrapper.get('[data-analysis-id="12"]')
  expect(own.get('h2').text()).toBe(parent.title)
  expect(own.get('ul').findAll('a').map((link) => link.attributes('href'))).toEqual(['/community/5', '/community/4'])
  expect(own.find('a[href="/community/6"]').exists()).toBe(false)
  expect(wrapper.get('[data-analysis-id="13"] ul a').attributes('href')).toBe('/community/6')
})

it('keeps a symbol under a filename heading until its parent arrives on a later page', async () => {
  const parent = { ...summary, tablet_filename: 'HT13.png' }
  const child = { ...parent, id: 4, sign_id: 0, title: 'ri', symbol_name: 'ri' }
  const fetch = vi.fn()
    .mockResolvedValueOnce(ok({ items: [child], next_before: 4 }))
    .mockResolvedValueOnce(ok({ items: [parent], next_before: null }))
  vi.stubGlobal('fetch', fetch)
  await render()
  expect(wrapper.get('[data-analysis-id="12"] h2').text()).toBe('HT13.png')
  expect(wrapper.find('a[href="/community/3"]').exists()).toBe(false)
  expect(wrapper.get('[data-analysis-id="12"] ul a').attributes('href')).toBe('/community/4')
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.findAll('[data-analysis-id]')).toHaveLength(1)
  expect(wrapper.get('[data-analysis-id="12"] h2').text()).toBe(parent.title)
  expect(wrapper.get('a[href="/community/3"]').exists()).toBe(true)
  expect(wrapper.findAll('a[href="/community/4"]')).toHaveLength(1)
  expect(fetch).toHaveBeenLastCalledWith('/api/community/discussions?limit=20&before=4', { cache: 'no-store' })
})
