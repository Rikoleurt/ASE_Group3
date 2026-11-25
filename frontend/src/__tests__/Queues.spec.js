import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import QueuesView from '../views/QueuesView.vue'
import { sessionReviewer } from '../state/session'

const BOX = { x: 0.1, y: 0.1, w: 0.1, h: 0.2 }
const row = (slug, score, extra = {}) => ({
  slug,
  tablet: slug.replace('-', ' '),
  agree: 1,
  differs: 1,
  missing: 0,
  total: 2,
  score,
  ...extra,
})
const RESPONSES = {
  'disagreement?offset=0&limit=25&against=model': {
    against: 'model',
    built_at: '2026-11-25T10:00:00+00:00',
    model_version: 'reader-7',
    total: 26,
    items: [row('HT-1', 0.5), row('HT-2', 0.25)],
  },
  'disagreement?offset=2&limit=25&against=model': {
    against: 'model',
    built_at: '2026-11-25T10:00:00+00:00',
    total: 26,
    items: [row('HT-3', 0.1)],
  },
  'disagreement?offset=0&limit=25&against=edition': {
    against: 'edition',
    total: 1,
    items: [row('HT-13', 0.75, { release_id: 9, edition_id: 4 })],
  },
  'low-confidence?offset=0&limit=25': {
    missing_hint: 'Build it with: python scripts/build_disagreement.py',
    threshold: 50,
    total: 0,
    items: [],
  },
  'close-votes?offset=0&limit=25': {
    total: 1,
    items: [
      {
        slug: 'HT-13',
        tablet: 'HT 13',
        gap: 0,
        votes: 2,
        releases: [
          { id: 9, title: 'Agreed', owner: 'anouk', votes: 1 },
          { id: 10, title: null, owner: 'dev', votes: 1 },
        ],
      },
    ],
  },
}

let wrapper
let router
let requested

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
  sessionReviewer.value = false
})

async function render(path = '/queues', responses = RESPONSES) {
  requested = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      requested.push(url)
      if (url.startsWith('/api/corrections')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: 5,
              analysis_id: 3,
              sign_id: 2,
              created_at: '2026-11-25T09:00:00',
              original_label: 'AB77 (ka)',
              proposed_sign: 'AB01',
              uncertain: false,
            },
          ],
        }
      }
      const body = responses[url.replace('/api/queues/', '')]
      if (body === 401) return { ok: false, status: 401, json: async () => ({}) }
      return body
        ? { ok: true, status: 200, json: async () => body }
        : { ok: false, status: 500, json: async () => ({}) }
    }),
  )
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/queues', component: QueuesView },
      { path: '/login', component: { template: '<p />' } },
      { path: '/:rest(.*)*', component: { template: '<p />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
}

const rows = () => wrapper.findAll('[data-testid="queue-row"]')

describe('Work queues', () => {
  it('lists the tablets where the scholars and the model disagree most, linking to compare', async () => {
    await render()
    expect(wrapper.get('[data-testid="queue-count"]').text()).toBe('26 items')
    expect(wrapper.get('[data-testid="queue-built"]').text()).toContain('model reader-7')
    expect(rows().map((r) => r.text())).toEqual([
      expect.stringContaining('1 of 2 places differ'),
      expect.stringContaining('1 of 2 places differ'),
    ])
    expect(rows()[0].get('[data-testid="queue-action"]').attributes('href')).toBe(
      '/tablets/HT-1/compare?v=scholar&v=model',
    )
  })

  it('pages with Show more', async () => {
    await render()
    await wrapper.get('[data-testid="queue-more"]').trigger('click')
    await flushPromises()
    expect(rows()).toHaveLength(3)
    expect(wrapper.get('[data-testid="queue-more"]').text()).toBe('Show more (23 left)')
  })

  it('compares the scholars with the community edition', async () => {
    await render()
    await wrapper.get('[data-testid="against-edition"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tab: 'disagreement', against: 'edition' })
    expect(rows()).toHaveLength(1)
    expect(rows()[0].get('[data-testid="queue-action"]').attributes('href')).toBe(
      '/tablets/HT-13/compare?v=scholar&v=copy:4',
    )
  })

  it('says how to build the model readings when they are missing', async () => {
    await render('/queues?tab=low-confidence')
    expect(wrapper.get('[data-testid="queue-missing"]').text()).toContain('build_disagreement.py')
    expect(wrapper.find('[data-testid="queue-empty"]').exists()).toBe(false)
  })

  it('shows close votes with both releases', async () => {
    await render('/queues?tab=close-votes')
    expect(rows()[0].text()).toContain('Tied')
    expect(
      rows()[0]
        .findAll('a')
        .map((a) => a.attributes('href')),
    ).toEqual(['/tablets/HT-13', '/editions/9', '/editions/10', '/tablets/HT-13'])
    expect(rows()[0].text()).toContain("dev's edition")
  })

  it('offers the review queue to reviewers only', async () => {
    await render()
    expect(wrapper.find('[data-testid="queue-tab-review"]').exists()).toBe(false)
    wrapper.unmount()
    sessionReviewer.value = true
    await render('/queues?tab=review')
    expect(requested).toContain('/api/corrections?status=pending&limit=200')
    expect(rows()[0].text()).toContain('AB77 (ka) → AB01')
  })

  it('moves between tabs with the arrow keys', async () => {
    await render()
    await wrapper
      .get('[data-testid="queue-tab-disagreement"]')
      .trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('close-votes')
  })

  it('sends a logged-out visitor to log in', async () => {
    await render('/queues', { ...RESPONSES, 'disagreement?offset=0&limit=25&against=model': 401 })
    expect(router.currentRoute.value.fullPath).toBe('/login?redirect=/queues')
  })
})
