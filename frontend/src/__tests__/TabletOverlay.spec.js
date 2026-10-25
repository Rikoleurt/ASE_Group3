import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import TabletOverlay from '../components/analysis/TabletOverlay.vue'
import { ROLES } from '../components/analysis/colors.js'
import { mismatch, signs } from './analysisFixture.js'

let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})

function render(props = { signs, formulas: [mismatch] }) {
  wrapper = mount(TabletOverlay, { props, slots: { default: '<img src="tablet.png" alt="tablet">' } })
  return wrapper
}

const boxes = () => wrapper.findAll('[data-testid="sign-box"]')

describe('Tablet overlay', () => {
  it('keeps the image and draws one box per sign, coloured by role', () => {
    render()
    expect(wrapper.get('img').attributes('src')).toBe('tablet.png')
    expect(boxes()).toHaveLength(signs.length)
    expect(boxes()[0].attributes()).toMatchObject({ x: '10', y: '10', width: '10', height: '8', stroke: ROLES.syllabogram.color })
    expect(boxes()[1].attributes('stroke')).toBe(ROLES.fraction.color)
    expect(boxes()[2].attributes('stroke')).toBe(ROLES.logogram.color)
  })

  it('gives the KU-RO signs their own colour', () => {
    render()
    expect(boxes().map((box) => box.attributes('data-role'))).toEqual([
      'syllabogram', 'fraction', 'logogram', 'fraction', 'total', 'total', 'fraction', 'syllabogram',
    ])
  })

  it('draws a dashed box around the formula in its verdict colour, after the signs', () => {
    render()
    const formula = wrapper.get('[data-testid="formula-box"]')
    expect(formula.attributes('stroke')).toBe('var(--color-confidence-low)')
    expect(formula.attributes()).toMatchObject({ x: '9', y: '9', width: '32', height: '50' })
    expect(formula.attributes('style')).toContain(`animation-delay: ${signs.length * 60 + 400}ms`)
  })

  it('shows a sign card while a box is hovered', async () => {
    render()
    expect(wrapper.find('[data-testid="sign-card"]').exists()).toBe(false)
    await boxes()[4].trigger('mouseenter')
    const card = wrapper.get('[data-testid="sign-card"]')
    expect(card.get('[data-testid="sign-glyph"]').text()).toBe('\u{10642}')
    expect(card.text()).toContain('ku')
    expect(card.get('[data-testid="sign-meaning"]').text()).toBe('total (KU-RO)')
    expect(boxes()[4].classes()).toContain('active')
    await boxes()[4].trigger('mouseleave')
    expect(wrapper.find('[data-testid="sign-card"]').exists()).toBe(false)
  })

  it('shows the card for keyboard focus too, and describes each box for screen readers', async () => {
    render()
    expect(boxes()[2].attributes('tabindex')).toBe('0')
    expect(boxes()[2].attributes('aria-label')).toBe('VIN (AB131a), Logogram, means wine, 90% confident')
    await boxes()[2].trigger('focus')
    expect(wrapper.get('[data-testid="sign-meaning"]').text()).toBe('wine')
    await boxes()[2].trigger('blur')
    expect(wrapper.find('[data-testid="sign-card"]').exists()).toBe(false)
  })

  it('places the card beside the box, on the side with more room', async () => {
    render()
    await boxes()[0].trigger('mouseenter') // left half: card to its right
    expect(wrapper.get('[data-testid="sign-card"]').attributes('style')).toContain('left: 21%')
    await boxes()[7].trigger('mouseenter') // right half and low: card to its left, anchored at the bottom
    const style = wrapper.get('[data-testid="sign-card"]').attributes('style')
    expect(style).toContain('right: 31%')
    expect(style).toContain('bottom: 22')
  })

  it('turns the boxes off and on again', async () => {
    render()
    const toggle = wrapper.get('button')
    expect(toggle.text()).toBe('Boxes: on')
    await toggle.trigger('click')
    expect(wrapper.find('[data-testid="tablet-overlay"]').exists()).toBe(false)
    expect(toggle.text()).toBe('Boxes: off')
    await toggle.trigger('click')
    expect(wrapper.find('[data-testid="tablet-overlay"]').exists()).toBe(true)
  })

  it('shows only the image when nothing was found', () => {
    render({ signs: [], formulas: [] })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.get('img').exists()).toBe(true)
  })

  it('skips the drawing animation for viewers who prefer less motion', () => {
    vi.stubGlobal('matchMedia', (query) => ({ matches: query === '(prefers-reduced-motion: reduce)' }))
    render()
    expect(wrapper.get('svg').classes()).toContain('still')
  })
})
