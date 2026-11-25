import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AnalysisView from '../views/AnalysisView.vue'
import { analysis } from './analysisFixture.js'

let wrapper

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

// Clicking a box also opens the other-tablets pane; it gets an empty page unless a test says otherwise.
const NO_OCCURRENCES = { ok: true, status: 200, json: async () => ({ sign: 'AB131a', total: 0, limit: 30, offset: 0, ranked_by: 'corpus', items: [], credit: null }) }

async function upload(response, options = {}) {
  const fetch = vi.fn((url) => Promise.resolve(url === '/api/users/me'
    ? { ok: true, json: async () => ({ user: { id: 1 }, csrf_token: 'csrf' }) }
    : url.startsWith('/api/glyphs/') ? NO_OCCURRENCES : response))
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(AnalysisView, options)
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [new File(['png'], 'tablet.png', { type: 'image/png' })] })
  await input.trigger('change')
  await flushPromises()
  return fetch
}

describe('Analysis page', () => {
  it('posts the upload and keeps its own result card', async () => {
    const fetch = await upload({ ok: true, json: async () => analysis })

    expect(fetch).toHaveBeenCalledWith('/api/analysis', expect.objectContaining({ method: 'POST' }))
    const card = wrapper.findAll('h2').find((title) => title.text() === 'Analysis').element.parentElement
    expect(card.textContent).toContain(analysis.summary)
    expect(card.textContent).toContain('Transliterationta J / VIN J / ku-ro J')
    expect(card.textContent).toContain('Confidence83%')
    expect(card.textContent).toContain('Processing time2.7 s')
  })

  it('draws the boxes on the uploaded image and adds the fraction check below', async () => {
    await upload({ ok: true, json: async () => analysis })

    expect(wrapper.get('img').attributes('src')).toBe('blob:preview')
    expect(wrapper.findAll('[data-testid="sign-box"]')).toHaveLength(analysis.signs.length)
    expect(wrapper.find('[data-testid="formula-box"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="verdict"]').text()).toBe('The fractions do not balance: off by ½')
  })

  it('goes back to the upload box from the result', async () => {
    await upload({ ok: true, json: async () => analysis })
    await wrapper.findAll('button').find((button) => button.text() === 'Analyze another image').trigger('click')

    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="formula"]').exists()).toBe(false)
  })

  it('opens the correction form for a clicked sign, with the sign catalogue', async () => {
    const fetch = await upload({ ok: true, json: async () => ({ ...analysis, analysis_id: 12, trained: true }) })
    fetch.mockImplementation((url) => Promise.resolve(url === '/api/corrections/catalogue'
      ? { ok: true, json: async () => [{ sign: 'AB81', name: 'AB81 (ku)', glyph: null, reading: 'ku', preview_url: '/glyphs/AB81/preview.png' }] }
      : url.startsWith('/api/glyphs/') ? NO_OCCURRENCES
        : { ok: true, json: async () => ({ user: { id: 1 }, csrf_token: 'csrf' }) }))
    expect(wrapper.find('[data-testid="sign-correction"]').exists()).toBe(false)

    await wrapper.findAll('[data-testid="sign-box"]')[2].trigger('click')
    await flushPromises()

    expect(fetch).toHaveBeenCalledWith('/api/corrections/catalogue')
    const form = wrapper.get('[data-testid="sign-correction"]')
    expect(form.get('[data-testid="correction-original"]').text()).toContain('VIN')
    await form.get('#proposed-sign').setValue('ku')
    expect(form.findAll('[data-testid="correction-suggestions"] button').map((button) => button.text())).toEqual(['AB81 ku'])
    await form.findAll('button').find((button) => button.text() === 'Close').trigger('click')
    expect(wrapper.find('[data-testid="sign-correction"]').exists()).toBe(false)
  })

  it('offers no correction for the generic fallback model', async () => {
    await upload({ ok: true, json: async () => ({ ...analysis, analysis_id: 12, trained: false }) })
    await wrapper.findAll('[data-testid="sign-box"]')[2].trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="sign-correction"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Click its box to correct it')
  })

  it('shows the server message when the reader is unavailable', async () => {
    await upload({ ok: false, status: 503, json: async () => ({ detail: 'The sign reader is unavailable.' }) })

    expect(wrapper.get('[role="alert"]').text()).toBe('The sign reader is unavailable.')
  })

  it('opens the other-tablets pane when a sign box is clicked', async () => {
    const withCrop = { ...analysis, signs: analysis.signs.map((sign) => ({ ...sign, crop: 'data:image/png;base64,iVBORw0KGgo=' })) }
    const calls = []
    const fetch = vi.fn((url, options) => {
      calls.push([url, options])
      if (url === '/api/users/me') return Promise.resolve({ ok: true, json: async () => ({ user: { id: 1 }, csrf_token: 'csrf' }) })
      if (url.includes('/occurrences/search')) return Promise.resolve({ ok: true, json: async () => ({ sign: 'AB59', total: 0, limit: 30, offset: 0, ranked_by: 'glyph', items: [], credit: null }) })
      if (url.includes('/annotations')) return Promise.resolve({ ok: true, json: async () => ({ items: [], next_before: null }) })
      return Promise.resolve({ ok: true, json: async () => withCrop })
    })
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(AnalysisView)
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['png'], 'tablet.png', { type: 'image/png' })] })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.find('[data-testid="glyph-pane"]').exists()).toBe(false)
    await wrapper.findAll('[data-testid="sign-box"]')[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="glyph-pane"]').text()).toContain('Other tablets with this sign')
    expect(calls.some(([url]) => url === '/api/glyphs/AB59/occurrences/search')).toBe(true)
    expect(wrapper.findAll('[data-testid="sign-box"]')[0].attributes('aria-pressed')).toBe('true')
  })
})


it('opens a symbol discussion from an uploaded detection with its analysis and occurrence', async () => {
  await upload({ ok: true, json: async () => ({ ...analysis, analysis_id: 12 }) }, {
    global: { stubs: { SymbolDiscussionDialog: {
      props: ['analysisId', 'symbol', 'filename'],
      template: '<div data-testid="symbol-dialog">{{ analysisId }} / {{ symbol.id }} / {{ filename }}</div>',
    } } },
  })
  await wrapper.findAll('[data-testid="sign-box"]')[0].trigger('mouseenter')
  await wrapper.get('[data-testid="sign-card"] button').trigger('click')
  expect(wrapper.get('[data-testid="symbol-dialog"]').text()).toBe(`12 / ${analysis.signs[0].id} / tablet.png`)
})
