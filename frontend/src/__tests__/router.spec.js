import { describe, expect, it } from 'vitest'
import router from '../router'

describe('Router', () => {
  it('loads the page behind every route', async () => {
    // Lazy routes only fail when visited, so a route to a deleted page would otherwise go unnoticed.
    for (const route of router.getRoutes()) {
      const page = await route.components.default()
      expect(page.default, route.path).toBeTruthy()
    }
  })

  it('serves the Analysis upload page', () => {
    expect(router.resolve('/analysis').name).toBe('analysis')
  })
})
