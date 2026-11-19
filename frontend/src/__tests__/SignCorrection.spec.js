import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SignCorrection from '../components/analysis/SignCorrection.vue'
import { signs } from './analysisFixture.js'

const catalogue = [
  { sign: 'AB59', name: 'AB59 (ta)', glyph: '\u{1062B}' },
  { sign: 'AB81', name: 'AB81 (ku)', glyph: '\u{10642}' },
]
const sign = { ...signs[0], label: 'AB59 (ta)', crop: 'data:image/png;base64,AAAA' }

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

function render(saved = { ok: true, status: 201, json: async () => ({ id: 1, uncertain: false }) }) {
  const fetch = vi.fn((url) => Promise.resolve(url === '/api/users/me'
    ? { ok: true, json: async () => ({ user: { id: 1 }, csrf_token: 'csrf' }) }
    : saved))
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(SignCorrection, { props: { sign, analysisId: 12, catalogue } })
  return fetch
}

const posted = (fetch) => {
  const [url, options] = fetch.mock.calls.find(([url]) => url !== '/api/users/me')
  return { url, options, body: JSON.parse(options.body) }
}

describe('Sign correction', () => {
  it('shows the predicted label beside its region of the tablet', () => {
    render()
    expect(wrapper.get('[data-testid="correction-crop"]').attributes('src')).toBe(sign.crop)
    expect(wrapper.get('[data-testid="correction-original"]').text()).toContain('AB59 (ta)')
    expect(wrapper.findAll('datalist option').map((option) => option.attributes('value'))).toEqual(['AB59', 'AB81'])
  })

  it('submits a replacement from the catalogue with the CSRF token and confirms it', async () => {
    const fetch = render()
    await wrapper.get('#proposed-sign').setValue('ab81')
    await wrapper.get('#correction-note').setValue('  clearer on the photo  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const { url, options, body } = posted(fetch)
    expect(url).toBe('/api/analysis/12/corrections')
    expect(options.headers['X-CSRF-Token']).toBe('csrf')
    expect(body).toEqual({ sign_id: 1, proposed_sign: 'AB81', note: 'clearer on the photo' })
    expect(wrapper.get('[data-testid="correction-saved"]').text()).toContain('A reviewer will check it')
  })

  it('flags an uncertain sign without proposing a label', async () => {
    const fetch = render({ ok: true, status: 201, json: async () => ({ id: 2, uncertain: true }) })
    await wrapper.findAll('button').find((button) => button.text().startsWith('Not sure')).trigger('click')
    await flushPromises()

    expect(posted(fetch).body).toEqual({ sign_id: 1, uncertain: true, note: null })
    expect(wrapper.get('[data-testid="correction-saved"]').text()).toContain('your flag was saved')
  })

  it('asks for a sign from the list instead of sending anything else', async () => {
    const fetch = render()
    await wrapper.get('#proposed-sign').setValue('not a sign')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetch.mock.calls.some(([url]) => url.includes('/corrections'))).toBe(false)
    expect(wrapper.get('[role="alert"]').text()).toBe('Choose a sign from the list.')
  })

  it('shows the server error and keeps the form', async () => {
    render({ ok: false, status: 422, json: async () => ({ detail: 'This is already the model\'s reading.' }) })
    await wrapper.get('#proposed-sign').setValue('AB59')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('This is already the model\'s reading.')
    expect(wrapper.find('[data-testid="correction-saved"]').exists()).toBe(false)
  })
})
