import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import EditionView from '../views/EditionView.vue'

const RELEASE = {
  id: 9,
  edition_id: 4,
  number: 2,
  tablet: 'HT-13',
  title: 'Agreed',
  notes: null,
  owner: 'anouk',
  version: 5,
  width: 1000,
  height: 500,
  image_url: '/tablets/HT-13/image',
  created_at: '2026-11-25T09:00:00',
  boxes: [],
  merged_from: [],
  contributors: ['anouk', 'dev'],
  reading: { signs: [], lines: [], formulas: [], summary: '', symbol_interpretation: 'ku-ro' },
  citation:
    'anouk, dev. Agreed: an edition of HT 13, release 2. ASE Group 3 Linear A workbench, 25 November 2026. /editions/9. Drawings and transcriptions: … CC BY-NC-SA 4.0.',
}

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

async function render() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) =>
      url === '/api/editions/9'
        ? { ok: true, status: 200, json: async () => RELEASE }
        : { ok: false, status: 404, json: async () => ({ detail: 'Not found.' }) },
    ),
  )
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/editions/:id', component: EditionView },
      { path: '/tablets/:slug?', component: { template: '<p />' } },
    ],
  })
  await router.push('/editions/9')
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
}

describe('Citing and exporting a release', () => {
  it("shows the citation with this site's permalink and copies it", async () => {
    const writeText = vi.fn(async () => {})
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await render()
    const citation = wrapper.get('[data-testid="citation"]').text()
    expect(citation).toContain(`${window.location.origin}/editions/9.`)
    expect(citation.startsWith('anouk, dev. Agreed: an edition of HT 13, release 2.')).toBe(true)
    await wrapper.get('[data-testid="copy-citation"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(citation)
    expect(wrapper.get('[data-testid="copy-citation"]').text()).toBe('Copied')
  })

  it('offers each format to download', async () => {
    await render()
    const links = ['xml', 'svg', 'png', 'csv', 'json'].map((ext) =>
      wrapper.get(`[data-testid="export-${ext}"]`),
    )
    expect(links.map((link) => link.attributes('href'))).toEqual(
      ['xml', 'svg', 'png', 'csv', 'json'].map((ext) => `/api/editions/9/export.${ext}`),
    )
    expect(links.every((link) => link.attributes('download') !== undefined)).toBe(true)
    expect(links[0].text()).toBe('TEI-EpiDoc')
  })
})
