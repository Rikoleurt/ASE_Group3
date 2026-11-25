import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabletsView from '../views/TabletsView.vue'
import CompareView from '../views/CompareView.vue'
import { versionName } from '../components/versions/versions'
import { forgetSession } from '../state/session'

const SESSION = { user: { id: 7, username: 'dev', email: 'dev@ase3.com' }, csrf_token: 'csrf' }
const VERSIONS = {
  slug: 'HT-13',
  tablet: 'HT 13',
  items: [
    { key: 'scholar', kind: 'scholar', box_count: 27 },
    { key: 'model', kind: 'model', needs_login: true, box_count: null },
    {
      key: 'copy:4',
      kind: 'copy',
      title: 'First go',
      owner: 'dev',
      mine: true,
      permission: 'owner',
      box_count: 26,
    },
    {
      key: 'copy:9',
      kind: 'edition',
      title: null,
      owner: 'anouk',
      mine: false,
      permission: 'view',
      box_count: 27,
    },
  ],
}
const box = (x, sign, id = 1) => ({
  id,
  box: { x, y: 0.1, w: 0.1, h: 0.1 },
  sign,
  label: `${sign} (x)`,
})
const COMPARISON = {
  slug: 'HT-13',
  tablet: 'HT 13',
  width: 1000,
  height: 500,
  image_url: '/tablets/HT-13/image',
  versions: [VERSIONS.items[0], VERSIONS.items[2]],
  clusters: [
    {
      box: box(0.1).box,
      members: { scholar: box(0.1, 'AB81'), 'copy:4': box(0.1, 'AB81', 5) },
      status: 'agree',
      moved: false,
    },
    {
      box: box(0.3).box,
      members: { scholar: box(0.3, 'AB01'), 'copy:4': box(0.3, 'AB02', 6) },
      status: 'differs',
      moved: false,
    },
    { box: box(0.5).box, members: { scholar: box(0.5, 'AB59') }, status: 'missing', moved: false },
  ],
  agreement: [{ a: 'scholar', b: 'copy:4', same: 1, total: 3 }],
}

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })

async function render(path, component) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tablets/:slug/compare', component: CompareView },
      { path: '/tablets/:slug?', component: TabletsView },
      { path: '/box-sets/:id', component: { template: '<p>Editor</p>' } },
      { path: '/login', component: { template: '<p>Login</p>' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount(component ?? { template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('version names', () => {
  it('says whose version it is', () => {
    expect(VERSIONS.items.map(versionName)).toEqual([
      "Scholars' boxes",
      "Model's boxes",
      'Your copy: First go',
      "anouk's edition",
    ])
  })
})

describe('Versions on the Tablets page', () => {
  function serve(extra = {}) {
    const fetch = vi.fn((url, options = {}) => {
      const key = `${options.method ?? 'GET'} ${url}`
      if (url === '/api/users/me') return json(SESSION)
      if (url.startsWith('/api/tablets?'))
        return json({ items: [{ slug: 'HT-13', tablet: 'HT 13', signs: 27 }], total: 1 })
      if (url === '/api/tablets/HT-13/versions') return json(VERSIONS)
      if (url.startsWith('/api/tablets/HT-13/boxes')) {
        return json({
          slug: 'HT-13',
          tablet: 'HT 13',
          source: 'scholar',
          width: 1000,
          height: 500,
          image_url: '/tablets/HT-13/image',
          symbol_interpretation: '',
          summary: '',
          signs: [],
          lines: [],
          formulas: [],
          credit: { licence: 'CC BY-NC-SA 4.0', url: '', text: '' },
        })
      }
      if (url === '/api/tablets/HT-13/box-set') return json({ id: 4 })
      return extra[key] ? extra[key](options) : json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  it('lists the versions you can see and compares the ticked ones', async () => {
    serve()
    const router = await render('/tablets/HT-13')
    const rows = wrapper.findAll('[data-testid="version"]')
    expect(rows.map((row) => row.text())).toEqual([
      "Scholars' boxes · 27 boxes",
      "Model's boxes",
      'Your copy: First go · 26 boxesOpen',
      "anouk's edition · 27 boxes· you can viewOpen",
    ])
    const compare = wrapper.get('[data-testid="compare-versions"]')
    expect(compare.attributes('disabled')).toBeDefined()
    await rows[0].get('input').setValue(true)
    await rows[2].get('input').setValue(true)
    expect(compare.attributes('disabled')).toBeUndefined()
    expect(compare.text()).toBe('Compare 2 versions')
    await compare.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/tablets/HT-13/compare?v=scholar&v=copy:4')
  })

  it('makes another copy when you already have one', async () => {
    const fetch = serve({ 'POST /api/box-sets': () => json({ id: 11 }, 201) })
    const router = await render('/tablets/HT-13')
    await wrapper.get('[data-testid="new-copy"]').trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/box-sets' && o?.method === 'POST',
    )
    expect(JSON.parse(options.body)).toEqual({ tablet: 'HT-13', start: 'scholar', new: true })
    expect(router.currentRoute.value.path).toBe('/box-sets/11')
  })
})

describe('Compare page', () => {
  function serve(response = json(COMPARISON)) {
    const fetch = vi.fn((url) => {
      if (url.startsWith('/api/tablets/HT-13/compare')) return response
      if (url === '/api/corrections/catalogue') return json([])
      return json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  it("shows each place with every version's sign and how often they agree", async () => {
    const fetch = serve()
    await render('/tablets/HT-13/compare?v=scholar&v=copy:4')
    expect(fetch).toHaveBeenCalledWith('/api/tablets/HT-13/compare?v=scholar&v=copy%3A4')
    expect(wrapper.get('h1').text()).toBe('Compare versions of HT 13')
    expect(wrapper.findAll('[data-testid="legend"]').map((item) => item.text())).toEqual([
      "Scholars' boxes (27)(shown; select to hide)",
      'Your copy: First go (26)(shown; select to hide)',
    ])
    expect(wrapper.get('[data-testid="agreement"]').text()).toContain(
      "Scholars' boxes and Your copy: First go33%1 of 3 places",
    )
    expect(wrapper.get('[data-testid="counts"]').text()).toBe(
      '1 agree · 1 with different signs · 1 missing from some',
    )
    const rows = wrapper.findAll('[data-testid="place-row"]')
    expect(rows.map((row) => row.get('[data-testid="place-status"]').text())).toEqual([
      'Agree',
      'Different signs',
      'Missing from some',
    ])
    expect(rows[1].text()).toContain('AB01 (x)')
    expect(rows[1].text()).toContain('AB02 (x)')
    expect(rows[2].text()).toContain('Not in: Your copy: First go')
    expect(wrapper.findAll('[data-testid="version-box"]')).toHaveLength(5)
  })

  it('selects a place from the list or the tablet, filters to differences and hides a version', async () => {
    serve()
    await render('/tablets/HT-13/compare?v=scholar&v=copy:4')
    await wrapper.findAll('[data-testid="place-row"]')[1].trigger('click')
    expect(wrapper.findAll('[data-testid="place"]')[1].attributes('aria-pressed')).toBe('true')
    await wrapper.findAll('[data-testid="place"]')[2].trigger('click')
    expect(wrapper.findAll('[data-testid="place-row"]')[2].attributes('aria-pressed')).toBe('true')
    await wrapper.get('[data-testid="only-differences"]').setValue(true)
    expect(wrapper.findAll('[data-testid="place-row"]')).toHaveLength(2)
    await wrapper.get('#show-copy\\:4').setValue(true) // hide your copy's boxes
    expect(wrapper.findAll('[data-testid="version-box"]')).toHaveLength(3)
  })

  it('explains a refusal and sends logged-out visitors to log in', async () => {
    serve(json({ detail: 'Corrected copy not found.' }, 404))
    await render('/tablets/HT-13/compare?v=scholar&v=copy:99')
    expect(wrapper.get('[role="alert"]').text()).toBe('Corrected copy not found.')
    wrapper.unmount()
    serve(json({ detail: 'Please log in.' }, 401))
    const router = await render('/tablets/HT-13/compare?v=scholar&v=model')
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
