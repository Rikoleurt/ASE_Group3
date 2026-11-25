import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import MentionComposer from '../components/mentions/MentionComposer.vue'

let wrapper
const ok = (items) => ({ ok: true, json: async () => ({ items, next_after: null }) })
const symbol = { key: 'symbol:12:0', kind: 'symbol', label: 'ku', sign_id: 0, tablet_filename: 'HT13.png' }
const user = { key: 'user:7', kind: 'user', label: 'reader' }
const button = (label) => wrapper.findAll('button').find((item) => item.text() === label)

afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it.each([{ users: [user] }, { users: [] }])('keeps the results panel mounted when switching tabs with results $users', async ({ users }) => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  let resolveUsers
  const fetch = vi.fn()
    .mockResolvedValueOnce(ok([symbol]))
    .mockImplementationOnce(() => new Promise((resolve) => { resolveUsers = resolve }))
    .mockResolvedValueOnce(ok([symbol]))
  vi.stubGlobal('fetch', fetch)
  wrapper = mount(MentionComposer, { props: { discussionId: 4 } })
  await wrapper.get('textarea').setValue('@')
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  const panel = wrapper.get('[aria-label="Mention results"]').element
  expect(wrapper.get('[role="option"]').text()).toContain('@ku')

  await button('Users').trigger('click')
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  expect(wrapper.get('[aria-label="Mention results"]').element).toBe(panel)
  expect(wrapper.get('[aria-label="Mention results"]').attributes('aria-busy')).toBe('true')
  expect(wrapper.get('[role="status"]').text()).toBe('Loading suggestions…')
  expect(wrapper.find('[role="option"]').exists()).toBe(false)
  expect(button('Users').attributes('aria-pressed')).toBe('true')

  resolveUsers(ok(users))
  await flushPromises()
  expect(wrapper.get('[aria-label="Mention results"]').element).toBe(panel)
  expect(wrapper.get('[aria-label="Mention results"]').attributes('aria-busy')).toBe('false')
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
  expect(wrapper.get('[aria-label="Mention results"]').text()).toContain(users.length ? '@reader' : 'No matching suggestions.')

  await button('Symbols of this tablet').trigger('click')
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  expect(wrapper.get('[aria-label="Mention results"]').element).toBe(panel)
  expect(wrapper.get('[role="option"]').text()).toContain('@ku')
  await wrapper.get('[role="option"]').trigger('click')
  expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['@[ku](symbol:12:0) '])
  expect(wrapper.find('[aria-label="Mention results"]').exists()).toBe(false)
})
