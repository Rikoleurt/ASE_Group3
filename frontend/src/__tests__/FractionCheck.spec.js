import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import FractionCheck from '../components/analysis/FractionCheck.vue'
import FractionEquation from '../components/analysis/FractionEquation.vue'
import { DEFINITIONS, pretty } from '../components/analysis/definitions.js'
import { analysis, mismatch } from './analysisFixture.js'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

function render(overrides = {}) {
  wrapper = mount(FractionCheck, { props: { analysis: { ...analysis, ...overrides } } })
  return wrapper
}

function equation(formula, markerGlyphs = '\u{10642}\u{10601}') {
  wrapper = mount(FractionEquation, { props: { formula, markerGlyphs } })
  return wrapper
}

describe('Fraction check', () => {
  it('shows the colour key with how many signs have each colour', () => {
    render()
    const key = wrapper.get('[aria-label="Box colours"]')
    expect(key.findAll('[tabindex="0"]').map((label) => label.text())).toEqual([
      'Syllable', 'Logogram', 'Fraction', 'KU-RO (total)', 'Fraction formula', // no "Other": none on this tablet
    ])
    expect(key.findAll('[data-testid="key-count"]').map((count) => count.text())).toEqual(['(2)', '(1)', '(3)', '(2)'])
  })

  it('explains each colour-key label when it is hovered or focused', () => {
    render()
    const tips = wrapper.findAll('[role="tooltip"]')
    expect(tips.map((tip) => tip.text())).toEqual([
      DEFINITIONS.syllabogram, DEFINITIONS.logogram, DEFINITIONS.fraction, DEFINITIONS.total, DEFINITIONS.formula,
    ])
    const label = wrapper.get('[aria-describedby]')
    expect(label.attributes('tabindex')).toBe('0') // reachable by keyboard
    expect(wrapper.get(`#${label.attributes('aria-describedby')}`).text()).toBe(DEFINITIONS.syllabogram)
  })

  it('writes the tablet out in Linear A, line by line, with readings', () => {
    render()
    const lines = wrapper.get('[data-testid="tablet-text"]').findAll(':scope > li')
    expect(lines).toHaveLength(4)
    const cells = lines[2].findAll('[data-testid="glyph-cell"]')
    expect(cells.map((cell) => cell.text())).toEqual(['\u{10642}ku', '\u{10601}ro', '\u{10746}J'])
    expect(lines[2].text()).toContain('ku-ro J — total 1/2')
    expect(lines[3].text()).toContain('□') // N800 has no Unicode character
    expect(lines[3].text()).not.toContain('—') // nothing glossed
  })

  it('shows the balance as an equation, then the verdict', () => {
    render()
    const formula = wrapper.get('[data-testid="formula"]')
    expect(formula.get('h3').text()).toBe('KU-RO total, lines 1–3')
    expect(formula.get('[data-testid="equation-check"]').text()).toBe('1 ≠ ½: off by ½')
    const verdict = formula.get('[data-testid="verdict"]')
    expect(verdict.text()).toBe('The fractions do not balance: off by ½')
    expect(verdict.attributes('style')).toContain('animation-delay: 2800ms, 3250ms') // after 3 terms + 4 pieces
    expect(formula.findAll('[data-testid="steps"] li').map((step) => step.text())).toEqual(mismatch.steps)
    expect(formula.text()).toContain('the check is on fractions only')
  })

  it('shows a balanced formula in the balance colour', () => {
    render({ formulas: [{ ...mismatch, verdict: 'balances', difference: '0' }] })
    const verdict = wrapper.get('[data-testid="verdict"]')
    expect(verdict.text()).toBe('The fractions balance')
    expect(verdict.attributes('style')).toContain('var(--color-confidence-high)')
  })

  it('lists totals before loose fractions, which get no verdict', () => {
    const group = { ...mismatch, kind: 'group', lines: [4], verdict: null, total: [], marker_ids: [] }
    render({ formulas: [group, mismatch] })
    const titles = wrapper.findAll('[data-testid="formula"] h3').map((title) => title.text())
    expect(titles).toEqual(['KU-RO total, lines 1–3', 'Fractions on line 5'])
    expect(wrapper.findAll('[data-testid="verdict"]')).toHaveLength(1)
  })

  it('says so when there is no formula', () => {
    render({ formulas: [] })
    expect(wrapper.get('[data-testid="no-formula"]').text()).toContain('No fraction signs or KU-RO total')
  })

  it('stays hidden when no signs were found', () => {
    render({ signs: [], formulas: [] })
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('shows everything at once for viewers who prefer less motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    render()
    expect(wrapper.get('section').classes()).toContain('still')
  })
})

describe('Fraction equation', () => {
  it('writes the entries and the total as glyphs with their values', () => {
    equation(mismatch)
    const entries = wrapper.get('[data-testid="equation-entries"]')
    expect(entries.findAll('[data-testid="term"]').map((term) => term.text())).toEqual(['\u{10746}J = ½', '\u{10746}J = ½'])
    expect(entries.text().replace(/\s+/g, ' ')).toContain('= ½ + ½ = 1')
    const total = wrapper.get('[data-testid="equation-total"]')
    expect(total.text()).toContain('\u{10642}\u{10601}KU-RO')
    expect(total.text()).toContain('= ½')
  })

  it.each([
    [{ verdict: 'balances', carried: 0, entries_sum: '3/4', total_value: '3/4' }, '¾ = ¾'],
    [{ verdict: 'balances', carried: 1, entries_sum: '1', total_value: '0' }, '1 = 0 + 1 whole'],
    [{ verdict: 'incomplete', entries_sum: '?', total_value: '1/2' }, '? ? ½: a sign has no agreed value'],
  ])('states the check for %o', (change, shown) => {
    equation({ ...mismatch, ...change })
    expect(wrapper.get('[data-testid="equation-check"]').text()).toBe(shown)
  })

  it('has no total or check for loose fractions', () => {
    equation({ ...mismatch, kind: 'group', verdict: null, total: [], entries_sum: '1' })
    expect(wrapper.text()).toContain('Sum')
    expect(wrapper.find('[data-testid="equation-total"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="equation-check"]').exists()).toBe(false)
  })

  it('names a grand total', () => {
    equation({ ...mismatch, kind: 'grand_total' })
    expect(wrapper.get('[data-testid="equation-total"]').text()).toContain('PO-TO-KU-RO')
  })
})

describe('Fractions shown', () => {
  it.each([
    ['1/2', '½'], ['3/4', '¾'], ['1 1/2', '1½'], ['1/16', '1/16'], ['2 1/16', '2 1/16'], ['1', '1'], ['?', '?'],
  ])('%s as %s', (value, shown) => {
    expect(pretty(value)).toBe(shown)
  })
})
