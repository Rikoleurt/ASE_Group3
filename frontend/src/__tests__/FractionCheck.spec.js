import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import FractionCheck from '../components/analysis/FractionCheck.vue'
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

describe('Fraction check', () => {
  it('shows the colour key with how many signs have each colour', () => {
    render()
    const key = wrapper.get('[aria-label="Box colours"]').findAll('li').filter((item) => item.isVisible())
    expect(key.map((item) => item.text())).toEqual([
      'Syllable (2)', 'Logogram (1)', 'Fraction (3)', 'KU-RO (total) (2)', 'Fraction formula',
    ])
  })

  it('reveals the working step by step, then the verdict', () => {
    render()
    const formula = wrapper.get('[data-testid="formula"]')
    expect(formula.get('h3').text()).toBe('KU-RO total, lines 1–3')
    const steps = formula.findAll('li')
    expect(steps.map((step) => step.text())).toEqual(mismatch.steps)
    expect(steps.map((step) => step.attributes('style'))).toEqual([
      'animation-delay: 0ms;', 'animation-delay: 600ms;', 'animation-delay: 1200ms;', 'animation-delay: 1800ms;',
    ])
    const verdict = formula.get('[data-testid="verdict"]')
    expect(verdict.text()).toBe('The fractions do not balance: off by 1/2')
    expect(verdict.attributes('style')).toContain('animation-delay: 2400ms, 2850ms')
    expect(formula.text()).toContain('the check is on fractions only')
  })

  it('shows a balanced formula in the balance colour', () => {
    render({ formulas: [{ ...mismatch, verdict: 'balances', difference: '0' }] })
    const verdict = wrapper.get('[data-testid="verdict"]')
    expect(verdict.text()).toBe('The fractions balance')
    expect(verdict.attributes('style')).toContain('var(--color-confidence-high)')
  })

  it('lists totals before loose fractions, which get no verdict', () => {
    const group = { ...mismatch, kind: 'group', lines: [4], verdict: null, steps: ['J = 1/2', 'Sum: J = 1/2'] }
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

  it('shows every step at once for viewers who prefer less motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    render()
    expect(wrapper.get('section').classes()).toContain('still')
  })
})
