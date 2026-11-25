// Visual review of the whole website: screenshots of every page at three widths and in its key
// states, with automated checks on each (scholars' workbench, final review).
//
//   cd e2e && npm ci && node visual-review.mjs [out-dir]
//
// Runs against a running frontend (BASE, default http://localhost:5174) whose backend has the
// HT 13 tablet and its seeded versions and edition (the in-memory demo, or a dev database with
// scripts/seed_versions.py). It needs Chrome installed (it uses the "chrome" channel).
//
// Visitors: on the demo, a `demo_as` cookie picks the visitor (anon, user, reviewer, admin). On a
// real server set VISUAL_ADMIN, VISUAL_REVIEWER and VISUAL_USER to "email:password" to log in.
//
// Checks on each capture:
//   - axe-core accessibility (serious and critical violations);
//   - no horizontal scroll;
//   - no console errors, page errors or server errors (5xx);
//   - at 390 px, touch targets of at least 40 px (text links inside sentences excepted);
//   - at 1440 px, keyboard focus is visible on the first 25 controls, and the top bar fits on
//     one line.
// Writes <out>/shots/*.png, <out>/report.json and <out>/report.md.

import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const { chromium } = await import('@playwright/test').catch(() => import('playwright-core'))
const require = createRequire(import.meta.url)
const AXE = require.resolve('axe-core/axe.min.js')

const BASE = process.env.BASE ?? 'http://localhost:5174'
const OUT = path.resolve(process.argv[2] ?? 'visual-review-out')
const WIDTHS = [1440, 820, 390]
const HEIGHTS = { 1440: 900, 820: 1180, 390: 844 }
const MAX_HEIGHT = 6000 // long pages are cut here
const ACTIVITY_KEY = 'ase3.show-glyph-activity'

