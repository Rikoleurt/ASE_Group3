import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SignPicker from '../components/signs/SignPicker.vue'
import SignPreview from '../components/signs/SignPreview.vue'
import MentionComposer from '../components/mentions/MentionComposer.vue'
import MentionText from '../components/mentions/MentionText.vue'
import { parseMentionTokens } from '../components/mentions/mentionSyntax'
import { searchSigns } from '../components/signs/signSearch'

const CATALOGUE = [
  {
    sign: 'A301',
    name: 'A301',
    glyph: '\u{10643}',
    reading: null,
    preview_url: '/glyphs/A301/preview.png',
  },
  {
    sign: 'AB01',
    name: 'AB01 (da)',
    glyph: '\u{10600}',
    reading: 'da',
    preview_url: '/glyphs/AB01/preview.png',
  },
  {
    sign: 'AB81',
    name: 'AB81 (ku)',
    glyph: '\u{10642}',
    reading: 'ku',
    preview_url: '/glyphs/AB81/preview.png',
  },
  { sign: 'AB80', name: 'AB80 (ma)', glyph: '\u{10641}', reading: 'ma', preview_url: null },
  {
    sign: 'AB131a',
    name: 'AB131a (VIN)',
    glyph: '\u{1065C}',
    reading: null,
    preview_url: '/glyphs/AB131a/preview.png',
  },
]

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

function serveCatalogue() {
  const fetch = vi.fn(async (url) =>
    url === '/api/corrections/catalogue'
      ? { ok: true, json: async () => CATALOGUE }
      : { ok: false, status: 404, json: async () => ({}) },
  )
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('sign search', () => {
  it('ranks exact readings and numbers first, then prefixes, then names', () => {
    expect(searchSigns(CATALOGUE, 'ku').map((sign) => sign.sign)).toEqual(['AB81'])
    expect(searchSigns(CATALOGUE, '81').map((sign) => sign.sign)).toEqual(['AB81'])
    expect(searchSigns(CATALOGUE, 'ab1').map((sign) => sign.sign)[0]).toBe('AB01') // AB1 is AB01
    expect(searchSigns(CATALOGUE, 'm').map((sign) => sign.sign)).toEqual(['AB80'])
    expect(searchSigns(CATALOGUE, 'vin').map((sign) => sign.sign)).toEqual(['AB131a'])
    expect(searchSigns(CATALOGUE, 'AB').length).toBe(4)
    expect(searchSigns(CATALOGUE, '  ')).toEqual([])
    expect(searchSigns(CATALOGUE, 'a', 2)).toHaveLength(2)
  })
})

describe('Sign picker', () => {
  it('shows matching signs with their drawings and picks with the keyboard', async () => {
    const fetch = serveCatalogue()
    wrapper = mount(SignPicker)
    await flushPromises()
    expect(fetch).toHaveBeenCalledWith('/api/corrections/catalogue')
    const input = wrapper.get('#sign-search')
    await input.setValue('a')
    const options = wrapper.findAll('[role="option"]')
    expect(options.length).toBeGreaterThan(1)
    expect(options[0].get('img').attributes('src')).toMatch(/^\/api\/glyphs\/.+\/preview\.png$/)
    expect(input.attributes('aria-activedescendant')).toBe('sign-search-matches-0')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe('sign-search-matches-1')
    const second = wrapper.findAll('[role="option"]')[1].text()
    await input.trigger('keydown', { key: 'Enter' })
    expect(second).toContain(wrapper.emitted('pick')[0][0])
    expect(input.element.value).toBe('') // cleared after picking
  })

  it("shows the model's guesses with drawings and marks the chosen one", async () => {
    serveCatalogue()
    wrapper = mount(SignPicker, {
      props: {
        selected: 'AB81',
        candidates: [
          { sign: 'AB81', label: 'AB81 (ku)', probability: 78 },
          { sign: 'AB80', label: 'AB80 (ma)', probability: 12 },
        ],
      },
    })
    await flushPromises()
    const guesses = wrapper.findAll('[data-testid="candidate"]')
    expect(guesses.map((guess) => guess.attributes('aria-pressed'))).toEqual(['true', 'false'])
    expect(guesses[0].get('img').attributes('src')).toBe('/api/glyphs/AB81/preview.png')
    expect(guesses[1].find('img').exists()).toBe(false) // AB80 has no picture: its character instead
    expect(guesses[1].get('[data-testid="sign-preview"]').text()).toBe('\u{10641}')
    await guesses[1].trigger('click')
    expect(wrapper.emitted('pick')).toEqual([['AB80']])
  })

  it('says when nothing matches, and works without a catalogue', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })),
    )
    wrapper = mount(SignPicker)
    await flushPromises()
    await wrapper.get('#sign-search').setValue('zz')
    expect(wrapper.text()).toContain('No sign matches.')
  })
})

describe('Sign preview', () => {
  it('falls back to the character when the picture fails to load', async () => {
    wrapper = mount(SignPreview, {
      props: { sign: 'AB81', glyph: '\u{10642}', previewUrl: '/glyphs/AB81/preview.png' },
    })
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('\u{10642}')
  })
})

describe('Sign mentions', () => {
  it('parses sign tokens without treating the sign number as a number', () => {
    expect(
      parseMentionTokens('see @[AB81 (ku)](sign:AB81) and @[x](user:007)').map(
        (token) => token.key,
      ),
    ).toEqual(['sign:AB81', 'user:7'])
  })

  it('offers catalogue signs with their drawings in the Signs tab', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    onTestFinished(() => vi.useRealTimers())
    const fetch = serveCatalogue()
    wrapper = mount(MentionComposer, { props: { discussionId: 4 } })
    expect(fetch).not.toHaveBeenCalledWith('/api/corrections/catalogue') // only when the Signs tab opens
    await wrapper.get('textarea').setValue('@ku')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Signs')
      .trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(250) // the composer waits for typing to pause
    await flushPromises()
    const option = wrapper.get('[role="option"]')
    expect(option.text()).toContain('@AB81 (ku)')
    expect(option.get('img').attributes('src')).toBe('/api/glyphs/AB81/preview.png')
    await option.trigger('click')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toBe('@[AB81 (ku)](sign:AB81) ')
  })

  it('shows a mentioned sign with its picture', () => {
    wrapper = mount(MentionText, {
      props: {
        body: 'is this @[AB81 (ku)](sign:AB81)?',
        mentions: [
          {
            token: '@[AB81 (ku)](sign:AB81)',
            key: 'sign:AB81',
            kind: 'sign',
            label: 'AB81 (ku)',
            available: true,
            sign_code: 'AB81',
            image_url: '/api/glyphs/AB81/preview.png',
          },
        ],
      },
      global: { stubs: { RouterLink: true } },
    })
    const chip = wrapper.get('[data-testid="sign-mention"]')
    expect(chip.text()).toBe('@AB81 (ku)')
    expect(chip.get('img').attributes('src')).toBe('/api/glyphs/AB81/preview.png')
  })
})
