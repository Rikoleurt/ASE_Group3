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

async function upload(response) {
  const fetch = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(AnalysisView)
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
    expect(card.textContent).toContain('Interpretationta J / VIN J / ku-ro J')
    expect(card.textContent).toContain('Confidence83%')
    expect(card.textContent).toContain('Processing time2.7 s')
  })

  it('draws the boxes on the uploaded image and adds the fraction check below', async () => {
    await upload({ ok: true, json: async () => analysis })

    expect(wrapper.get('img').attributes('src')).toBe('blob:preview')
    expect(wrapper.findAll('[data-testid="sign-box"]')).toHaveLength(analysis.signs.length)
    expect(wrapper.find('[data-testid="formula-box"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="verdict"]').text()).toBe('The fractions do not balance: off by 1/2')
  })

  it('goes back to the upload box from the result', async () => {
    await upload({ ok: true, json: async () => analysis })
    await wrapper.findAll('button').find((button) => button.text() === 'Analyze another image').trigger('click')

    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="formula"]').exists()).toBe(false)
  })

  it('shows the server message when the reader is unavailable', async () => {
    await upload({ ok: false, status: 503, json: async () => ({ detail: 'The sign reader is unavailable.' }) })

    expect(wrapper.get('[role="alert"]').text()).toBe('The sign reader is unavailable.')
  })
})