await mkdir(path.join(OUT, 'shots'), { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []

// --- visitors ------------------------------------------------------------------------------

async function visitor(role, width) {
  const context = await browser.newContext({ viewport: { width, height: HEIGHTS[width] ?? 900 } })
  const login = process.env[`VISUAL_${role.toUpperCase()}`]
  if (login) {
    const [email, password] = login.split(/:(.*)/s)
    const response = await context.request.post(`${BASE}/api/users/login`, { data: { email, password } })
    if (!response.ok()) throw new Error(`Could not log in as ${role}: ${response.status()}`)
  } else {
    await context.addCookies([{ name: 'demo_as', value: role, url: BASE }])
  }
  return context
}

async function api(context, method, url, data) {
  const me = await context.request.get(`${BASE}/api/users/me`)
  const csrf = me.ok() ? (await me.json()).csrf_token : undefined
  const response = await context.request.fetch(`${BASE}/api${url}`, {
    method,
    headers: csrf ? { 'X-CSRF-Token': csrf } : {},
    ...(data instanceof Object && data.multipart ? { multipart: data.multipart } : data ? { data } : {}),
  })
  if (!response.ok()) throw new Error(`${method} ${url}: ${response.status()} ${await response.text()}`)
  return response.status() === 204 ? null : response.json()
}

// --- seed what the pages show ----------------------------------------------------------------

const admin = await visitor('admin', 1440)
const seed = {}
{
  const image = await admin.request.get(`${BASE}/api/tablets/HT-13/image`)
  const analysis = await api(admin, 'POST', '/analysis', {
    multipart: { file: { name: 'HT-13.png', mimeType: 'image/png', buffer: await image.body() } },
  })
  seed.analysis = analysis.analysis_id
  const sign = analysis.signs.find((s) => s.sign) ?? analysis.signs[0]
  await api(admin, 'POST', `/analysis/${seed.analysis}/corrections`, { sign_id: sign.id, proposed_sign: 'AB01', note: 'The left stroke is longer.' }).catch(() => {})
  const discussion = await api(admin, 'POST', '/community/discussions', { analysis_id: seed.analysis, title: `Reading of HT 13 (${Date.now()})` })
  seed.discussion = discussion.id
  await api(admin, 'POST', `/community/discussions/${seed.discussion}/comments`, { body: 'Is the third sign of line 2 really @[AB81 (ku)](sign:AB81)? Compare @[the edition](edition:1).' }).catch(() => {})
  seed.copy = (await api(admin, 'GET', '/tablets/HT-13/box-set').catch(() => null))?.id
  const versions = await api(admin, 'GET', '/tablets/HT-13/versions')
  seed.copies = versions.items.filter((v) => v.kind !== 'scholar' && v.kind !== 'model').map((v) => v.key)
  const editions = await api(admin, 'GET', '/tablets/HT-13/editions')
  seed.release = editions.items[0]?.id
  seed.copy ??= Number(seed.copies[0]?.split(':')[1])
}
console.log('seeded', JSON.stringify(seed))

// --- pages -----------------------------------------------------------------------------------

const ALL = ['admin']
const PAGES = [
  { name: 'home', path: '/', roles: ['admin', 'anon'] },
  { name: 'analysis', path: '/analysis', roles: ALL },
  { name: 'tablets', path: '/tablets', roles: ALL },
  { name: 'tablet', path: '/tablets/HT-13', roles: ['admin', 'user', 'anon'] },
  { name: 'tablet-model', path: '/tablets/HT-13?boxes=model', roles: ALL },
  { name: 'tablet-sequence-hit', path: '/tablets/HT-13?hl=21,22', roles: ALL },
  { name: 'tablet-bubbles', path: '/tablets/HT-13', roles: ALL, bubbles: true },
  { name: 'compare', path: `/tablets/HT-13/compare?v=scholar&v=model&${seed.copies.slice(0, 1).map((k) => `v=${k}`).join('&')}`, roles: ALL },
  { name: 'merge', path: `/tablets/HT-13/merge?v=scholar&${seed.copies.slice(0, 2).map((k) => `v=${k}`).join('&')}`, roles: ALL },
  { name: 'box-set', path: `/box-sets/${seed.copy}`, roles: ALL },
  { name: 'edition', path: `/editions/${seed.release}`, roles: ['admin', 'anon'] },
  { name: 'edition-missing', path: '/editions/999999', roles: ALL },
  { name: 'signs', path: '/signs', roles: ALL },
  { name: 'sign', path: '/signs/AB81', roles: ALL },
  { name: 'community', path: '/community', roles: ['admin', 'anon'] },
  { name: 'discussion', path: `/community/${seed.discussion}`, roles: ALL },
  { name: 'benchmarks', path: '/benchmarks', roles: ALL },
  { name: 'profile', path: '/profile', roles: ALL },
  { name: 'history', path: '/profile/history', roles: ALL },
  { name: 'history-detail', path: `/profile/history/${seed.analysis}`, roles: ALL },
  { name: 'shared', path: '/shared', roles: ALL },
  { name: 'review', path: '/review', roles: ['admin', 'user'] },
  { name: 'admin', path: '/admin', roles: ALL },
  { name: 'queues', path: '/queues', roles: ['admin', 'reviewer', 'anon'] },
  { name: 'queues-edition', path: '/queues?tab=disagreement&against=edition', roles: ALL },
  { name: 'queues-low-confidence', path: '/queues?tab=low-confidence', roles: ALL },
  { name: 'queues-no-edition', path: '/queues?tab=no-edition', roles: ALL },
  { name: 'queues-close-votes', path: '/queues?tab=close-votes', roles: ALL },
  { name: 'queues-loading', path: '/queues', roles: ALL, delay: '**/api/queues/**' },
  { name: 'queues-error', path: '/queues', roles: ALL, fail: '**/api/queues/**' },
  { name: 'tablet-demo', path: '/tablet-demo', roles: ALL },
  { name: 'tablet-reading', path: '/tablet-reading', roles: ALL },
  { name: 'login', path: '/login', roles: ['anon'] },
  { name: 'signup', path: '/signup', roles: ['anon'] },
]

// --- checks ----------------------------------------------------------------------------------

async function checks(page, width) {
  await page.addScriptTag({ path: AXE })
  const axe = await page.evaluate(async () => {
    const { violations } = await window.axe.run(document, { resultTypes: ['violations'] })
    return violations
      .filter((v) => ['serious', 'critical'].includes(v.impact))
      .map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, sample: v.nodes[0]?.target.join(' ') }))
  })
  const layout = await page.evaluate((narrow) => {
    const root = document.documentElement
    const out = { overflow: root.scrollWidth - root.clientWidth }
    const header = document.querySelector('header')
    out.topBarHeight = header ? Math.round(header.getBoundingClientRect().height) : null
    if (narrow) {
      const small = []
      for (const el of document.querySelectorAll('button, a[href], input:not([type=hidden]), select, [role=tab]')) {
        const box = el.getBoundingClientRect()
        if (!box.width || !box.height || getComputedStyle(el).visibility === 'hidden') continue
        const inline = el.tagName === 'A' && getComputedStyle(el).display === 'inline' && el.closest('p, li, td, span')
        if (inline || el.type === 'checkbox' || el.type === 'radio') continue
        if (box.height < 40 && box.width < 40 * 4) small.push(`${el.tagName.toLowerCase()}${el.dataset.testid ? `[${el.dataset.testid}]` : ''} "${(el.innerText || el.getAttribute('aria-label') || el.placeholder || '').trim().slice(0, 24)}" ${Math.round(box.width)}×${Math.round(box.height)}`)
      }
      out.smallTargets = small
    }
    return out
  }, width === 390)
  let focus = null
  if (width === 1440) {
    focus = []
    await page.locator('body').click({ position: { x: 1, y: 1 } }).catch(() => {})
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('Tab')
      const found = await page.evaluate(() => {
        const el = document.activeElement
        if (!el || el === document.body) return null
        const style = getComputedStyle(el)
        const visible = (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none'
        return visible ? null : `${el.tagName.toLowerCase()} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 24)}"`
      })
      if (found && !focus.includes(found)) focus.push(found)
    }
  }
  return { axe, ...layout, focusInvisible: focus }
}

