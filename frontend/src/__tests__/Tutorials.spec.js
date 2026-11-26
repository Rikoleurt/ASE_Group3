import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import TutorialsView from '../views/TutorialsView.vue'
import WelcomeTour from '../components/WelcomeTour.vue'
import { LESSONS, SECTIONS, WATCHED, WELCOME_DISMISSED } from '../state/tutorials'

let wrapper
let router

beforeEach(() => {
  WATCHED.value = []
  WELCOME_DISMISSED.value = false
  try {
    localStorage.clear()
  } catch {
    // jsdom without storage: nothing to clear
  }
})

afterEach(() => wrapper?.unmount())

async function render(path = '/tutorials', component = TutorialsView) {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tutorials/:lesson?', component: TutorialsView },
      { path: '/home', component },
      { path: '/:rest(.*)*', component: { template: '<p />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
}

describe('Tutorials', () => {
  it('lists every lesson by section and opens the first one', async () => {
    await render()
    expect(wrapper.findAll('[data-testid="lesson-link"]')).toHaveLength(LESSONS.length)
    expect(wrapper.findAll('nav[aria-label="Lessons"] h2').map((h) => h.text())).toEqual(
      SECTIONS.map((section) => section.title),
    )
    expect(wrapper.get('#lesson-h').text()).toBe(LESSONS[0].title)
    expect(wrapper.get('[data-testid="lesson-video"]').attributes('src')).toBe(
      `/tutorials/${LESSONS[0].id}.mp4`,
    )
    expect(wrapper.get('[data-testid="lesson-steps"]').findAll('li')).toHaveLength(
      LESSONS[0].steps.length,
    )
  })

  it('opens a lesson from its link, with a way to try the feature', async () => {
    await render('/tutorials/merge-an-edition')
    const lesson = LESSONS.find((l) => l.id === 'merge-an-edition')
    expect(wrapper.get('#lesson-h').text()).toBe(lesson.title)
    expect(wrapper.get('[aria-current="true"]').text()).toContain(lesson.title)
    expect(wrapper.get('[data-testid="try-it"]').attributes('href')).toBe(lesson.tryIt.to)
    await wrapper.get('[data-testid="next-lesson"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe(
      `/tutorials/${LESSONS[LESSONS.indexOf(lesson) + 1].id}`,
    )
  })

  it('falls back to the first lesson for an unknown one', async () => {
    await render('/tutorials/nope')
    expect(wrapper.get('#lesson-h').text()).toBe(LESSONS[0].title)
  })

  it('marks a lesson watched when its video ends, and counts progress', async () => {
    await render('/tutorials/find-a-sign')
    expect(wrapper.get('[data-testid="tutorial-progress"]').text()).toContain(
      `0 of ${LESSONS.length} watched`,
    )
    await wrapper.get('[data-testid="lesson-video"]').trigger('ended')
    expect(WATCHED.value).toEqual(['find-a-sign'])
    expect(wrapper.find('[data-testid="watched"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="tutorial-progress"]').text()).toContain(
      `1 of ${LESSONS.length} watched`,
    )
    await wrapper.get('[data-testid="next-lesson"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="mark-watched"]').trigger('click')
    expect(WATCHED.value).toHaveLength(2)
  })

  it('keeps the steps readable when a video cannot be loaded', async () => {
    await render('/tutorials/discuss')
    await wrapper.get('[data-testid="lesson-video"]').trigger('error')
    expect(wrapper.get('[data-testid="lesson-video-missing"]').text()).toContain(
      'could not be loaded',
    )
    expect(wrapper.get('[data-testid="lesson-steps"]').text()).toContain('mention')
  })

  it('has a video and a poster for every lesson', () => {
    for (const lesson of LESSONS) {
      for (const ext of ['mp4', 'jpg']) {
        expect(
          existsSync(resolve(__dirname, `../../public/tutorials/${lesson.id}.${ext}`)),
          `${lesson.id}.${ext}`,
        ).toBe(true)
      }
    }
  })
})

describe('The welcome on the home page', () => {
  it('points new visitors to the first lesson, and can be dismissed', async () => {
    await render('/home', WelcomeTour)
    expect(wrapper.get('[data-testid="welcome-start"]').attributes('href')).toBe(
      `/tutorials/${LESSONS[0].id}`,
    )
    await wrapper.get('[data-testid="welcome-dismiss"]').trigger('click')
    expect(wrapper.find('[data-testid="welcome-tour"]').exists()).toBe(false)
    expect(WELCOME_DISMISSED.value).toBe(true)
  })

  it('continues from the first lesson not yet watched, and hides once all are watched', async () => {
    WATCHED.value = [LESSONS[0].id, LESSONS[1].id]
    await render('/home', WelcomeTour)
    expect(wrapper.get('[data-testid="welcome-start"]').text()).toBe(
      `Continue: ${LESSONS[2].title}`,
    )
    WATCHED.value = LESSONS.map((lesson) => lesson.id)
    await flushPromises()
    expect(wrapper.find('[data-testid="welcome-tour"]').exists()).toBe(false)
  })
})
