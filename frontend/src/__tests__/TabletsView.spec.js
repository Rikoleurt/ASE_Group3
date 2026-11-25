import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabletsView from '../views/TabletsView.vue'
import { forgetSession } from '../state/session'

const SIGN = { id: 1, sign: 'AB77', label: 'AB77 (ka)', reading: 'ka', role: 'syllabogram', confidence: 100, detection_confidence: 100,
  box: { x: 0.1, y: 0.1, w: 0.1, h: 0.2 }, candidates: [], line: 0, order: 0 }
const boxes = (source, extra = {}) => ({
  slug: 'HT-13', tablet: 'HT 13', source, width: 1000, height: 500, image_url: '/tablets/HT-13/image',
  symbol_interpretation: 'ka', summary: '1 sign found: 1 syllabogram.', signs: [SIGN], lines: [], formulas: [],
  credit: { licence: 'CC BY-NC-SA 4.0', url: 'https://creativecommons.org/licenses/by-nc-sa/4.0/', text: 'From SigLA via lineara.eu.' },
  ...extra,
})
const PAGE = { items: [{ slug: 'HT-13', tablet: 'HT 13', signs: 27 }, { slug: 'HT-130', tablet: 'HT 130', signs: 9 }], total: 2 }
const SESSION = { user: { id: 1, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf' }

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body })