// --- capture ---------------------------------------------------------------------------------

async function capture(spec, role, width) {
  const ctx = await visitor(role, width)
  if (spec.bubbles) await ctx.addInitScript(([key]) => localStorage.setItem(key, '1'), [ACTIVITY_KEY])
  const page = await ctx.newPage()
  page.setDefaultTimeout(60000)
  const errors = []
  page.on('console', (message) => message.type() === 'error' && errors.push(`console: ${message.text().slice(0, 160)}`))
  page.on('pageerror', (error) => errors.push(`page: ${error.message.slice(0, 160)}`))
  page.on('response', (response) => response.status() >= 500 && errors.push(`${response.status()} ${new URL(response.url()).pathname}`))
  // Waiting is on API responses, not "network idle": Chrome never reports an error response
  // whose body the page did not read as finished, so network idle may never come.
  const pending = new Set()
  page.on('request', (request) => request.url().includes('/api/') && pending.add(request))
  page.on('response', (response) => pending.delete(response.request()))
  page.on('requestfailed', (request) => pending.delete(request))
  async function settled(limit = 60000) {
    const end = Date.now() + limit
    let quiet = 0
    while (Date.now() < end && quiet < 3) {
      await page.waitForTimeout(250)
      quiet = pending.size ? 0 : quiet + 1
    }
  }
  if (spec.delay) await page.route(spec.delay, async (route) => { await new Promise((r) => setTimeout(r, 4000)); await route.continue() })
  if (spec.fail) await page.route(spec.fail, (route) => route.abort('failed'))
  const name = `${spec.name}${role === 'admin' ? '' : `-${role}`}-${width}`
  const result = { name, page: spec.name, role, width, path: spec.path, url: null, errors }
  try {
    await page.goto(`${BASE}${spec.path}`, { waitUntil: spec.delay ? 'domcontentloaded' : 'load', timeout: 90000 })
    if (spec.delay) await page.waitForTimeout(600)
    else {
      await settled()
      await page.waitForTimeout(500) // images and transitions
    }
    result.url = page.url().replace(BASE, '')
    const height = await page.evaluate(() => document.documentElement.scrollHeight)
    await page.screenshot({
      path: path.join(OUT, 'shots', `${name}.png`),
      fullPage: height <= MAX_HEIGHT,
      ...(height > MAX_HEIGHT ? { clip: { x: 0, y: 0, width, height: MAX_HEIGHT }, fullPage: true } : {}),
    })
    if (!spec.delay) Object.assign(result, await checks(page, width))
  } catch (error) {
    result.failed = error.message.split('\n')[0]
  }
  results.push(result)
  console.log(`${name}: ${result.failed ?? `${result.axe?.length ?? '-'} axe, overflow ${result.overflow}, ${errors.length} errors`}`)
  await ctx.close()
}

