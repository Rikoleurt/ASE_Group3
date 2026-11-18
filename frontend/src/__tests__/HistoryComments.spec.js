import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import HistoryPanel from '../components/boxes/HistoryPanel.vue'
import BoxComments from '../components/boxes/BoxComments.vue'
import BoxSetView from '../views/BoxSetView.vue'
import { forgetSession } from '../state/session'

const SESSION = { user: { id: 7, username: 'owner', email: 'o@ase3.com' }, csrf_token: 'csrf' }
const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })
const at = (x, sign, deleted = false) => ({ box: { x, y: 0.1, w: 0.1, h: 0.1 }, sign, deleted })
const change = (id, version, action, before, after, extra = {}) => ({
  id, version, action, box_id: 1, before, after, reverts: null, reverted_by: null,
  author: { id: 7, username: 'owner' }, created_at: '2026-11-18T09:00:00Z', ...extra,
})
const CHANGES = [
  change(4, 3, 'revert', at(0.2, 'AB02'), at(0.2, 'AB81'), { reverts: 2 }),
  change(3, 2, 'add', null, at(0.5, null), { box_id: 2, author: { id: 8, username: 'anouk' } }),
  change(2, 1, 'update', at(0.2, 'AB81'), at(0.2, 'AB02'), { reverted_by: 4 }),
  change(1, 1, 'update', at(0.1, 'AB81'), at(0.2, 'AB81')),
]

