import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import DiscussionLinks from '../components/DiscussionLinks.vue'
import MentionText from '../components/mentions/MentionText.vue'
import { parseMentionTokens } from '../components/mentions/mentionSyntax'
import DiscussionView from '../views/DiscussionView.vue'
import { acceptSession, forgetSession } from '../state/session'
import { analysis } from './analysisFixture'

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body })
const session = { user: { id: 7, username: 'owner', email: 'owner@ase3.com' }, csrf_token: 'csrf' }
const summary = {
  id: 3,
  analysis_id: 12,
  author_id: 7,
  title: 'HT13 discussion',
  author_username: 'owner',
  created_at: '2026-11-10T12:00:00Z',
}

let wrapper

afterEach(() => {
  wrapper?.unmount()
  forgetSession()
  vi.unstubAllGlobals()
})

async function render(path, component) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<p />' } },
      { path: '/community/:id', component: DiscussionView },
      { path: '/tablets/:slug?', component: { template: '<p />' } },
      { path: '/editions/:id', component: { template: '<p />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount(component ?? { template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('glyph and edition mentions', () => {
  it('parses their tokens and links them to their pages', async () => {
    expect(
      parseMentionTokens('@[HT 13 · ka](glyph:HT-13:5) and @[Agreed, release 2](edition:007)').map(
        (t) => t.key,
      ),
    ).toEqual(['glyph:HT-13:5', 'edition:7'])
    await render('/', {
      components: { MentionText },
      template: '<MentionText :body="body" :mentions="mentions" />',
      data: () => ({
        body: 'see @[HT 13 · ka](glyph:HT-13:5) and @[Agreed](edition:7)',
        mentions: [
          {
            token: '@[HT 13 · ka](glyph:HT-13:5)',
            key: 'glyph:HT-13:5',
            kind: 'glyph',
            label: 'HT 13 · ka',
            available: true,
            glyph_tablet: 'HT-13',
            glyph_position: 5,
            image_url: '/api/tablets/HT-13/thumbnail.png?position=5',
          },
          {
            token: '@[Agreed](edition:7)',
            key: 'edition:7',
            kind: 'edition',
            label: 'Agreed, release 2',
            available: true,
            release_id: 7,
          },
        ],
      }),
    })
    expect(wrapper.get('[data-testid="glyph-mention"]').attributes('href')).toBe('/tablets/HT-13')
    expect(wrapper.get('[data-testid="glyph-mention"] img').attributes('src')).toBe(
      '/api/tablets/HT-13/thumbnail.png?position=5',
    )
    expect(wrapper.get('[data-testid="edition-mention"]').attributes('href')).toBe('/editions/7')
  })
})

describe('Discussion links', () => {
  function serve() {
    const fetch = vi.fn((url) => {
      if (url === '/api/community/linked?target=glyph%3AHT-13%3A5') {
        return json({
          target: 'glyph:HT-13:5',
          items: [
            { id: 4, title: 'Is this ka?', author: 'anouk', mentioned_at: '2026-11-25T09:00:00Z' },
          ],
        })
      }
      if (url === '/api/community/discussions?limit=10')
        return json({ items: [summary], parents: [], next_cursor: null })
      return json({ detail: 'Not found.' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  it('lists the discussions that mention a glyph', async () => {
    serve()
    await render('/', {
      components: { DiscussionLinks },
      template: '<DiscussionLinks target="glyph:HT-13:5" label="HT 13 · ka" />',
    })
    const links = wrapper.findAll('[data-testid="linked-discussions"] a')
    expect(links.map((link) => [link.text(), link.attributes('href')])).toEqual([
      ['Is this ka?', '/community/4'],
    ])
    expect(wrapper.find('[data-testid="mention-in"]').exists()).toBe(false) // logged out
  })

  it('opens a chosen discussion with the mention ready to post', async () => {
    serve()
    acceptSession(session)
    const router = await render('/', {
      components: { DiscussionLinks },
      template: '<DiscussionLinks target="glyph:HT-13:5" label="HT 13 · ka" />',
    })
    await wrapper.get('[data-testid="mention-in"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="discussion-choice"] button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/community/3')
    expect(router.currentRoute.value.query).toEqual({
      mention: 'glyph:HT-13:5',
      label: 'HT 13 · ka',
    })
  })

  it('puts the mention in the comment box of the discussion, then drops it from the address', async () => {
    acceptSession(session)
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) =>
        url.endsWith('/comments')
          ? { ok: true, status: 200, json: async () => [] }
          : url === '/api/users/me'
            ? { ok: true, status: 200, json: async () => session }
            : {
                ok: true,
                status: 200,
                json: async () => ({ ...summary, image_url: '/x.png', result: analysis }),
              },
      ),
    )
    const router = await render(
      '/community/3?mention=glyph%3AHT-13%3A5&label=HT%2013%20%C2%B7%20ka',
    )
    await flushPromises()
    expect(wrapper.get('textarea').element.value).toBe('@HT 13 · ka ')
    expect(router.currentRoute.value.fullPath).toBe('/community/3')
  })
})
