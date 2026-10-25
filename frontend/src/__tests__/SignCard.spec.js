import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SignCard from '../components/analysis/SignCard.vue'
import { ROLES } from '../components/analysis/colors.js'
import { signs } from './analysisFixture.js'

const card = (sign, roleKey = sign.role) => mount(SignCard, { props: { sign, roleKey } })

describe('Sign card', () => {
  it('shows the glyph in its role colour, the reading, ID, role, meaning and confidence', () => {
    const wrapper = card(signs[2])
    const glyph = wrapper.get('[data-testid="sign-glyph"]')
    expect(glyph.text()).toBe('\u{1064D}')
    expect(glyph.classes()).toContain('linear-a')
    expect(glyph.attributes('style')).toContain('color: rgb(204, 121, 167)') // logogram
    expect(wrapper.text()).toContain('VIN')
    expect(wrapper.text()).toContain('AB131a')
    expect(wrapper.text()).toContain(ROLES.logogram.label)
    expect(wrapper.get('[data-testid="sign-meaning"]').text()).toBe('wine')
    expect(wrapper.text()).toContain('Confidence90%')
  })

  it('lists runner-up readings, leaving out those below 1%', () => {
    const wrapper = card(signs[2])
    expect(wrapper.text()).toContain('Or perhapsAB131b (VIN) (12%)')
    expect(wrapper.text()).not.toContain('A706')
  })

  it('leaves out what a sign does not have', () => {
    const wrapper = card(signs[0]) // a syllable: a sound, no meaning, no runner-ups
    expect(wrapper.find('[data-testid="sign-meaning"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Or perhaps')
  })

  it('says so when Unicode has no character for the sign', () => {
    const wrapper = card(signs[7])
    expect(wrapper.get('[data-testid="sign-glyph"]').text()).toBe('?')
    expect(wrapper.text()).toContain('no Unicode character')
  })

  it('uses the KU-RO colour for the signs of KU-RO', () => {
    const wrapper = card(signs[4], 'total')
    expect(wrapper.text()).toContain(ROLES.total.label)
  })
})
