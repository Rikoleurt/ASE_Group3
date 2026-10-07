import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabletReadingView from '../views/TabletReadingView.vue'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

const reading = {
  id: 'HT 13',
  site: 'Haghia Triada',
  period: 'LM IB',
  scribe: 'HT Scribe 8',
  url: 'https://lineara.eu/documents/HT-13/',
  lines: [
    { number: 2, tokens: [
      { kind: 'sign', text: 're' }, { kind: 'sign', text: 'za' }, { kind: 'number', text: '5' },
      { kind: 'damage', text: '[ ]' }, { kind: 'fraction', text: 'J', value: '1/2' },
    ] },
    { number: 8, tokens: [{ kind: 'sign', text: 'ku' }, { kind: 'sign', text: 'ro' }, { kind: 'number', text: '130' }] },
  ],
  sections: [{
    entries: [
      { line: 2, word: 're-za', quantity: { value: '11/2', damaged: true } },
      { line: 4, word: 'te-ki', quantity: { value: '251/2', damaged: false } },
    ],
    total: { line: 8, marker: 'ku-ro', quantity: { integer: 130, value: '261/2' } },
    integer_sum: 130,
    entries_value: '131',
    residual: '-1/2',
    verdict: 'OVERFULL',
    means: 'Entries exceed an intact total; a break cannot subtract.',
  }],
  upstream_arithmetic: { status: 'balances', detail: 'integers balance 130 = 130' },
  credit: { licence: 'CC BY-NC-SA 4.0', url: 'https://creativecommons.org/licenses/by-nc-sa/4.0/', text: 'From SigLA.' },
}

const fractionSigns = {
  available: true,
  references: 306,
  signs: [
    { position: 9, transcribed: { label: 'J' }, correct: true, image: '/tablets/HT-13/signs/9.png',
      guesses: [{ label: 'J' }, { label: 'D' }, { label: 'B' }] },
    { position: 14, transcribed: { label: 'J' }, correct: false, image: '/tablets/HT-13/signs/14.png',
      guesses: [{ label: 'D' }, { label: 'J' }] },
  ],
}

function api({ readingOk = true, fractions = fractionSigns } = {}) {
  return vi.fn(async (url) => {
    if (url.endsWith('/reading')) return readingOk ? { ok: true, json: async () => reading } : { ok: false, status: 503 }
    if (url.endsWith('/fraction-signs')) return fractions ? { ok: true, json: async () => fractions } : { ok: false, status: 500 }
    throw new Error(`unexpected ${url}`)
  })
}

async function render() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tablet-reading', component: TabletReadingView },
      { path: '/tablet-demo', component: { template: '<h1>Demo</h1>' } },
    ],
  })
  await router.push('/tablet-reading')
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return router
}

describe('Tablet reading', () => {
  it('shows the transcription with numbers, fractions and breaks', async () => {
    const fetch = api()
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(fetch).toHaveBeenCalledWith('/api/tablets/HT-13/reading')
    expect(wrapper.get('h1').text()).toBe('HT 13')
    expect(wrapper.text()).toContain('Haghia Triada · LM IB · HT Scribe 8')
    const lines = wrapper.findAll('[data-testid="line"]')
    const tokens = lines[0].findAll('span span').map((t) => t.text())
    expect(tokens).toEqual(['re', 'za', '5', '[ ]', 'J'])
    expect(lines[0].find('[title="J = ½"]').exists()).toBe(true)
  })

  it('explains the arithmetic check, including what the integer-only check misses', async () => {
    vi.stubGlobal('fetch', api())
    await render()
    expect(wrapper.text()).toContain('The entries add up to 131; the scribe\'s total is 130½.')
    expect(wrapper.get('[data-testid="verdict"]').text()).toBe('Does not balance (off by −½)')
    expect(wrapper.text()).toContain('Line 2 is broken')
    expect(wrapper.text()).toContain('it checks whole numbers only')
    expect(wrapper.text()).toContain('5½ (broken)')
  })

  it('shows shape matches against the transcription', async () => {
    vi.stubGlobal('fetch', api())
    await render()
    const signs = wrapper.findAll('[data-testid="fraction-sign"]')
    expect(signs).toHaveLength(2)
    expect(signs[0].get('img').attributes('src')).toBe('/api/tablets/HT-13/signs/9.png')
    expect(signs[0].text()).toContain('Best match: J')
    expect(signs[0].text()).toContain('✓ matches transcription (J)')
    expect(signs[1].text()).toContain('✗ differs from transcription (J)')
    expect(wrapper.text()).toContain('306 drawings')
  })

  it('explains how to enable shape matching when drawings are not downloaded', async () => {
    vi.stubGlobal('fetch', api({ fractions: { available: false, references: 0, signs: [] } }))
    await render()
    expect(wrapper.text()).toContain('python -m la.cli images')
    expect(wrapper.findAll('[data-testid="fraction-sign"]')).toHaveLength(0)
  })

  it('reports a backend that cannot read the tablet', async () => {
    vi.stubGlobal('fetch', api({ readingOk: false }))
    await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('could not be loaded')
    expect(wrapper.find('[data-testid="verdict"]').exists()).toBe(false)
  })

  it('links back to sign detection', async () => {
    vi.stubGlobal('fetch', api())
    const router = await render()
    await wrapper.get('a[href="/tablet-demo"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/tablet-demo')
  })
})
