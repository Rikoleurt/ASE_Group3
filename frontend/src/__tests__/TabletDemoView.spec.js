import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TabletDemoView from '../views/TabletDemoView.vue'

let wrapper
const predictions = [{ id: 1, label: 'object', confidence: 72.34, imageUrl: 'data:image/png;base64,crop', box: { x: 0.1, y: 0.2, w: 0.3, h: 0.4 } }]
const response = (items = predictions) => ({ ok: true, json: async () => ({ width: 1000, height: 2000, predictions: items }) })

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

async function render(fetch = vi.fn().mockResolvedValue(response())) {
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(TabletDemoView)
  await flushPromises()
  return fetch
}

describe('HT13 demo', () => {
  it('loads real predictions on the left and preserves the original cards on the right', async () => {
    const fetch = await render()
    expect(fetch).toHaveBeenCalledWith('/api/tablet-demo/ht13/predictions')
    const image = wrapper.get('img')
    expect(image.attributes('src')).toBe('/api/tablet-demo/ht13?annotated=false')
    expect(wrapper.get('main > section').classes()).toContain('md:w-1/3')
    await image.trigger('load')
    const box = wrapper.get('[data-testid="prediction-box"]')
    expect(box.attributes('style')).toContain('left: 10%; top: 20%; width: 30%; height: 40%;')
    const right = wrapper.findAll('main > section')[1]
    expect(right.findAll('li')).toHaveLength(6)
    expect(right.findAll('li').map((card) => card.get('p').text())).toEqual([
      'Symbol: ha', 'Symbol: lo', 'Symbol: sa', 'Symbol: es', 'Symbol: an', 'Symbol: en',
    ])
    expect(right.get('button').text()).toBe('Learn More')
    expect(right.text()).not.toContain('object')
  })

  it('shows the empty prediction message below the tablet and preserves the right panel', async () => {
    await render(vi.fn().mockResolvedValue(response([])))
    await wrapper.get('img').trigger('load')
    const [left, right] = wrapper.findAll('main > section')
    const status = left.get('[role="status"]')
    expect(status.text()).toBe('No detections found on HT13.')
    expect(status.element.previousElementSibling.contains(left.get('img').element)).toBe(true)
    expect(right.text()).not.toContain('No detections found')
    expect(wrapper.findAll('[data-testid="prediction-box"]')).toHaveLength(0)
    expect(wrapper.findAll('li')).toHaveLength(6)
  })

  it('shows inference loading separately from image loading', async () => {
    let resolve
    await render(vi.fn().mockReturnValue(new Promise((done) => { resolve = done })))
    await wrapper.get('img').trigger('load')
    expect(wrapper.get('[role="status"]').text()).toBe('Loading predictions…')
    expect(wrapper.text()).not.toContain('No detections found')
    resolve(response())
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('allows retry after a prediction failure', async () => {
    const fetch = await render(vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    expect(wrapper.get('[role="alert"]').text()).toContain('could not be loaded')
    fetch.mockResolvedValue(response())
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    await wrapper.get('img').trigger('load')
    expect(wrapper.findAll('[data-testid="prediction-box"]')).toHaveLength(1)
  })

  it('handles network errors', async () => {
    await render(vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect(wrapper.get('[role="alert"]').text()).toContain('Unable to reach the server')
  })

  it('uses the existing image error placeholders when an image fails', async () => {
    await render()
    await wrapper.get('img').trigger('error')
    expect(wrapper.get('[role="alert"]').text()).toContain('issue loading the tablet image')
    expect(wrapper.find('[data-testid="prediction-box"]').exists()).toBe(false)
    expect(wrapper.get('li').text()).toContain('issue loading the symbol image')
  })
})
