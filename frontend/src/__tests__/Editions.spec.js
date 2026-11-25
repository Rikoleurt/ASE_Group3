import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import EditionsPanel from '../components/versions/EditionsPanel.vue'
import ReleasePanel from '../components/versions/ReleasePanel.vue'
import VotingRightsEditor from '../components/admin/VotingRightsEditor.vue'
import EditionView from '../views/EditionView.vue'
import { forgetSession, loadSession } from '../state/session'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const release = (id, extra = {}) => ({
  id,
  edition_id: 4,
  number: 1,
  title: null,
  notes: null,
  owner: 'anouk',
  box_count: 27,
  created_at: '2026-11-25T09:00:00',
  votes: 0,
  reviewer_votes: 0,
  accepted: false,
  ...extra,
})
const PAGE = {
  slug: 'HT-13',
  items: [
    release(1, { title: 'Agreed', votes: 2, reviewer_votes: 1, accepted: true }),
    release(2, { owner: 'ahmed', notes: 'Fixed line 2' }),
  ],
  accepted_release_id: 1,
  override: null,
  my_vote: 1,
  voting: { allowed: true, reason: null },
}
const SESSION = (admin = false) => ({
  user: { id: 7, username: 'dev', email: 'd@x.co' },
  csrf_token: 'csrf',
  admin,
})

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

const router = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<p />' } },
      { path: '/editions/:id', component: EditionView },
      { path: '/tablets/:slug?', component: { template: '<p />' } },
    ],
  })

async function mountWith(component, props, { routes } = {}) {
  await loadSession().catch(() => {})
  const r = router()
  await r.push(routes ?? '/')
  await r.isReady()
  wrapper = mount(component, { props, global: { plugins: [r] } })
  await flushPromises()
  return r
}

function serve(handlers, admin = false) {
  const fetch = vi.fn((url, options = {}) => {
    if (url === '/api/users/me') return json(SESSION(admin))
    const key = `${options.method ?? 'GET'} ${url}`
    return handlers[key] ? handlers[key](options) : json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('Editions panel', () => {
  it('shows the releases with their backers and lets you change your vote', async () => {
    const fetch = serve({
      'GET /api/tablets/HT-13/editions': () => json(PAGE),
      'PUT /api/tablets/HT-13/vote': () => json({ ...PAGE, my_vote: 2 }),
      'DELETE /api/tablets/HT-13/vote': () => json({ ...PAGE, my_vote: null }),
    })
    await mountWith(EditionsPanel, { slug: 'HT-13' })
    const rows = wrapper.findAll('[data-testid="edition"]')
    expect(rows[0].text()).toContain('Community edition')
    expect(rows[0].text()).toContain('Agreed, release 1')
    expect(rows[0].text()).toContain('2 backers, 1 of them reviewer')
    expect(rows[1].text()).toContain("ahmed's edition, release 1")
    expect(rows[1].text()).toContain('Fixed line 2')
    expect(rows[0].get('[data-testid="withdraw"]').text()).toContain('You back this')
    await rows[1].get('[data-testid="back"]').trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/tablets/HT-13/vote' && o?.method === 'PUT',
    )
    expect(JSON.parse(options.body)).toEqual({ release_id: 2 })
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(
      wrapper.findAll('[data-testid="edition"]')[1].find('[data-testid="withdraw"]').exists(),
    ).toBe(true)
  })

  it('says why you cannot vote and shows an admin override with its reason', async () => {
    serve({
      'GET /api/tablets/HT-13/editions': () =>
        json({
          ...PAGE,
          my_vote: null,
          voting: { allowed: false, reason: 'New accounts can vote one day after they are made.' },
          override: {
            release_id: 2,
            admin: 'boss',
            comment: 'Matches the new photographs',
            created_at: '2026-11-25T10:00:00',
          },
        }),
    })
    await mountWith(EditionsPanel, { slug: 'HT-13' })
    expect(wrapper.get('[data-testid="voting-blocked"]').text()).toBe(
      'New accounts can vote one day after they are made.',
    )
    expect(wrapper.find('[data-testid="back"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="override"]').text()).toContain('Chosen by an admin (boss')
    expect(wrapper.get('[data-testid="override"]').text()).toContain(
      '“Matches the new photographs”',
    )
    expect(wrapper.find('[data-testid="choose"]').exists()).toBe(false) // not an admin
  })

  it('lets an admin choose an edition over the vote only with a reason', async () => {
    const fetch = serve(
      {
        'GET /api/tablets/HT-13/editions': () => json(PAGE),
        'PUT /api/tablets/HT-13/edition-override': () =>
          json({
            ...PAGE,
            override: {
              release_id: 2,
              admin: 'dev',
              comment: 'x',
              created_at: '2026-11-25T10:00:00',
            },
          }),
      },
      true,
    )
    await mountWith(EditionsPanel, { slug: 'HT-13' })
    await wrapper.findAll('[data-testid="choose"]')[1].trigger('click')
    const confirm = wrapper.get('[data-testid="choose-confirm"]')
    await wrapper.get('#choose-2').setValue('too short')
    expect(confirm.attributes('disabled')).toBeDefined()
    await wrapper.get('#choose-2').setValue('Matches the new photographs of the tablet')
    expect(confirm.attributes('disabled')).toBeUndefined()
    await confirm.trigger('submit')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url]) => url === '/api/tablets/HT-13/edition-override',
    )
    expect(JSON.parse(options.body)).toEqual({
      release_id: 2,
      comment: 'Matches the new photographs of the tablet',
    })
    expect(wrapper.find('[data-testid="override"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="clear-override"]').exists()).toBe(true)
  })

  it('stays hidden when the editions cannot be loaded', async () => {
    serve({})
    await mountWith(EditionsPanel, { slug: 'HT-13' })
    expect(wrapper.find('[data-testid="editions"]').exists()).toBe(false)
  })
})

