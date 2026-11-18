// State fixes from the #98 review: each test is one sequence of events that used to go wrong.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import BoxEditor from '../components/boxes/BoxEditor.vue'
import BoxComments from '../components/boxes/BoxComments.vue'
import HistoryPanel from '../components/boxes/HistoryPanel.vue'
import ShareDialog from '../components/boxes/ShareDialog.vue'
import SignCorrection from '../components/analysis/SignCorrection.vue'
import BoxSetView from '../views/BoxSetView.vue'
import { acceptSession, forgetSession, sessionFetch } from '../state/session'

const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })
const box = (id, x, sign) => ({ id, box: { x, y: 0.1, w: 0.1, h: 0.1 }, sign, origin: 'model', model_sign: sign, model_confidence: 80, candidates: [], changed: false })
const copy = (version, boxes, extra = {}) => ({
  id: 5, owner: 'owner', permission: 'owner', everyone: 'none', version, width: 100, height: 100,
  source: { kind: 'analysis', analysis_id: 12, tablet: null, filename: 'tablet.png' }, start: 'model',
  image_url: '/box-sets/5/image', created_at: '2026-11-18T09:00:00Z', updated_at: '2026-11-18T09:00:00Z', boxes,
  reading: { symbol_interpretation: 'ku', summary: '1 sign.', lines: [], formulas: [], signs: [] }, ...extra,
})

let wrapper

beforeEach(() => {
  Element.prototype.getBoundingClientRect = function () {
    return { left: 0, top: 0, width: 1000, height: 800, right: 1000, bottom: 800, x: 0, y: 0 }
  }
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  forgetSession()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function pointer(target, type, x, y) {
  target.element.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, cancelable: true }))
  await nextTick()
}

describe('Box editor', () => {
  it('lets read-only viewers select a box by clicking it', async () => {
    wrapper = mount(BoxEditor, { props: { imageUrl: '/t.png', boxes: [box(1, 0.1, 'AB81')], readOnly: true } })
    await pointer(wrapper.get('[data-testid="edit-box"]'), 'pointerdown', 150, 120)
    expect(wrapper.emitted('select')).toEqual([[1]]) // not followed by a deselect from the surface
  })

  it('ignores Delete in the middle of a drag', async () => {
    wrapper = mount(BoxEditor, { props: { imageUrl: '/t.png', boxes: [box(1, 0.1, 'AB81')], selectedId: 1 } })
    await pointer(wrapper.get('[data-testid="edit-box"]'), 'pointerdown', 150, 120)
    await wrapper.get('[data-testid="box-editor"]').trigger('keydown', { key: 'Delete' })
    expect(wrapper.emitted('remove')).toBeUndefined()
    await pointer(wrapper.get('[data-testid="box-editor"]'), 'pointerup', 150, 120)
    await wrapper.get('[data-testid="box-editor"]').trigger('keydown', { key: 'Delete' })
    expect(wrapper.emitted('remove')).toEqual([[1]])
  })

  it('ends a drag where it is when editing pauses', async () => {
    wrapper = mount(BoxEditor, { props: { imageUrl: '/t.png', boxes: [box(1, 0.1, 'AB81')] } })
    await pointer(wrapper.get('[data-testid="edit-box"]'), 'pointerdown', 150, 120)
    await wrapper.setProps({ readOnly: true })
    expect(wrapper.emitted('end')).toHaveLength(1)
    await pointer(wrapper.get('[data-testid="box-editor"]'), 'pointermove', 300, 300)
    expect(wrapper.emitted('place')).toBeUndefined()
  })
})

describe('Session', () => {
  it('refuses a write after a login as someone else in another tab, but not a logout', async () => {
    acceptSession({ user: { id: 1, username: 'alice' }, csrf_token: 'a' })
    const fetch = vi.fn((url) => json(url === '/api/users/me' ? { user: { id: 2, username: 'bob' }, csrf_token: 'b' } : {}))
    vi.stubGlobal('fetch', fetch)
    await expect(sessionFetch('/api/box-sets/5', { method: 'PATCH' })).rejects.toThrow('You logged in as someone else in another tab.')
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/users/me'])
    acceptSession({ user: { id: 1, username: 'alice' }, csrf_token: 'a' })
    await sessionFetch('/api/users/logout', { method: 'POST', anyUser: true })
    expect(fetch.mock.calls.at(-1)[0]).toBe('/api/users/logout')
  })
})

describe('History panel', () => {
  const CHANGE = { id: 1, version: 1, action: 'update', box_id: 1, before: { box: box(1, 0.1).box, sign: 'AB81', deleted: false },
    after: { box: box(1, 0.2).box, sign: 'AB81', deleted: false }, reverts: null, reverted_by: null,
    author: { id: 7, username: 'owner' }, created_at: '2026-11-18T09:00:00Z' }

  it('passes a conflict on to the page instead of showing a dead-end error', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url === '/api/users/me') return json({ user: { id: 7 }, csrf_token: 'c' })
      if (options.method === 'POST') return json({ detail: 'Someone else changed this copy.', current: copy(3, []) }, 409)
      return json({ items: [CHANGE], next_before: null })
    }))
    wrapper = mount(HistoryPanel, { props: { setId: 5, version: 1, canRevert: true } })
    await flushPromises()
    await wrapper.get('[data-testid="history-undo"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('conflict')[0][0].current.version).toBe(3)
    expect(wrapper.emitted('busy')).toEqual([[true], [false]])
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('clears the box filter when the selection goes away', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ items: [CHANGE], next_before: null })))
    wrapper = mount(HistoryPanel, { props: { setId: 5, version: 1, selectedBoxId: 2 } })
    await flushPromises()
    await wrapper.get('[data-testid="history-only-box"]').setValue(true)
    expect(wrapper.findAll('[data-testid="history-change"]')).toHaveLength(0)
    await wrapper.setProps({ selectedBoxId: null })
    expect(wrapper.findAll('[data-testid="history-change"]')).toHaveLength(1)
  })
})

