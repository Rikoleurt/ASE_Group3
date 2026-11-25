import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabletsView from '../views/TabletsView.vue'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import { forgetSession } from '../state/session'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const RESULTS = {
  query: 'ku-ro',
  source: 'scholar',
  total_tablets: 2,
  total_hits: 3,
  items: [
    {
      slug: 'HT-100',
      tablet: 'HT 100',
      release_id: null,
      hits: [{ line: 2, positions: [7, 8], text: 'ku-ro' }],
    },
    {
      slug: 'HT-13',
      tablet: 'HT 13',
      release_id: null,
      hits: [
        { line: 6, positions: [25, 26], text: 'ku-ro' },
        { line: 7, positions: [27, null], text: 'ku-ro' },
      ],
    },
  ],
}

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

function serve(search = () => json(RESULTS)) {
  const fetch = vi.fn((url) => {
    if (url === '/api/users/me') return json({ detail: 'Please log in.' }, 401)
    if (url.startsWith('/api/tablets?'))
      return json({ items: [{ slug: 'HT-13', tablet: 'HT 13', signs: 27 }], total: 1 })
    if (url.startsWith('/api/corpus/search?')) return search(url)
    return json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function render(path = '/tablets') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tablets/:slug?', component: TabletsView },
      { path: '/editions/:id', component: { template: '<p>Edition</p>' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('Searching by sign sequence', () => {
  it('lists the tablets with the sequence and opens one with the matches highlighted', async () => {
    const fetch = serve()
    const router = await render()
    await wrapper.get('[data-testid="search-sequence"]').trigger('click')
    await wrapper.get('#tablet-search').setValue('KU-RO')
    await wrapper.get('[data-testid="across-words"]').setValue(true)
    await wrapper.get('form[role="search"]').trigger('submit')
    await flushPromises()
    const url = fetch.mock.calls.map(([u]) => u).find((u) => u.startsWith('/api/corpus/search?'))
    expect(new URLSearchParams(url.split('?')[1]).toString()).toBe(
      'q=KU-RO&source=scholar&across_words=true&limit=100',
    )
    expect(wrapper.get('[data-testid="sequence-count"]').text()).toBe('3 matches on 2 tablets')
    const results = wrapper.findAll('[data-testid="sequence-results"] button')
    expect(results.map((r) => r.text())).toEqual(['HT 1001×ku-ro', 'HT 132×ku-ro'])
    expect(wrapper.find('[data-testid="tablet-list"]').exists()).toBe(false)
    await results[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/tablets/HT-13?hl=25,26,27')
  })

  it('searches the community editions and opens the matching release', async () => {
    serve(() =>
      json({ ...RESULTS, source: 'edition', items: [{ ...RESULTS.items[0], release_id: 9 }] }),
    )
    const router = await render()
    await wrapper.get('[data-testid="search-sequence"]').trigger('click')
    await wrapper.get('[data-testid="sequence-source"]').setValue('edition')
    await wrapper.get('#tablet-search').setValue('ku-ro')
    await wrapper.get('form[role="search"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-testid="sequence-results"]').text()).toContain(
      'in the community edition',
    )
    await wrapper.get('[data-testid="sequence-results"] button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/editions/9')
  })

  it('explains a query that is not a sign sequence', async () => {
    serve(() =>
      json(
        { detail: '“r$o” is not a sign: use a sign ID, a reading, * or alternatives with |.' },
        422,
      ),
    )
    await render()
    await wrapper.get('[data-testid="search-sequence"]').trigger('click')
    await wrapper.get('#tablet-search').setValue('ku-r$o')
    await wrapper.get('form[role="search"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('is not a sign')
  })

  it('highlights the found signs on the tablet', () => {
    const sign = (id, x) => ({
      id,
      sign: 'AB81',
      label: 'AB81 (ku)',
      reading: 'ku',
      role: 'syllabogram',
      confidence: 100,
      detection_confidence: 100,
      box: { x, y: 0.1, w: 0.1, h: 0.1 },
      candidates: [],
    })
    wrapper = mount(TabletOverlay, {
      props: { signs: [sign(25, 0.1), sign(26, 0.3), sign(30, 0.5)], highlight: [25, 26] },
    })
    expect(
      wrapper.findAll('[data-testid="sign-box"]').map((box) => box.classes().includes('found')),
    ).toEqual([true, true, false])
  })
})
