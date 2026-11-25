import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import BoxSetView from '../views/BoxSetView.vue'
import { NO_MARKS, diff } from '../composables/useBoxSet'
import { forgetSession } from '../state/session'

const box = (id, x, sign, extra = {}) => ({
  id,
  box: { x, y: 0.1, w: 0.1, h: 0.1 },
  sign,
  origin: 'scholar',
  model_sign: sign,
  model_confidence: null,
  candidates: [],
  changed: false,
  marks: { ...NO_MARKS },
  ...extra,
})
const copyWith = (boxes, version = 0) => ({
  id: 5,
  owner: 'dev',
  permission: 'owner',
  everyone: 'none',
  source: { kind: 'tablet', analysis_id: null, tablet: 'HT-13', filename: null },
  start: 'scholar',
  kind: 'copy',
  merged_from: [],
  contributors: [],
  version,
  width: 1000,
  height: 800,
  image_url: '/box-sets/5/image',
  created_at: '2026-11-25T09:00:00Z',
  updated_at: '2026-11-25T09:00:00Z',
  boxes,
  reading: {
    symbol_interpretation: 'ku-ro',
    summary: '',
    lines: [],
    formulas: [],
    signs: boxes.map((b) => ({
      id: b.id,
      sign: b.sign,
      label: b.sign,
      role: 'syllabogram',
      box: b.box,
      confidence: 100,
      candidates: [],
    })),
  },
})
const COPY = copyWith([box(1, 0.1, 'AB81'), box(2, 0.3, 'AB02')])
const SESSION = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf' }
const CATALOGUE = [
  { sign: 'AB81', name: 'AB81 (ku)', glyph: '\u{10642}', reading: 'ku' },
  { sign: 'AB02', name: 'AB02 (ro)', glyph: null, reading: 'ro' },
]

let wrapper

beforeEach(() => {
  Element.prototype.getBoundingClientRect = function () {
    return { left: 0, top: 0, width: 1000, height: 800, right: 1000, bottom: 800, x: 0, y: 0 }
  }
})

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

describe('marks in the saved changes', () => {
  it("sends a box's marks only when they changed", () => {
    const saved = [box(1, 0.1, 'AB81')]
    expect(diff(saved, [box(1, 0.1, 'AB81')])).toEqual([])
    const marked = [
      box(1, 0.1, 'AB81', {
        marks: { ...NO_MARKS, certainty: 'uncertain', alternatives: ['AB02'] },
      }),
    ]
    expect(diff(saved, marked)).toEqual([
      {
        op: 'update',
        box_id: 1,
        marks: { ...NO_MARKS, certainty: 'uncertain', alternatives: ['AB02'] },
      },
    ])
    const drawn = { ...box(-1, 0.5, null), marks: { ...NO_MARKS, word_end: true } }
    expect(diff(saved, [...saved, drawn])).toEqual([
      { op: 'add', box: drawn.box, sign: null, marks: { ...NO_MARKS, word_end: true } },
    ])
    expect(diff(saved, [...saved, box(-2, 0.5, null)])[0]).not.toHaveProperty('marks')
  })
})

describe('Marking boxes in the editor', () => {
  const json = (body, status = 200) =>
    Promise.resolve({ ok: status < 400, status, json: async () => body })

  function serve(saved = COPY) {
    const fetch = vi.fn((url, options = {}) => {
      const key = `${options.method ?? 'GET'} ${url}`
      if (url === '/api/users/me') return json(SESSION)
      if (url === '/api/corrections/catalogue') return json(CATALOGUE)
      if (/\/comments$/.test(url)) return json([])
      if (/\/changes\?/.test(url)) return json({ items: [], next_before: null })
      if (/\/releases$/.test(url)) return json([])
      if (key === 'GET /api/box-sets/5') return json(COPY)
      if (key === 'PATCH /api/box-sets/5') return json(saved)
      return json({ detail: `unexpected ${key}` }, 500)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  async function render() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/box-sets/:id', component: BoxSetView }],
    })
    await router.push('/box-sets/5')
    await router.isReady()
    wrapper = mount(
      { template: '<RouterView />' },
      { global: { plugins: [router] }, attachTo: document.body },
    )
    await flushPromises()
  }

  const sent = (fetch) =>
    JSON.parse(
      fetch.mock.calls.find(([url, o]) => url === '/api/box-sets/5' && o?.method === 'PATCH')[1]
        .body,
    )

  it('marks the selected box uncertain, restored and ending a word, and saves the marks', async () => {
    const fetch = serve()
    await render()
    await wrapper.findAll('[data-testid="box-row"]')[0].trigger('click')
    await wrapper.get('[data-testid="certainty-uncertain"]').setValue(true)
    await wrapper.get('[data-testid="damage-restored"]').setValue(true)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'w' })) // W: word end
    await nextTick()
    expect(wrapper.get('[data-testid="word-end"]').element.checked).toBe(true)
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('1 unsaved change')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(sent(fetch).changes).toEqual([
      {
        op: 'update',
        box_id: 1,
        marks: { ...NO_MARKS, certainty: 'uncertain', damage: 'restored', word_end: true },
      },
    ])
  })

  it('toggles uncertain with U, and undo takes a mark back', async () => {
    serve()
    await render()
    await wrapper.findAll('[data-testid="box-row"]')[1].trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'u' }))
    await nextTick()
    expect(wrapper.get('[data-testid="certainty-uncertain"]').element.checked).toBe(true)
    await wrapper.get('[data-testid="undo"]').trigger('click')
    expect(wrapper.get('[data-testid="certainty-certain"]').element.checked).toBe(true)
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('All changes saved')
  })

  it('sets the reading order by clicking the boxes, line by line', async () => {
    const fetch = serve()
    await render()
    await wrapper.get('[data-testid="mode-order"]').trigger('click')
    expect(wrapper.get('[data-testid="ordering"]').text()).toContain('line 1, sign 1')
    const boxes = wrapper.findAll('[data-testid="edit-box"]')
    for (const target of [boxes[1]]) {
      target.element.dispatchEvent(
        new MouseEvent('pointerdown', { clientX: 350, clientY: 120, button: 0, bubbles: true }),
      )
      window.dispatchEvent(
        new MouseEvent('pointerup', { clientX: 350, clientY: 120, button: 0, bubbles: true }),
      )
      await nextTick()
    }
    await wrapper.get('[data-testid="order-new-line"]').trigger('click')
    boxes[0].element.dispatchEvent(
      new MouseEvent('pointerdown', { clientX: 150, clientY: 120, button: 0, bubbles: true }),
    )
    window.dispatchEvent(
      new MouseEvent('pointerup', { clientX: 150, clientY: 120, button: 0, bubbles: true }),
    )
    await nextTick()
    expect(
      wrapper
        .findAll('[data-testid="glyph-badge"]')
        .map((badge) => badge.text())
        .sort(),
    ).toEqual(['1·1', '2·1'])
    await wrapper.get('[data-testid="order-done"]').trigger('click')
    expect(wrapper.find('[data-testid="ordering"]').exists()).toBe(false)
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    const changes = sent(fetch).changes
    expect(changes.find((c) => c.box_id === 2).marks).toMatchObject({ line: 0, seq: 0 })
    expect(changes.find((c) => c.box_id === 1).marks).toMatchObject({ line: 1, seq: 0 })
  })
})
