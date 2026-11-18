import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import BoxEditor from '../components/boxes/BoxEditor.vue'
import BoxSetView from '../views/BoxSetView.vue'
import { clampBox, diff } from '../composables/useBoxSet'
import { forgetSession } from '../state/session'

const box = (id, x, sign, extra = {}) => ({
  id, box: { x, y: 0.1, w: 0.1, h: 0.1 }, sign, origin: 'model', model_sign: sign, model_confidence: 80,
  candidates: [{ sign: 'AB81', label: 'AB81 (ku)', roles: ['syllabogram'], probability: 70 }, { sign: 'AB02', label: 'AB02 (ro)', roles: ['syllabogram'], probability: 20 }],
  changed: false, ...extra,
})
const reading = (boxes) => ({
  symbol_interpretation: 'ku-ro', summary: `${boxes.length} signs found.`, lines: [], formulas: [],
  signs: boxes.map((b) => ({ id: b.id, sign: b.sign, label: b.sign, role: 'syllabogram', box: b.box, confidence: 80, candidates: [] })),
})
const copyWith = (boxes, version = 0) => ({
  id: 5, owner: 'dev', permission: 'owner', everyone: 'none', source: { kind: 'analysis', analysis_id: 12, tablet: null, filename: 'tablet.png' }, start: 'model',
  version, width: 1000, height: 800, image_url: '/box-sets/5/image', created_at: '2026-11-18T09:00:00Z',
  updated_at: '2026-11-18T09:00:00Z', boxes, reading: reading(boxes),
})
const COPY = copyWith([box(1, 0.1, 'AB81'), box(2, 0.3, 'AB02')])
const SESSION = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf' }
const CATALOGUE = [{ sign: 'AB81', name: 'AB81 (ku)', glyph: '\u{10642}' }, { sign: 'AB02', name: 'AB02 (ro)', glyph: null }, { sign: 'A707', name: 'J', glyph: null }]

let wrapper

// jsdom has no PointerEvent; a MouseEvent with the pointer type's name carries the coordinates.
async function pointer(target, type, x, y) {
  target.element.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, cancelable: true }))
  await nextTick()
}

