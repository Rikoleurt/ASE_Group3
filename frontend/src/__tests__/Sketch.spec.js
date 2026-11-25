import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import SketchPad from '../components/signs/SketchPad.vue'
import SignPicker from '../components/signs/SignPicker.vue'
import SignsView from '../views/SignsView.vue'
import SignView from '../views/SignView.vue'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const CATALOGUE = [
  {
    sign: 'AB81',
    name: 'AB81 (ku)',
    glyph: '\u{10642}',
    reading: 'ku',
    preview_url: '/glyphs/AB81/preview.png',
  },
  {
    sign: 'AB53',
    name: 'AB53 (ri)',
    glyph: '\u{10630}',
    reading: 'ri',
    preview_url: '/glyphs/AB53/preview.png',
  },
  {
    sign: 'A301',
    name: 'A301',
    glyph: '\u{10643}',
    reading: null,
    preview_url: '/glyphs/A301/preview.png',
  },
]
const CANDIDATES = {
  items: [
    {
      sign: 'AB81',
      name: 'AB81 (ku)',
      reading: 'ku',
      glyph: '\u{10642}',
      preview_url: '/glyphs/AB81/preview.png',
      score: 45.6,
    },
    {
      sign: 'AB53',
      name: 'AB53 (ri)',
      reading: 'ri',
      glyph: '\u{10630}',
      preview_url: '/glyphs/AB53/preview.png',
      score: 36.5,
    },
  ],
}

let wrapper
let drawn

beforeEach(() => {
  drawn = []
  const ctx = new Proxy(
    {},
    {
      get: (target, name) =>
        name in target ? target[name] : (...args) => drawn.push([name, ...args]),
      set: (target, name, value) => {
        target[name] = value
        return true
      },
    },
  )
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx)
  HTMLCanvasElement.prototype.toBlob = function (resolve) {
    resolve(new Blob(['png'], { type: 'image/png' }))
  }
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})

afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function serve(sketch = () => json(CANDIDATES)) {
  const fetch = vi.fn((url, options = {}) => {
    if (url === '/api/corrections/catalogue') return json(CATALOGUE)
    if (url === '/api/glyphs/sketch' && options.method === 'POST') return sketch(options)
    if (url.startsWith('/api/glyphs/AB81/occurrences')) {
      return json({
        sign: 'AB81',
        total: 106,
        limit: 60,
        offset: 0,
        ranked_by: 'centre',
        credit: null,
        items: [
          {
            tablet: 'HT-13',
            title: 'HT 13',
            position: 4,
            sign: 'AB81',
            crop_url: '/tablets/HT-13/signs/4.png',
            thumbnail_url: '/tablets/HT-13/thumbnail.png?position=4',
            outlier: false,
          },
          {
            tablet: 'HT-9a',
            title: 'HT 9a',
            position: 2,
            sign: 'AB81',
            crop_url: null,
            thumbnail_url: '/tablets/HT-9a/thumbnail.png?position=2',
            outlier: true,
          },
        ],
      })
    }
    return json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

// jsdom has no PointerEvent: send mouse events under the pointer events' names.
function pointer(element, type, x = 0, y = 0) {
  element.dispatchEvent(
    new MouseEvent(type, { clientX: x, clientY: y, bubbles: true, cancelable: true }),
  )
}

async function stroke(
  pad,
  points = [
    [10, 10],
    [60, 80],
    [120, 40],
  ],
) {
  const canvas = pad.get('[data-testid="sketch-canvas"]').element
  pointer(canvas, 'pointerdown', ...points[0])
  for (const [x, y] of points.slice(1)) pointer(canvas, 'pointermove', x, y)
  pointer(canvas, 'pointerup')
  await flushPromises()
}

describe('Sketch pad', () => {
  it('searches 400 ms after a stroke and lists similar signs to pick', async () => {
    const fetch = serve()
    wrapper = mount(SketchPad)
    expect(wrapper.text()).toContain('Draw a sign')
    await stroke(wrapper)
    expect(drawn.some(([name]) => name === 'lineTo')).toBe(true)
    expect(fetch.mock.calls.some(([url]) => url === '/api/glyphs/sketch')).toBe(false) // not yet
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url]) => url === '/api/glyphs/sketch')
    expect(options.body.get('file')).toBeInstanceOf(Blob)
    expect(options.body.get('limit')).toBe('8')
    const results = wrapper.findAll('[data-testid="sketch-result"]')
    expect(results.map((result) => result.text())).toEqual(['AB81ku46% alike', 'AB53ri37% alike'])
    await results[0].trigger('click')
    expect(wrapper.emitted('pick')).toEqual([['AB81']])
  })

  it('undoes and clears strokes, and shows only the latest answer', async () => {
    let answer
    serve(
      () =>
        new Promise((resolve) => {
          answer = resolve
        }),
    )
    wrapper = mount(SketchPad)
    await stroke(wrapper)
    await stroke(wrapper, [
      [5, 5],
      [9, 9],
    ])
    await wrapper.get('[data-testid="sketch-undo"]').trigger('click')
    await vi.advanceTimersByTimeAsync(400)
    await wrapper.get('[data-testid="sketch-clear"]').trigger('click') // cleared before the answer came
    answer(json(CANDIDATES))
    await flushPromises()
    expect(wrapper.find('[data-testid="sketch-results"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Draw a sign')
    expect(wrapper.get('[data-testid="sketch-undo"]').attributes('disabled')).toBeDefined()
  })

  it('explains a refusal from the server', async () => {
    serve(() => json({ detail: 'Draw a sign first.' }, 422))
    wrapper = mount(SketchPad)
    await stroke(wrapper, [[1, 1]])
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Draw a sign first.')
  })

  it('opens from any sign picker and picks the drawn sign', async () => {
    serve()
    wrapper = mount(SignPicker)
    await flushPromises()
    await wrapper.get('[data-testid="sketch-open"]').trigger('click')
    await stroke(wrapper)
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    await wrapper.findAll('[data-testid="sketch-result"]')[1].trigger('click')
    expect(wrapper.emitted('pick')).toEqual([['AB53']])
    expect(wrapper.find('[data-testid="sketch-pad"]').exists()).toBe(false) // closed after picking
  })
})

describe('Find a sign', () => {
  async function render(path) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/signs', component: SignsView },
        { path: '/signs/:sign', component: SignView },
        { path: '/tablets/:slug?', component: { template: '<p>Tablet</p>' } },
      ],
    })
    await router.push(path)
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    return router
  }

  it('lists every sign, searches them, and opens one drawn on the pad', async () => {
    serve()
    const router = await render('/signs')
    expect(wrapper.findAll('[data-testid="sign-card-link"]')).toHaveLength(3)
    await wrapper.get('#signs-search').setValue('ku')
    expect(wrapper.findAll('[data-testid="sign-card-link"]').map((link) => link.text())).toEqual([
      'AB81ku',
    ])
    await stroke(wrapper)
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    await wrapper.findAll('[data-testid="sketch-result"]')[0].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/signs/AB81')
  })

  it("shows a sign's reading and its occurrences, falling back to the tablet thumbnail", async () => {
    serve()
    await render('/signs/AB81')
    expect(wrapper.get('h1').text()).toContain('AB81')
    expect(wrapper.get('[data-testid="sign-name"]').text()).toBe('Reading: ku')
    expect(wrapper.get('[data-testid="occurrence-count"]').text()).toBe(
      '106 occurrences in the corpus',
    )
    const pictures = wrapper.findAll('[data-testid="occurrences"] img')
    expect(pictures.map((img) => img.attributes('src'))).toEqual([
      '/api/tablets/HT-13/signs/4.png',
      '/api/tablets/HT-9a/thumbnail.png?position=2',
    ])
    await pictures[0].trigger('error')
    expect(wrapper.findAll('[data-testid="occurrences"] img')[0].attributes('src')).toBe(
      '/api/tablets/HT-13/thumbnail.png?position=4',
    )
    await wrapper.findAll('[data-testid="occurrences"] img')[1].trigger('error') // HT 9a: no drawing at all
    expect(wrapper.findAll('[data-testid="no-drawing"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('unusual form')
    expect(wrapper.text()).toContain('HT 9a')
  })

  it('says when a sign has no occurrences', async () => {
    serve()
    await render('/signs/A301')
    expect(wrapper.get('[data-testid="occurrence-count"]').text()).toBe(
      'No occurrences in the corpus',
    )
  })
})
