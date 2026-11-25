import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import ZoomFrame from '../components/boxes/ZoomFrame.vue'
import BoxSetView from '../views/BoxSetView.vue'
import TabletsView from '../views/TabletsView.vue'
import { NO_MARKS } from '../composables/useBoxSet'
import { RECENT_TABLETS } from '../state/preferences'
import { forgetSession } from '../state/session'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const SESSION = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf' }

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

const press = async (key) => {
  window.dispatchEvent(new KeyboardEvent('keydown', { key }))
  await nextTick()
}

describe('Zoom frame', () => {
  it('zooms with the buttons and Ctrl + wheel, and filters the image', async () => {
    wrapper = mount(ZoomFrame, { slots: { default: '<img src="t.png" />' } })
    const content = () => wrapper.get('[data-testid="zoom-content"]')
    expect(content().attributes('style')).toContain('width: 100%')
    expect(wrapper.get('[data-testid="zoom-out"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="zoom-in"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="zoom-level"]').text()).toBe('125%')
    expect(content().attributes('style')).toContain('width: 125%')
    // test-utils cannot set ctrlKey on its stand-in event: send a real WheelEvent.
    wrapper
      .get('[data-testid="zoom-frame"]')
      .element.dispatchEvent(
        new WheelEvent('wheel', {
          deltaY: -500,
          ctrlKey: true,
          clientX: 10,
          clientY: 10,
          bubbles: true,
          cancelable: true,
        }),
      )
    await nextTick()
    expect(Number.parseInt(wrapper.get('[data-testid="zoom-level"]').text())).toBeGreaterThan(125)
    const before = wrapper.get('[data-testid="zoom-level"]').text()
    wrapper
      .get('[data-testid="zoom-frame"]')
      .element.dispatchEvent(new WheelEvent('wheel', { deltaY: -500, bubbles: true }))
    await nextTick()
    expect(wrapper.get('[data-testid="zoom-level"]').text()).toBe(before) // no Ctrl: the page scrolls instead
    await wrapper.get('[data-testid="zoom-fit"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="zoom-level"]').text()).toBe('100%')
    await wrapper.get('[data-testid="invert"]').setValue(true)
    await wrapper.get('[data-testid="contrast"]').setValue(true)
    expect(content().classes()).toEqual(
      expect.arrayContaining(['[&_img]:invert', '[&_img]:contrast-200']),
    )
  })
})