describe('Editor page', () => {
  it('pauses editing while a save is on its way', async () => {
    let finish
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url === '/api/users/me') return json({ user: { id: 7 }, csrf_token: 'c' })
      if (url === '/api/corrections/catalogue' || url.endsWith('/comments')) return json([])
      if (url.includes('/changes?')) return json({ items: [], next_before: null })
      if (options.method === 'PATCH') return new Promise((resolve) => { finish = () => resolve({ ok: true, status: 200, json: async () => copy(1, []) }) })
      return json(copy(0, [box(1, 0.1, 'AB81')]))
    }))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/box-sets/:id', component: BoxSetView }, { path: '/profile/history/:id', component: { template: '<p/>' } }] })
    await router.push('/box-sets/5')
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.get('[data-testid="box-row"]').trigger('click')
    await wrapper.get('[data-testid="delete-box"]').trigger('click')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="mode-draw"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="undo"]').attributes('disabled')).toBeDefined()
    finish()
    await flushPromises()
    expect(wrapper.get('[data-testid="mode-draw"]').attributes('disabled')).toBeUndefined()
  })
})

describe('Share dialog', () => {
  const SHARING = { everyone: 'edit', shares: [
    { user: { id: 7, username: 'me' }, permission: 'manage' },
    { user: { id: 8, username: 'boss' }, permission: 'manage' },
    { user: { id: 9, username: 'viewer' }, permission: 'view' },
  ] }

  async function render(isOwner, routes = {}) {
    acceptSession({ user: { id: 7, username: 'me' }, csrf_token: 'c' })
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url === '/api/users/me') return json({ user: { id: 7, username: 'me' }, csrf_token: 'c' })
      const key = `${options.method ?? 'GET'} ${url}`
      return routes[key] ? routes[key]() : json(SHARING)
    }))
    wrapper = mount(ShareDialog, { props: { setId: 5, isOwner } })
    await flushPromises()
  }
  const rows = () => wrapper.findAll('[data-testid="share-row"]')

  it('leaves out your own row and keeps Manage for the owner to give', async () => {
    await render(false)
    expect(rows().map((row) => row.get('span').text())).toEqual(['boss', 'viewer'])
    expect(rows()[0].get('select').attributes('disabled')).toBeDefined()
    expect(rows()[0].find('button').exists()).toBe(false)
    expect(rows()[1].findAll('option').map((o) => o.attributes('value'))).not.toContain('manage')
    expect(wrapper.get('[data-testid="new-level"]').findAll('option').map((o) => o.attributes('value'))).not.toContain('manage')
  })

  it('says when everyone already has more access than someone\'s own share', async () => {
    await render(true)
    expect(rows()[1].get('[data-testid="everyone-more"]').text()).toBe('Everyone logged in can edit, so viewer can too.')
  })

  it('puts a refused level back', async () => {
    await render(true, { 'PUT /api/box-sets/5/shares/9': () => json({ detail: 'Only the owner can give, change or take away Manage access.' }, 403) })
    await rows()[1].get('select').setValue('edit')
    await flushPromises()
    expect(rows()[1].get('select').element.value).toBe('view')
    expect(wrapper.get('[role="alert"]').text()).toContain('Only the owner can give')
  })
})

describe('Comments', () => {
  it('keeps a draft per thread', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])))
    wrapper = mount(BoxComments, { props: { setId: 5, boxId: 1, canComment: true } })
    await flushPromises()
    await wrapper.get('textarea').setValue('about box 1')
    await wrapper.setProps({ boxId: 2 })
    expect(wrapper.get('textarea').element.value).toBe('')
    await wrapper.setProps({ boxId: 1 })
    expect(wrapper.get('textarea').element.value).toBe('about box 1')
  })
})

describe('Sign correction', () => {
  it('ignores the reply for a sign you moved away from', async () => {
    let finish
    vi.stubGlobal('fetch', vi.fn((url) => url === '/api/users/me'
      ? json({ user: { id: 7 }, csrf_token: 'c' })
      : new Promise((resolve) => { finish = () => resolve({ ok: true, status: 201, json: async () => ({ id: 1, uncertain: true }) }) })))
    const sign = (id) => ({ id, sign: 'AB81', label: 'AB81 (ku)', confidence: 80, box: { x: 0, y: 0, w: 0.1, h: 0.1 }, candidates: [] })
    wrapper = mount(SignCorrection, { props: { sign: sign(1), analysisId: 12, catalogue: [] } })
    const flag = wrapper.findAll('button').find((b) => /uncertain/i.test(b.text()))
    await flag.trigger('click')
    await flushPromises()
    await wrapper.setProps({ sign: sign(2) })
    finish()
    await flushPromises()
    expect(wrapper.find('[data-testid="correction-saved"]').exists()).toBe(false)
  })
})
