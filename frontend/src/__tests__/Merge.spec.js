import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import MergeView from '../views/MergeView.vue'
import { defaultPick, majorityPicks, takeAllFrom } from '../components/versions/mergeDefaults'
import { forgetSession } from '../state/session'

const KEYS = ['scholar', 'copy:4', 'copy:9']
const at = (x, sign, id = 1) => ({
  id,
  box: { x, y: 0.1, w: 0.1, h: 0.1 },
  sign,
  label: `${sign} (x)`,
})
const PLACES = [
  {
    box: at(0.1).box,
    members: { scholar: at(0.1, 'AB81'), 'copy:4': at(0.1, 'AB81'), 'copy:9': at(0.1, 'AB81') },
    status: 'agree',
    moved: false,
  },
  {
    box: at(0.3).box,
    members: { scholar: at(0.3, 'AB01'), 'copy:4': at(0.3, 'AB02'), 'copy:9': at(0.3, 'AB02') },
    status: 'differs',
    moved: false,
  },
  {
    box: at(0.5).box,
    members: { 'copy:4': at(0.5, 'AB59'), 'copy:9': at(0.5, 'AB60') },
    status: 'missing',
    moved: false,
  },
]
const COMPARISON = {
  slug: 'HT-13',
  tablet: 'HT 13',
  width: 1000,
  height: 500,
  image_url: '/tablets/HT-13/image',
  versions: [
    { key: 'scholar', kind: 'scholar', box_count: 2 },
    { key: 'copy:4', kind: 'copy', owner: 'anouk', mine: false, version: 7, box_count: 3 },
    {
      key: 'copy:9',
      kind: 'copy',
      owner: 'dev',
      mine: true,
      title: 'Mine',
      version: 2,
      box_count: 3,
    },
  ],
  clusters: PLACES,
  agreement: [],
}

describe('merge defaults', () => {
  it("keeps the majority sign, the scholars' box among equals, else the earliest version's", () => {
    expect(defaultPick(PLACES[0], KEYS)).toBe('scholar') // all agree: the scholars' box
    expect(defaultPick(PLACES[1], KEYS)).toBe('copy:4') // AB02 twice beats the scholars' AB01
    expect(defaultPick(PLACES[2], KEYS)).toBe('copy:4') // a tie between two copies: the earlier one
    const tie = { members: { scholar: at(0, 'AB01'), 'copy:4': at(0, 'AB02') } }
    expect(defaultPick(tie, KEYS)).toBe('scholar') // a tie the scholars are in: theirs
    expect(defaultPick({ members: {} }, KEYS)).toBe(null)
  })

  it('takes every box from one version where it has one', () => {
    expect(majorityPicks(PLACES, KEYS)).toEqual(['scholar', 'copy:4', 'copy:4'])
    expect(takeAllFrom(PLACES, ['scholar', 'copy:4', null], 'scholar')).toEqual([
      'scholar',
      'scholar',
      null,
    ])
  })
})

describe('Merge page', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    forgetSession()
    vi.unstubAllGlobals()
  })

  const json = (body, status = 200) =>
    Promise.resolve({ ok: status < 400, status, json: async () => body })

  function serve(merge = () => json({ id: 31 }, 201)) {
    const fetch = vi.fn((url, options = {}) => {
      if (url === '/api/users/me')
        return json({ user: { id: 7, username: 'dev', email: 'd@x.co' }, csrf_token: 'csrf' })
      if (url.startsWith('/api/tablets/HT-13/compare')) return json(COMPARISON)
      if (url === '/api/corrections/catalogue') return json([])
      if (url === '/api/box-sets/merge' && options.method === 'POST') return merge(options)
      return json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  async function render() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/tablets/:slug/merge', component: MergeView },
        { path: '/box-sets/:id', component: { template: '<p>Editor</p>' } },
      ],
    })
    await router.push('/tablets/HT-13/merge?v=scholar&v=copy:4&v=copy:9')
    await router.isReady()
    wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    return router
  }

  it('lists the differing places with the majority chosen, then creates the edition', async () => {
    const fetch = serve()
    const router = await render()
    expect(wrapper.get('[data-testid="merge-title"]').element.value).toBe('Edition of HT 13')
    expect(wrapper.get('[data-testid="merge-summary"]').text()).toBe('3 of 3 places kept')
    const places = wrapper.findAll('[data-testid="merge-place"]')
    expect(places).toHaveLength(2) // the place where all agree needs no choice
    const options = places[0].findAll('[data-testid="merge-option"]')
    expect(options.map((option) => option.text())).toEqual([
      "AB01 (x)Scholars' boxes",
      "AB02 (x)anouk's copy",
      'AB02 (x)Your copy: Mine',
    ])
    expect(options[1].get('input').element.checked).toBe(true)
    expect(options[0].findAll('[data-testid="box-crop"]')).toHaveLength(1)
    await options[0].get('input').setValue(true) // keep the scholars' AB01 instead
    await places[1].get('[data-testid="merge-leave-out"] input').setValue(true)
    expect(wrapper.get('[data-testid="merge-summary"]').text()).toBe('2 of 3 places kept')
    await wrapper.get('[data-testid="merge-title"]').setValue('  Agreed  ')
    await wrapper.get('[data-testid="create-edition"]').trigger('click')
    await flushPromises()
    const [, options2] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/box-sets/merge' && o?.method === 'POST',
    )
    expect(options2.headers['X-CSRF-Token']).toBe('csrf')
    expect(JSON.parse(options2.body)).toEqual({
      tablet: 'HT-13',
      title: 'Agreed',
      sources: [{ key: 'scholar' }, { key: 'copy:4', version: 7 }, { key: 'copy:9', version: 2 }],
      picks: ['scholar', 'scholar', null],
    })
    expect(router.currentRoute.value.path).toBe('/box-sets/31')
  })

  it('applies bulk choices and shows every place on request', async () => {
    serve()
    await render()
    await wrapper.get('[data-testid="take-from"]').setValue('copy:9')
    await wrapper.get('[data-testid="take-all"]').trigger('click')
    const places = wrapper.findAll('[data-testid="merge-place"]')
    expect(places[0].findAll('[data-testid="merge-option"]')[2].get('input').element.checked).toBe(
      true,
    )
    expect(places[1].findAll('[data-testid="merge-option"]')[1].get('input').element.checked).toBe(
      true,
    )
    await wrapper.get('[data-testid="majority"]').trigger('click')
    expect(
      wrapper
        .findAll('[data-testid="merge-place"]')[0]
        .findAll('[data-testid="merge-option"]')[1]
        .get('input').element.checked,
    ).toBe(true)
    await wrapper.get('[data-testid="only-differences"]').setValue(false)
    expect(wrapper.findAll('[data-testid="merge-place"]')).toHaveLength(3)
  })

  it('offers a reload when a version changed meanwhile', async () => {
    serve(() =>
      json(
        { detail: "anouk's copy changed since you opened the merge. Reload to see the changes." },
        409,
      ),
    )
    await render()
    await wrapper.get('[data-testid="create-edition"]').trigger('click')
    await flushPromises()
    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain("anouk's copy changed")
    expect(alert.get('button').text()).toBe('Reload')
  })
})
