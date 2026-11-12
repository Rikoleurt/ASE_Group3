import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import GlyphGrid from '../components/benchmarks/GlyphGrid.vue'

const row = (over) => ({ n: 4, id_correct: 1, e2e_n: 4, e2e_correct: 1, role: 'logogram', bucket: '2-4', confused_with: [], ...over })

describe('GlyphGrid', () => {
  it('shows a corpus drawing for a sign with no Unicode character, and the ID when it cannot load', async () => {
    const wrapper = mount(GlyphGrid, {
      props: {
        mode: 'id',
        signs: [
          row({ sign: 'A517', glyph: null, drawing: { tablet: 'HT-120', position: 13 } }),
          row({ sign: 'AB302', glyph: null, drawing: null }),
          row({ sign: 'AB01', glyph: 'A' }),
        ],
      },
    })
    const img = wrapper.get('[data-sign="A517"] img')
    expect(img.attributes('src')).toBe('/api/tablets/HT-120/signs/13.png')
    expect(img.attributes('alt')).toBe('') // the tile's label names the sign
    expect(wrapper.get('[data-sign="AB302"]').text()).toBe('AB302')
    expect(wrapper.get('[data-sign="AB01"]').text()).toBe('A')
    await img.trigger('error')
    expect(wrapper.find('[data-sign="A517"] img').exists()).toBe(false)
    expect(wrapper.get('[data-sign="A517"]').text()).toBe('A517')
  })
})