for (const spec of PAGES) {
  for (const role of spec.roles) {
    for (const width of role === 'admin' ? WIDTHS : [1440, 390]) await capture(spec, role, width)
  }
}

// States that need a change on the server first, put back afterwards.
const tablet = PAGES.find((p) => p.name === 'tablet')
if (seed.release) {
  await api(admin, 'PUT', '/tablets/HT-13/edition-override', { release_id: seed.release, comment: 'Checked against the new photographs of the tablet.' })
  await capture({ ...tablet, name: 'tablet-override' }, 'user', 1440)
  await api(admin, 'POST', '/tablets/HT-13/edition-override/clear', { comment: 'Back to the vote after the visual review.' })
}
const anouk = (await api(admin, 'GET', '/admin/users?q=anouk').catch(() => null))?.items?.[0]
if (anouk) {
  await api(admin, 'PUT', `/admin/users/${anouk.id}/voting`, { can_vote: false, reason: 'Several throwaway accounts voted together.' })
  await capture({ ...tablet, name: 'tablet-no-voting-rights' }, 'user', 1440)
  await api(admin, 'PUT', `/admin/users/${anouk.id}/voting`, { can_vote: true, reason: 'Restored after the visual review.' })
}
await admin.close()
await browser.close()

// --- report ----------------------------------------------------------------------------------

await writeFile(path.join(OUT, 'report.json'), JSON.stringify({ base: BASE, seed, results }, null, 2))
const rows = results.map((r) => {
  const notes = [
    r.failed && `failed: ${r.failed}`,
    r.overflow > 0 && `scrolls sideways by ${r.overflow}px`,
    ...(r.axe ?? []).map((v) => `axe ${v.id} ×${v.nodes} (${v.sample})`),
    ...r.errors,
    r.smallTargets?.length && `${r.smallTargets.length} small targets: ${r.smallTargets.slice(0, 3).join('; ')}`,
    r.focusInvisible?.length && `focus not visible: ${r.focusInvisible.slice(0, 3).join('; ')}`,
    r.width === 1440 && r.topBarHeight > 80 && `top bar ${r.topBarHeight}px tall (wraps?)`,
  ].filter(Boolean)
  return `| ${r.name} | ${r.url ?? r.path} | ${notes.join('<br>') || 'ok'} |`
})
await writeFile(
  path.join(OUT, 'report.md'),
  `# Visual review\n\n${new Date().toISOString()} against ${BASE}\n\n| Capture | Page | Findings |\n|---|---|---|\n${rows.join('\n')}\n`,
)
console.log(`wrote ${results.length} captures to ${OUT}`)
