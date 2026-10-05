import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabletDemoView from '../views/TabletDemoView.vue'

let wrapper

afterEach(() => wrapper?.unmount())

async function render() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tablet-demo', component: TabletDemoView }],
  })
  await router.push('/tablet-demo')
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
}

describe('HT13 Sprint 1 demo', () => {
  it('displays original and annotated images through the existing API proxy', async () => {
    await render()
    const images = wrapper.findAll('img')
    expect(images.map((image) => image.attributes('src'))).toEqual([
      '/api/tablet-demo/ht13?annotated=false',
      '/api/tablet-demo/ht13',
    ])
    expect(wrapper.text()).toContain('generic pretrained YOLO baseline')
    expect(wrapper.text()).toContain('not validated character detections')
    expect(wrapper.text()).toContain('No boxes means no detections')
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    await images[1].trigger('load')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('reports an unavailable image', async () => {
    await render()
    await wrapper.findAll('img')[1].trigger('error')
    expect(wrapper.get('[role="alert"]').text()).toContain('could not be loaded')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })
})