function stubServer(routes, session = SESSION) {
  const fetch = vi.fn((url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (url === '/api/users/me') return session ? json(session) : json({ detail: 'Please log in.' }, 401)
    if (url.startsWith('/api/tablets?')) return json(PAGE)
    return routes[key] ? routes[key](options) : json({ detail: 'Corrected copy not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function render(path = '/tablets/HT-13') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/tablets/:slug?', component: TabletsView },
    { path: '/box-sets/:id', component: { template: '<p>Editor</p>' } },
    { path: '/login', component: { template: '<p>Login</p>' } },
  ] })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('Tablets page', () => {
  it('lists tablets and shows the scholars\' boxes with the credit', async () => {
    stubServer({ 'GET /api/tablets/HT-13/boxes?source=scholar': () => json(boxes('scholar')) })
    await render()
    expect(wrapper.findAll('[data-testid="tablet-list"] button').map((b) => b.text())).toEqual(['HT 1327 signs', 'HT 1309 signs'])
    expect(wrapper.get('img').attributes('src')).toBe('/api/tablets/HT-13/image')
    expect(wrapper.findAll('[data-testid="sign-box"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="credit"]').text()).toContain('CC BY-NC-SA 4.0')
    expect(wrapper.get('[data-testid="source-scholar"]').attributes('aria-pressed')).toBe('true')
  })

  it('switches to the model\'s boxes through the URL', async () => {
    const fetch = stubServer({
      'GET /api/tablets/HT-13/boxes?source=scholar': () => json(boxes('scholar')),
      'GET /api/tablets/HT-13/boxes?source=model': () => json(boxes('model')),
    })
    const router = await render()
    await wrapper.get('[data-testid="source-model"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/tablets/HT-13?boxes=model')
    expect(fetch.mock.calls.some(([url]) => url === '/api/tablets/HT-13/boxes?source=model')).toBe(true)
    expect(wrapper.get('[data-testid="correct-boxes"]').text()).toBe("Correct the model's boxes")
  })

  it('starts a corrected copy from the boxes on show', async () => {
    const fetch = stubServer({
      'GET /api/tablets/HT-13/boxes?source=scholar': () => json(boxes('scholar')),
      'POST /api/box-sets': () => json({ id: 7 }, 201),
    })
    const router = await render()
    await wrapper.get('[data-testid="correct-boxes"]').trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(([url, o]) => url === '/api/box-sets' && o?.method === 'POST')
    expect(JSON.parse(options.body)).toEqual({ tablet: 'HT-13', start: 'scholar' })
    expect(router.currentRoute.value.path).toBe('/box-sets/7')
  })

  it('opens an existing copy instead of making another', async () => {
    stubServer({
      'GET /api/tablets/HT-13/boxes?source=scholar': () => json(boxes('scholar')),
      'GET /api/tablets/HT-13/box-set': () => json({ id: 3 }),
    })
    const router = await render()
    const button = wrapper.get('[data-testid="correct-boxes"]')
    expect(button.text()).toBe('Open your corrected copy')
    await button.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/box-sets/3')
  })

  it('lets logged-out visitors look, and asks them to log in to correct', async () => {
    stubServer({ 'GET /api/tablets/HT-13/boxes?source=scholar': () => json(boxes('scholar')) }, null)
    await render()
    expect(wrapper.find('[data-testid="correct-boxes"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Log in to correct the boxes')
    expect(wrapper.findAll('[data-testid="sign-box"]')).toHaveLength(1)
  })

  it('explains a missing reader or tablet', async () => {
    stubServer({
      'GET /api/tablets/HT-13/boxes?source=model': () => json({ detail: 'The Linear A sign reader is not installed.' }, 503),
    })
    await render('/tablets/HT-13?boxes=model')
    expect(wrapper.get('[role="alert"]').text()).toBe('The Linear A sign reader is not installed.')
  })

  it('says when tablets are hidden because their drawings are not downloaded', async () => {
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url === '/api/users/me') return json(SESSION)
      if (url.startsWith('/api/tablets?')) return json({ items: [], total: 0, without_drawing: 706, hint: 'Download them with: python scripts/fetch_corpus.py' })
      return json({ detail: "This tablet's drawing is not on this server. Download them with: python scripts/fetch_corpus.py" }, 404)
    }))
    await render('/tablets/HT-13')
    expect(wrapper.get('[data-testid="missing-drawings"]').text()).toContain('706 more tablets are hidden')
    expect(wrapper.get('[data-testid="missing-drawings"]').text()).toContain('scripts/fetch_corpus.py')
    expect(wrapper.get('[role="alert"]').text()).toContain("This tablet's drawing is not on this server.")
  })

  it('lets an admin download the missing drawings, shows progress, then lists the tablets', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    let downloaded = false
    let polls = 0
    const fetch = vi.fn((url, options = {}) => {
      const key = `${options.method ?? 'GET'} ${url}`
      if (url === '/api/users/me') return json({ ...SESSION, admin: true })
      if (url.startsWith('/api/tablets?')) return json(downloaded ? PAGE : { items: [], total: 0, without_drawing: 706, hint: 'Download them with: python scripts/fetch_corpus.py' })
      if (key === 'POST /api/tablets/download') return json({ state: 'running', log: ['downloading linear_a_corpus.zip (1.9 MB)…'], error: null }, 202)
      if (key === 'GET /api/tablets/download') {
        polls += 1
        downloaded = polls > 1
        return json(downloaded ? { state: 'done', log: ['  unpacked 731 file(s) into fraction-solver/'], error: null }
          : { state: 'running', log: ['downloading linear_a_tracings.zip (31.2 MB)…'], error: null })
      }
      return json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    try {
      await render('/tablets')
      await wrapper.get('[data-testid="download-corpus"]').trigger('click')
      await flushPromises()
      const post = fetch.mock.calls.find(([url, options]) => url === '/api/tablets/download' && options?.method === 'POST')
      expect(post[1].headers['X-CSRF-Token']).toBe('csrf')
      expect(wrapper.get('[data-testid="download-corpus"]').attributes('disabled')).toBeDefined()
      expect(wrapper.get('[data-testid="download-progress"]').text()).toContain('linear_a_corpus.zip')
      await vi.advanceTimersByTimeAsync(1500)
      await flushPromises()
      expect(wrapper.get('[data-testid="download-progress"]').text()).toContain('linear_a_tracings.zip')
      await vi.advanceTimersByTimeAsync(1500)
      await flushPromises()
      expect(wrapper.findAll('[data-testid="tablet-list"] button')).toHaveLength(2)
      expect(wrapper.get('[data-testid="missing-drawings"]').text()).toContain('Downloaded.')
      expect(wrapper.find('[data-testid="download-corpus"]').exists()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('tells others an admin can download the drawings, without a button', async () => {
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url === '/api/users/me') return json(SESSION)
      if (url.startsWith('/api/tablets?')) return json({ items: [], total: 0, without_drawing: 3, hint: 'Download them with: python scripts/fetch_corpus.py' })
      return json({ detail: 'Not found.' }, 404)
    }))
    await render('/tablets')
    expect(wrapper.find('[data-testid="download-corpus"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="missing-drawings"]').text()).toContain('An admin can download them from this page.')
  })

  it('offers the download to an admin when the corpus is not installed at all', async () => {
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url === '/api/users/me') return json({ ...SESSION, admin: true })
      if (url.startsWith('/api/tablets?')) return json({ detail: 'The cached lineara.eu corpus is not installed on this server.' }, 503)
      return json({ detail: 'Not found.' }, 404)
    }))
    await render('/tablets')
    expect(wrapper.get('[data-testid="download-corpus"]').text()).toContain('Download the drawings')
  })

  it('asks for a tablet when none is chosen', async () => {
    stubServer({})
    await render('/tablets')
    expect(wrapper.text()).toContain('Pick a tablet to see its boxes.')
  })
})