describe('Release panel', () => {
  it('releases with notes, but not with unsaved changes', async () => {
    const fetch = serve({
      'GET /api/box-sets/4/releases': () => json([]),
      'POST /api/box-sets/4/releases': () => json({ id: 9, number: 1 }, 201),
    })
    await mountWith(ReleasePanel, { setId: 4, canRelease: true, dirty: true })
    await wrapper.get('[data-testid="release-open"]').trigger('click')
    expect(wrapper.get('[data-testid="release-confirm"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('Save your changes first')
    await wrapper.setProps({ dirty: false })
    await wrapper.get('#release-notes').setValue('First agreed reading')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/box-sets/4/releases' && o?.method === 'POST',
    )
    expect(JSON.parse(options.body)).toEqual({ notes: 'First agreed reading' })
    expect(wrapper.emitted('released')[0][0]).toEqual({ id: 9, number: 1 })
  })

  it('lists the releases, and offers no release button to viewers', async () => {
    serve({
      'GET /api/box-sets/4/releases': () =>
        json([release(9, { number: 2, notes: 'Line 2 fixed' }), release(8)]),
    })
    await mountWith(ReleasePanel, { setId: 4, canRelease: false })
    expect(
      wrapper.findAll('[data-testid="release"]').map((row) => row.text().split(' · ')[0]),
    ).toEqual(['Release 2', 'Release 1'])
    expect(wrapper.find('[data-testid="release-open"]').exists()).toBe(false)
  })
})

describe('Release page', () => {
  it('shows the snapshot with its reading, contributors and sources', async () => {
    serve({
      'GET /api/editions/9': () =>
        json({
          id: 9,
          edition_id: 4,
          number: 2,
          tablet: 'HT-13',
          title: null,
          notes: 'Line 2 fixed',
          owner: 'anouk',
          version: 5,
          width: 1000,
          height: 500,
          image_url: '/tablets/HT-13/image',
          created_at: '2026-11-25T09:00:00',
          boxes: [],
          merged_from: [
            { key: 'scholar', kind: 'scholar' },
            { key: 'copy:3', kind: 'copy', owner: 'ahmed', title: 'Mine' },
          ],
          contributors: ['ahmed', 'anouk'],
          reading: {
            signs: [],
            lines: [],
            formulas: [],
            summary: 'No signs found',
            symbol_interpretation: 'ka-ro',
          },
        }),
    })
    await mountWith({ template: '<RouterView />' }, {}, { routes: '/editions/9' })
    expect(wrapper.get('h1').text()).toBe("anouk's edition of HT 13")
    expect(wrapper.get('[data-testid="release-meta"]').text()).toContain('Release 2')
    expect(wrapper.get('[data-testid="release-contributors"]').text()).toBe(
      'Contributors: ahmed, anouk',
    )
    expect(wrapper.text()).toContain("Merged from the scholars' boxes, ahmed's copy “Mine”.")
    expect(wrapper.get('[data-testid="release-reading"]').text()).toContain('ka-ro')
  })

  it('explains a missing release', async () => {
    serve({ 'GET /api/editions/9': () => json({ detail: 'Release not found.' }, 404) })
    await mountWith({ template: '<RouterView />' }, {}, { routes: '/editions/9' })
    expect(wrapper.get('[role="alert"]').text()).toBe('Release not found.')
  })
})

describe('Voting rights editor', () => {
  it('removes voting rights only with a reason', async () => {
    const fetch = serve(
      {
        'GET /api/admin/users/9/voting': () =>
          json({ can_vote: true, reason: null, changed_by: null, changed_at: null }),
        'PUT /api/admin/users/9/voting': () =>
          json({
            can_vote: false,
            reason: 'Voting from several accounts',
            changed_by: 'dev',
            changed_at: '2026-11-25T11:00:00',
          }),
      },
      true,
    )
    await mountWith(VotingRightsEditor, { user: { id: 9, username: 'ahmed' } })
    expect(wrapper.get('[data-testid="voting-status"]').text()).toBe('Can vote on editions.')
    const change = wrapper.get('[data-testid="voting-change"]')
    expect(change.text()).toBe('Remove voting rights')
    expect(change.attributes('disabled')).toBeDefined()
    await wrapper.get('textarea').setValue('Voting from several accounts')
    await change.trigger('click')
    await flushPromises()
    const [, options] = fetch.mock.calls.find(
      ([url, o]) => url === '/api/admin/users/9/voting' && o?.method === 'PUT',
    )
    expect(JSON.parse(options.body)).toEqual({
      can_vote: false,
      reason: 'Voting from several accounts',
    })
    expect(wrapper.get('[data-testid="voting-status"]').text()).toContain('Cannot vote')
    expect(wrapper.get('[data-testid="voting-status"]').text()).toContain(
      'Last change by dev: “Voting from several accounts”',
    )
    expect(wrapper.get('[data-testid="voting-change"]').text()).toBe('Restore voting rights')
  })
})
