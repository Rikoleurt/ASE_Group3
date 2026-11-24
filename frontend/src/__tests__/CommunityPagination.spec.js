import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CommunityView from '../views/CommunityView.vue'

let wrapper
let observer
const parent = { id: 3, analysis_id: 12, sign_id: null, title: 'HT13 discussion', tablet_filename: 'HT13.png', author_username: 'owner' }
const child = { ...parent, id: 4, sign_id: 0, title: 'ri', symbol_name: 'ri' }
const ok = (items = [], next_cursor = null, parents = []) => ({
  ok: true, json: async () => ({ items, next_cursor, parents }),
})
const button = (label) => wrapper.findAll('button').find((item) => item.text() === label)
const intersect = () => observer.callback([{ isIntersecting: true }])

beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback) {
      this.callback = callback
      this.observe = vi.fn()
      this.unobserve = vi.fn()
      this.disconnect = vi.fn()
      observer = this
    }
  })
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function render(fetch) {
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(CommunityView, { global: { stubs: {
    RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
  } } })
  await flushPromises()
}

it('loads only 30 matches and attaches their parent without loading unrelated symbols', async () => {
  const fetch = vi.fn().mockResolvedValue(ok([child], null, [parent]))
  await render(fetch)
  expect(fetch).toHaveBeenCalledOnce()
  expect(fetch).toHaveBeenCalledWith('/api/community/discussions?limit=30&filter_by=recent', expect.objectContaining({ cache: 'no-store', signal: expect.any(AbortSignal) }))
  expect(wrapper.get('h2').text()).toBe(parent.title)
  expect(wrapper.findAll('h3').map((item) => item.text())).toEqual(['ri'])
  expect(wrapper.get('a[href="/community/3"]').exists()).toBe(true)
  intersect(); await flushPromises()
  expect(fetch).toHaveBeenCalledOnce()
  expect(wrapper.text()).toContain('All matching discussions have been loaded')
})

it('fetches the next page on intersection once, shows a spinner, and stops at the end', async () => {
  let resolve
  const fetch = vi.fn().mockResolvedValueOnce(ok([child], 'page-two', [parent]))
    .mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  await render(fetch)
  intersect(); intersect(); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(wrapper.get('[role="status"]').text()).toBe('Loading discussions…')
  expect(wrapper.get('[role="status"] [aria-hidden="true"]').classes()).toContain('animate-spin')
  expect(fetch.mock.calls[1][0]).toBe('/api/community/discussions?limit=30&filter_by=recent&cursor=page-two')
  expect(wrapper.find('a[href="/community/4"]').exists()).toBe(true)
  resolve(ok([child, { ...child, id: 5, sign_id: 1, title: 'ki' }]))
  await flushPromises()
  expect(wrapper.findAll('a[href="/community/4"]')).toHaveLength(1)
  expect(wrapper.findAll('h3')).toHaveLength(2)
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
  // Re-observing after layout also handles short pages that leave the bottom visible.
  expect(observer.observe.mock.calls.length).toBeGreaterThan(1)
  intersect(); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('debounces text search, sends the selected mode, and resets the cursor', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  const fetch = vi.fn().mockResolvedValue(ok([child], 'old-cursor', [parent]))
  await render(fetch)
  await button('Tablet name').trigger('click'); await flushPromises()
  await wrapper.get('input').setValue('HT')
  await vi.advanceTimersByTimeAsync(150)
  await wrapper.get('input').setValue('HT13')
  expect(wrapper.find('h3').exists()).toBe(false)
  expect(wrapper.get('[role="status"]').text()).toBe('Searching discussions…')
  await vi.advanceTimersByTimeAsync(299)
  expect(fetch).toHaveBeenCalledTimes(2)
  await vi.advanceTimersByTimeAsync(1); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(3)
  expect(fetch.mock.calls[2][0]).toBe('/api/community/discussions?limit=30&filter_by=tablet&q=HT13')
  await button('Author').trigger('click'); await flushPromises()
  expect(fetch.mock.lastCall[0]).toBe('/api/community/discussions?limit=30&filter_by=author&q=HT13')
  await button('Most recent').trigger('click'); await flushPromises()
  expect(fetch.mock.lastCall[0]).toBe('/api/community/discussions?limit=30&filter_by=recent')
  expect(wrapper.find('input').exists()).toBe(false)
})

it('aborts and ignores a stale response when switching searches', async () => {
  let resolveOld
  const fetch = vi.fn().mockImplementationOnce(() => new Promise((done) => { resolveOld = done }))
    .mockResolvedValue(ok([{ ...parent, id: 9, analysis_id: 20, title: 'New result' }]))
  await render(fetch)
  expect(wrapper.get('[role="status"]').text()).toBe('Loading discussions…')
  await button('Author').trigger('click'); await flushPromises()
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true)
  resolveOld(ok([child], 'stale-cursor', [parent])); await flushPromises()
  expect(wrapper.get('h2').text()).toBe('New result')
  expect(wrapper.find('a[href="/community/4"]').exists()).toBe(false)
  intersect(); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('keeps existing results on a page failure and retries the same cursor explicitly', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(ok([parent], 'next'))
    .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ detail: 'Please retry' }) })
    .mockResolvedValueOnce(ok([{ ...parent, id: 2, analysis_id: 13, title: 'Next tablet' }]))
  await render(fetch)
  intersect(); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe('Please retry')
  expect(wrapper.get('h2').text()).toBe(parent.title)
  intersect(); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
  await button('Try again').trigger('click'); await flushPromises()
  expect(fetch.mock.calls[2][0]).toBe(fetch.mock.calls[1][0])
  expect(wrapper.findAll('h2')).toHaveLength(2)
})

it('shows an empty-search message and supports immediate submission and clearing', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  const fetch = vi.fn().mockResolvedValue(ok())
  await render(fetch)
  await button('Author').trigger('click'); await flushPromises()
  await wrapper.get('input').setValue('nobody')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.text()).toContain('No discussions match your search')
  expect(fetch.mock.lastCall[0]).toBe('/api/community/discussions?limit=30&filter_by=author&q=nobody')
  await vi.advanceTimersByTimeAsync(300); await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(3)
  await wrapper.get('input').setValue('')
  await vi.advanceTimersByTimeAsync(300); await flushPromises()
  expect(fetch.mock.lastCall[0]).toBe('/api/community/discussions?limit=30&filter_by=author')
})

it('disconnects the observer and aborts the request on unmount', async () => {
  const fetch = vi.fn(() => new Promise(() => {}))
  await render(fetch)
  wrapper.unmount()
  expect(observer.disconnect).toHaveBeenCalledOnce()
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true)
  wrapper = null
})