beforeEach(() => {
  // jsdom has no layout: the editor is 1000 x 800 px at the page's top-left corner.
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

describe('saving the difference', () => {
  it('turns the working boxes into add, update and delete changes', () => {
    const working = [
      { ...box(1, 0.15, 'AB81') }, // moved
      { ...box(2, 0.3, 'A707') }, // renamed
      { ...box(-1, 0.5, null), origin: 'user' }, // drawn
    ]
    expect(diff([box(1, 0.1, 'AB81'), box(2, 0.3, 'AB02'), box(3, 0.7, 'AB81')], working)).toEqual([
      { op: 'update', box_id: 1, box: { x: 0.15, y: 0.1, w: 0.1, h: 0.1 } },
      { op: 'update', box_id: 2, sign: 'A707' },
      { op: 'delete', box_id: 3 },
      { op: 'add', box: { x: 0.5, y: 0.1, w: 0.1, h: 0.1 }, sign: null },
    ])
    expect(diff(COPY.boxes, COPY.boxes)).toEqual([])
  })

  it('keeps boxes inside the image and not too small', () => {
    expect(clampBox({ x: 0.95, y: -0.1, w: 0.1, h: 0.0001 })).toEqual({ x: 0.9, y: 0, w: 0.1, h: 0.002 })
  })
})

describe('Box editor', () => {
  function render(props = {}) {
    wrapper = mount(BoxEditor, { props: { imageUrl: '/t.png', boxes: COPY.boxes, ...props } })
    return wrapper
  }

  it('selects and drags a box', async () => {
    render()
    const first = wrapper.findAll('[data-testid="edit-box"]')[0]
    await pointer(first, 'pointerdown', 150, 120)
    expect(wrapper.emitted('select')[0]).toEqual([1])
    expect(wrapper.emitted('begin')).toHaveLength(1)
    await pointer(wrapper.get('[data-testid="box-editor"]'), 'pointermove', 250, 200)
    const [id, moved] = wrapper.emitted('place')[0]
    expect(id).toBe(1)
    expect(moved.x).toBeCloseTo(0.2)
    expect(moved.y).toBeCloseTo(0.2)
    await pointer(wrapper.get('[data-testid="box-editor"]'), 'pointerup', 250, 200)
    expect(wrapper.emitted('end')).toHaveLength(1)
  })

  it('resizes from a corner, keeping the opposite corner still', async () => {
    render({ selectedId: 1 })
    await pointer(wrapper.get('[data-testid="handle-se"]'), 'pointerdown', 200, 160)
    await pointer(wrapper.get('[data-testid="box-editor"]'), 'pointermove', 300, 240)
    const [, resized] = wrapper.emitted('place')[0]
    expect(resized.x).toBeCloseTo(0.1)
    expect(resized.y).toBeCloseTo(0.1)
    expect(resized.w).toBeCloseTo(0.2)
    expect(resized.h).toBeCloseTo(0.2)
  })

  it('draws a new box in draw mode, and ignores a click without a drag', async () => {
    render({ mode: 'draw' })
    const surface = wrapper.get('[data-testid="box-editor"]')
    await pointer(surface, 'pointerdown', 600, 400)
    await pointer(surface, 'pointermove', 500, 320)
    expect(wrapper.find('[data-testid="draft-box"]').exists()).toBe(true)
    await pointer(surface, 'pointerup', 500, 320)
    const [drawn] = wrapper.emitted('draw')[0]
    expect(drawn.x).toBeCloseTo(0.5)
    expect(drawn.y).toBeCloseTo(0.4)
    expect(drawn.w).toBeCloseTo(0.1)
    expect(drawn.h).toBeCloseTo(0.1)
    await pointer(surface, 'pointerdown', 100, 100)
    await pointer(surface, 'pointerup', 100, 100)
    expect(wrapper.emitted('draw')).toHaveLength(1)
  })

  it('moves, resizes and deletes the selected box from the keyboard', async () => {
    render({ selectedId: 2 })
    const surface = wrapper.get('[data-testid="box-editor"]')
    await surface.trigger('keydown', { key: 'ArrowRight' })
    await surface.trigger('keydown', { key: 'ArrowDown', shiftKey: true })
    const [[, right], [, taller]] = wrapper.emitted('nudge')
    expect(right.x).toBeCloseTo(0.302)
    expect(taller.h).toBeCloseTo(0.102)
    await surface.trigger('keydown', { key: 'Delete' })
    expect(wrapper.emitted('remove')[0]).toEqual([2])
    await surface.trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('select').at(-1)).toEqual([null])
  })

  it('only selects when read only', async () => {
    render({ readOnly: true, selectedId: 1 })
    await pointer(wrapper.findAll('[data-testid="edit-box"]')[1], 'pointerdown', 350, 120)
    expect(wrapper.emitted('select')[0]).toEqual([2])
    expect(wrapper.emitted('begin')).toBeUndefined()
    expect(wrapper.find('[data-testid="handle-se"]').exists()).toBe(false)
    await wrapper.get('[data-testid="box-editor"]').trigger('keydown', { key: 'Delete' })
    expect(wrapper.emitted('remove')).toBeUndefined()
  })

  it('marks changed and unnamed boxes', () => {
    render({ boxes: [box(1, 0.1, 'AB81', { changed: true }), box(-1, 0.3, null)] })
    const [changed, drawn] = wrapper.findAll('[data-testid="edit-box"]')
    expect(changed.classes()).toContain('changed')
    expect(drawn.classes()).toEqual(expect.arrayContaining(['changed', 'unnamed']))
  })
})

describe('Correct the boxes page', () => {
  const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })

  function stubServer(routes) {
    const fetch = vi.fn((url, options = {}) => {
      const key = `${options.method ?? 'GET'} ${url}`
      if (url === '/api/users/me') return json(SESSION)
      if (url === '/api/corrections/catalogue') return json(CATALOGUE)
      return routes[key] ? routes[key](options) : json({ detail: `unexpected ${key}` }, 500)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  async function render() {
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/box-sets/:id', component: BoxSetView },
      { path: '/profile/history/:id', component: { template: '<p>History</p>' } },
      { path: '/login', component: { template: '<p>Login</p>' } },
    ] })
    await router.push('/box-sets/5')
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    return router
  }

  const rows = () => wrapper.findAll('[data-testid="box-row"]')

  it('renames a box from the model\'s guesses and saves the change', async () => {
    const renamed = copyWith([box(1, 0.1, 'AB02', { changed: true }), box(2, 0.3, 'AB02')], 1)
    const fetch = stubServer({ 'GET /api/box-sets/5': () => json(COPY), 'PATCH /api/box-sets/5': () => json(renamed) })
    await render()
    expect(wrapper.get('img').attributes('src')).toBe('/api/box-sets/5/image')
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('All changes saved')
    await rows()[0].trigger('click')
    await wrapper.findAll('[data-testid="candidate"]')[1].trigger('click')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('AB02 (ro)')
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('1 unsaved change')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url, o]) => url === '/api/box-sets/5' && o?.method === 'PATCH')
    expect(JSON.parse(options.body)).toEqual({ version: 0, changes: [{ op: 'update', box_id: 1, sign: 'AB02' }] })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('All changes saved')
    expect(wrapper.text()).toContain('Saved 1 change.')
  })

  it('finds a sign in the catalogue, clears it, deletes a box, and undoes', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(COPY) })
    await render()
    await rows()[1].trigger('click')
    await wrapper.get('#sign-search').setValue('j')
    await wrapper.get('[data-testid="sign-matches"] button').trigger('click')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('J')
    await wrapper.get('[data-testid="clear-sign"]').trigger('click')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('Unnamed')
    await wrapper.get('[data-testid="delete-box"]').trigger('click')
    expect(rows()).toHaveLength(1)
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('1 unsaved change')
    await wrapper.get('[data-testid="undo"]').trigger('click')
    await wrapper.get('[data-testid="undo"]').trigger('click')
    await wrapper.get('[data-testid="undo"]').trigger('click')
    expect(rows()).toHaveLength(2)
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('All changes saved')
  })

  it('draws a box and selects it for naming', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(COPY) })
    await render()
    await wrapper.get('[data-testid="mode-draw"]').trigger('click')
    const surface = wrapper.get('[data-testid="box-editor"]')
    await pointer(surface, 'pointerdown', 600, 400)
    await pointer(surface, 'pointermove', 700, 500)
    await pointer(surface, 'pointerup', 700, 500)
    expect(rows()).toHaveLength(3)
    expect(rows()[2].text()).toContain('new')
    expect(wrapper.get('[data-testid="selected-sign"]').text()).toBe('Unnamed')
    expect(wrapper.get('[data-testid="mode-select"]').attributes('aria-pressed')).toBe('true')
  })

  it('offers the newer copy when someone else saved first', async () => {
    const newer = copyWith([box(1, 0.1, 'AB81')], 3)
    stubServer({
      'GET /api/box-sets/5': () => json(COPY),
      'PATCH /api/box-sets/5': () => json({ detail: 'Someone else changed this copy since you opened it. Reload to see their changes.', current: newer }, 409),
    })
    await render()
    await rows()[0].trigger('click')
    await wrapper.get('[data-testid="delete-box"]').trigger('click')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    const conflict = wrapper.get('[data-testid="conflict"]')
    expect(conflict.text()).toContain('Someone else changed this copy')
    await conflict.get('button').trigger('click')
    expect(rows()).toHaveLength(1)
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('All changes saved')
  })

  it('shows why a save was refused', async () => {
    stubServer({
      'GET /api/box-sets/5': () => json(COPY),
      'PATCH /api/box-sets/5': () => json({ detail: 'NOPE is not a sign in the catalogue.' }, 422),
    })
    await render()
    await rows()[0].trigger('click')
    await wrapper.get('[data-testid="delete-box"]').trigger('click')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('NOPE is not a sign in the catalogue.')
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('1 unsaved change')
  })

  it('asks before leaving with unsaved changes', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json(COPY) })
    const router = await render()
    await rows()[0].trigger('click')
    await wrapper.get('[data-testid="delete-box"]').trigger('click')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    await router.push('/profile/history/12')
    expect(confirm).toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/box-sets/5')
  })

  it('says when the copy does not exist', async () => {
    stubServer({ 'GET /api/box-sets/5': () => json({ detail: 'Corrected copy not found.' }, 404) })
    await render()
    expect(wrapper.get('[role="alert"]').text()).toBe('This corrected copy was not found.')
  })
})