let wrapper

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  forgetSession()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubServer(routes) {
  const fetch = vi.fn((url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (url === '/api/users/me') return json(SESSION)
    if (url === '/api/corrections/catalogue') return json([])
    return routes[key] ? routes[key](options) : json({ detail: `unexpected ${key}` }, 500)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('History panel', () => {
  async function render(props = {}) {
    wrapper = mount(HistoryPanel, { props: { setId: 5, version: 3, canRevert: true, ...props } })
    await flushPromises()
  }

  it('groups changes by save and says what each did', async () => {
    stubServer({ 'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES, next_before: null }) })
    await render()
    const saves = wrapper.findAll('[data-testid="history-save"]')
    expect(saves).toHaveLength(3)
    expect(saves[1].text()).toContain('anouk')
    expect(wrapper.findAll('[data-testid="history-change"]').map((c) => c.text())).toEqual([
      'Undid change 2', 'Drew a box', 'Renamed AB81 to AB02', 'Moved AB81',
    ])
    // An undone change is struck through and cannot be undone again.
    expect(wrapper.findAll('[data-testid="history-change"]')[2].classes()).toContain('line-through')
    expect(wrapper.findAll('[data-testid="history-undo"]')).toHaveLength(3)
  })

  it('filters by person and by the selected box', async () => {
    stubServer({ 'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES, next_before: null }) })
    await render({ selectedBoxId: 2 })
    await wrapper.get('[data-testid="history-author"]').setValue('8')
    expect(wrapper.findAll('[data-testid="history-change"]').map((c) => c.text())).toEqual(['Drew a box'])
    await wrapper.get('[data-testid="history-author"]').setValue('')
    await wrapper.get('[data-testid="history-only-box"]').setValue(true)
    expect(wrapper.findAll('[data-testid="history-change"]')).toHaveLength(1)
  })

  it('selects a change and undoes it with the current version', async () => {
    const fetch = stubServer({
      'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES, next_before: null }),
      'POST /api/box-sets/5/changes/1/revert': () => json({ id: 5, version: 4 }),
    })
    await render()
    await wrapper.findAll('[data-testid="history-change"]')[3].trigger('click')
    expect(wrapper.emitted('select')[0][0].id).toBe(1)
    await wrapper.findAll('[data-testid="history-undo"]')[2].trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/box-sets/5/changes/1/revert')
    expect(JSON.parse(options.body)).toEqual({ version: 3 })
    expect(wrapper.emitted('reverted')[0][0].version).toBe(4)
  })

  it('shows why an undo was refused, and blocks undo while edits are unsaved', async () => {
    stubServer({
      'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES, next_before: null }),
      'POST /api/box-sets/5/changes/1/revert': () => json({ detail: 'This box was changed again later. Undo the later change first.' }, 422),
    })
    await render()
    await wrapper.findAll('[data-testid="history-undo"]')[2].trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('changed again later')
    await wrapper.setProps({ unsaved: true })
    expect(wrapper.findAll('[data-testid="history-undo"]').every((b) => b.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.text()).toContain('Save or discard your changes to undo saved ones.')
  })

  it('offers no undo to people who cannot edit, and loads older changes', async () => {
    stubServer({
      'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES.slice(0, 2), next_before: 3 }),
      'GET /api/box-sets/5/changes?limit=50&before=3': () => json({ items: CHANGES.slice(2), next_before: null }),
    })
    await render({ canRevert: false })
    expect(wrapper.find('[data-testid="history-undo"]').exists()).toBe(false)
    await wrapper.findAll('button').find((b) => b.text() === 'Older changes').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="history-change"]')).toHaveLength(4)
  })
})

describe('Comments', () => {
  const COMMENTS = [
    { id: 1, box_id: 1, author: { id: 8, username: 'anouk' }, body: 'This is ro.', created_at: '2026-11-18T09:00:00Z', can_delete: false },
    { id: 2, box_id: null, author: { id: 7, username: 'owner' }, body: 'Worn tablet.', created_at: '2026-11-18T09:01:00Z', can_delete: true },
  ]

  async function render(props = {}) {
    wrapper = mount(BoxComments, { props: { setId: 5, boxId: 1, boxName: 'AB81 (ku)', canComment: true, ...props } })
    await flushPromises()
  }

  it('shows the box thread, or the copy thread when no box is selected', async () => {
    stubServer({ 'GET /api/box-sets/5/comments': () => json(COMMENTS) })
    await render()
    expect(wrapper.get('h2').text()).toBe('Comments on AB81 (ku)')
    expect(wrapper.findAll('[data-testid="comment"]').map((c) => c.text())).toEqual([expect.stringContaining('This is ro.')])
    expect(wrapper.find('[data-testid="comment-delete"]').exists()).toBe(false)
    await wrapper.setProps({ boxId: null })
    expect(wrapper.get('h2').text()).toBe('Comments on this copy')
    expect(wrapper.get('[data-testid="comment"]').text()).toContain('Worn tablet.')
    expect(wrapper.find('[data-testid="comment-delete"]').exists()).toBe(true)
  })

  it('posts a comment on the selected box', async () => {
    const fetch = stubServer({
      'GET /api/box-sets/5/comments': () => json(COMMENTS),
      'POST /api/box-sets/5/comments': (options) => json({ ...COMMENTS[0], id: 3, ...JSON.parse(options.body), author: { id: 7, username: 'owner' }, can_delete: true }, 201),
    })
    await render()
    await wrapper.get('textarea').setValue('  Agreed.  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url, o]) => url === '/api/box-sets/5/comments' && o?.method === 'POST')
    expect(JSON.parse(options.body)).toEqual({ box_id: 1, body: 'Agreed.' })
    expect(wrapper.findAll('[data-testid="comment"]')).toHaveLength(2)
    expect(wrapper.get('textarea').element.value).toBe('')
  })

  it('deletes your own comment after asking', async () => {
    stubServer({
      'GET /api/box-sets/5/comments': () => json(COMMENTS),
      'DELETE /api/box-sets/5/comments/2': () => Promise.resolve({ ok: true, status: 204, json: async () => null }),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await render({ boxId: null })
    await wrapper.get('[data-testid="comment-delete"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="comment"]').exists()).toBe(false)
  })

  it('is read only without comment access, and waits for new boxes to be saved', async () => {
    stubServer({ 'GET /api/box-sets/5/comments': () => json(COMMENTS) })
    await render({ canComment: false })
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.text()).toContain('You can read comments on this copy but not write them.')
    await wrapper.setProps({ boxId: -1 })
    expect(wrapper.text()).toContain('Save the new box before commenting on it.')
  })
})

describe('History in the editor', () => {
  const box = (id, x, sign) => ({ id, box: { x, y: 0.1, w: 0.1, h: 0.1 }, sign, origin: 'model', model_sign: sign, model_confidence: 80, candidates: [], changed: false })
  const copy = (version, boxes) => ({
    id: 5, owner: 'owner', permission: 'owner', everyone: 'none', version, width: 100, height: 100,
    source: { kind: 'analysis', analysis_id: 12, tablet: null, filename: 'tablet.png' }, start: 'model',
    image_url: '/box-sets/5/image', created_at: '2026-11-18T09:00:00Z', updated_at: '2026-11-18T09:00:00Z', boxes,
    reading: { symbol_interpretation: 'ku', summary: '1 sign.', lines: [], formulas: [], signs: [] },
  })

  it('outlines where a moved box was, and takes the copy an undo returns', async () => {
    stubServer({
      'GET /api/box-sets/5': () => json(copy(3, [box(1, 0.2, 'AB81')])),
      'GET /api/box-sets/5/comments': () => json([]),
      'GET /api/box-sets/5/changes?limit=50': () => json({ items: CHANGES, next_before: null }),
      'GET /api/box-sets/5/changes?limit=50&before=0': () => json({ items: [], next_before: null }),
      'POST /api/box-sets/5/changes/1/revert': () => json(copy(4, [box(1, 0.1, 'AB81')])),
    })
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/box-sets/:id', component: BoxSetView }, { path: '/profile/history/:id', component: { template: '<p/>' } }] })
    await router.push('/box-sets/5')
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findAll('[data-testid="history-change"]')[3].trigger('click')
    const ghost = wrapper.get('[data-testid="ghost-box"]')
    expect(ghost.attributes('x')).toBe('10')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('AB81')
    await wrapper.findAll('[data-testid="history-undo"]')[2].trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="ghost-box"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="edit-box"]').attributes('x')).toBe('10')
    expect(wrapper.text()).toContain('The change was undone.')
  })
})
