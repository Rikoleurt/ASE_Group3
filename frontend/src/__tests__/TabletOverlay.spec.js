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

describe('Tablet overlay', () => {
  it('keeps the image and draws one box per sign, coloured by role', () => {
    render()
    expect(wrapper.get('img').attributes('src')).toBe('tablet.png')
    const boxes = wrapper.findAll('[data-testid="sign-box"]')
    expect(boxes).toHaveLength(7)
    expect(boxes[0].attributes()).toMatchObject({ x: '10', y: '10', width: '10', height: '8', stroke: ROLES.syllabogram.color })
    expect(boxes[1].attributes('stroke')).toBe(ROLES.fraction.color)
    expect(boxes[2].attributes('stroke')).toBe(ROLES.logogram.color)
    expect(boxes[0].get('title').text()).toBe('ta (90%)')
  })

  it('gives the KU-RO signs their own colour', () => {
    render()
    const roles = wrapper.findAll('[data-testid="sign-box"]').map((box) => box.attributes('data-role'))
    expect(roles).toEqual(['syllabogram', 'fraction', 'logogram', 'fraction', 'total', 'total', 'fraction'])
  })

  it('draws a dashed box around the formula in its verdict colour, after the signs', () => {
    render()
    const formula = wrapper.get('[data-testid="formula-box"]')
    expect(formula.attributes('stroke')).toBe('var(--color-confidence-low)')
    expect(formula.attributes()).toMatchObject({ x: '9', y: '9', width: '32', height: '50' })
    expect(formula.attributes('style')).toContain('animation-delay: 820ms')
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