describe('Editor shortcuts', () => {
  const box = (id, x, sign) => ({
    id,
    box: { x, y: 0.1, w: 0.1, h: 0.1 },
    sign,
    origin: 'model',
    model_sign: sign,
    model_confidence: 80,
    changed: false,
    marks: { ...NO_MARKS },
    candidates: [
      { sign: 'AB81', label: 'AB81 (ku)', roles: [], probability: 70 },
      { sign: 'AB02', label: 'AB02 (ro)', roles: [], probability: 20 },
    ],
  })
  const boxes = [box(1, 0.1, 'AB81'), box(2, 0.3, 'AB02')]
  const COPY = {
    id: 5,
    owner: 'dev',
    permission: 'owner',
    everyone: 'none',
    source: { kind: 'tablet', tablet: 'HT-13', analysis_id: null, filename: null },
    start: 'model',
    kind: 'copy',
    merged_from: [],
    contributors: [],
    version: 0,
    width: 1000,
    height: 800,
    image_url: '/box-sets/5/image',
    created_at: '2026-11-25T09:00:00Z',
    updated_at: '2026-11-25T09:00:00Z',
    boxes,
    reading: {
      symbol_interpretation: '',
      summary: '',
      lines: [],
      formulas: [],
      signs: boxes.map((b) => ({ ...b, label: b.sign, role: 'syllabogram', confidence: 80 })),
    },
  }

  async function render() {
    vi.stubGlobal(
      'fetch',
      vi.fn((url) => {
        if (url === '/api/users/me') return json(SESSION)
        if (url === '/api/box-sets/5') return json(COPY)
        if (url === '/api/corrections/catalogue') return json([])
        if (/\/changes\?/.test(url)) return json({ items: [], next_before: null })
        return json([])
      }),
    )
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

  const selected = () => wrapper.find('[data-testid="selected-sign"]')

  it('moves through the boxes with N and P, names one with 2, and switches tools with D and V', async () => {
    await render()
    await press('n')
    expect(selected().text()).toBe('AB81')
    await press('n')
    expect(selected().text()).toBe('AB02')
    await press('n') // wraps around
    expect(selected().text()).toBe('AB81')
    await press('p')
    expect(selected().text()).toBe('AB02')
    await press('1') // the model's first guess
    expect(selected().text()).toBe('AB81')
    expect(wrapper.get('[data-testid="save-state"]').text()).toBe('1 unsaved change')
    await press('d')
    expect(wrapper.get('[data-testid="mode-draw"]').attributes('aria-pressed')).toBe('true')
    await press('v')
    expect(wrapper.get('[data-testid="mode-select"]').attributes('aria-pressed')).toBe('true')
  })

  it('lists the shortcuts with ?, closes them with Escape, and zooms with + and 0', async () => {
    await render()
    const invert = wrapper.get('[data-testid="invert"]').element
    invert.focus() // a focused checkbox does not swallow shortcuts; a text field does
    invert.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', bubbles: true }))
    await nextTick()
    expect(selected().text()).toBe('AB81')
    const search = wrapper.get('#sign-search').element
    search.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', bubbles: true }))
    await nextTick()
    expect(selected().text()).toBe('AB81')
    await press('?')
    expect(wrapper.find('[data-testid="shortcut-help"]').exists()).toBe(true)
    expect(document.body.textContent).toContain('Next / previous box')
    await press('Escape')
    expect(wrapper.find('[data-testid="shortcut-help"]').exists()).toBe(false)
    await press('+')
    expect(wrapper.get('[data-testid="zoom-level"]').text()).toBe('125%')
    await press('0')
    expect(wrapper.get('[data-testid="zoom-level"]').text()).toBe('100%')
  })
})

describe('Bookmarks and recent tablets', () => {
  it('bookmarks the open tablet and lists bookmarks and recent tablets first', async () => {
    let marked = ['KH-5']
    const fetch = vi.fn((url, options = {}) => {
      if (url === '/api/users/me') return json(SESSION)
      if (url.startsWith('/api/tablets?'))
        return json({ items: [{ slug: 'HT-13', tablet: 'HT 13', signs: 27 }], total: 1 })
      if (url === '/api/bookmarks') return json({ tablets: marked })
      if (url === '/api/bookmarks/HT-13') {
        marked =
          options.method === 'PUT'
            ? ['HT-13', ...marked]
            : marked.filter((slug) => slug !== 'HT-13')
        return json({ tablets: marked })
      }
      return json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    RECENT_TABLETS.value = ['HT-9a']
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/tablets/:slug?', component: TabletsView }],
    })
    await router.push('/tablets/HT-13')
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    expect(RECENT_TABLETS.value).toEqual(['HT-13', 'HT-9a']) // opening a tablet remembers it
    expect(wrapper.get('[data-testid="bookmarked-tablets"]').text()).toBe('KH 5')
    expect(wrapper.get('[data-testid="recent-tablets"]').text()).toContain('HT 9a')
    const star = wrapper.get('[data-testid="bookmark"]')
    expect(star.text()).toBe('☆')
    await star.trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/bookmarks/HT-13' && o?.method === 'PUT',
    )
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(wrapper.get('[data-testid="bookmark"]').text()).toBe('★')
    expect(wrapper.get('[data-testid="bookmarked-tablets"]').text()).toContain('HT 13')
    await wrapper.get('[data-testid="bookmarked-tablets"]').findAll('button')[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/tablets/KH-5')
  })
})
