// Records the lessons on the Tutorials page (frontend/public/tutorials) from a running copy of the
// site, logged in as an admin with the seeded HT 13 versions and edition: see docs/tutorials.md.
//
//   cd e2e && node record-tutorials.mjs <out dir> <tablet image.png> [lesson,lesson]
const { chromium } = await import('@playwright/test').catch(() => import('playwright-core'))
import { mkdirSync, renameSync, existsSync, rmSync } from 'node:fs'
import { join } from 'node:path'

const [outDir, tablet] = process.argv.slice(2)
const BASE = process.env.BASE ?? 'http://localhost:5174'
const SIZE = { width: 1280, height: 800 }
mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })

// A visible cursor and a caption bar, injected into every page.
const OVERLAY = `
(() => {
  const ready = () => {
    if (document.getElementById('demo-cursor')) return
    const cursor = document.createElement('div')
    cursor.id = 'demo-cursor'
    Object.assign(cursor.style, { position: 'fixed', zIndex: 99999, width: '18px', height: '18px', borderRadius: '50%',
      background: 'rgba(220,38,38,.75)', border: '2px solid white', boxShadow: '0 0 4px rgba(0,0,0,.5)',
      pointerEvents: 'none', transform: 'translate(-50%,-50%)', left: '-50px', top: '-50px', transition: 'width .1s, height .1s' })
    document.body.appendChild(cursor)
    addEventListener('mousemove', (e) => { cursor.style.left = e.clientX + 'px'; cursor.style.top = e.clientY + 'px' }, true)
    addEventListener('mousedown', () => { cursor.style.width = cursor.style.height = '26px' }, true)
    addEventListener('mouseup', () => { cursor.style.width = cursor.style.height = '18px' }, true)
    const caption = document.createElement('div')
    caption.id = 'demo-caption'
    Object.assign(caption.style, { position: 'fixed', zIndex: 99998, left: '50%', bottom: '24px', transform: 'translateX(-50%)',
      background: 'rgba(30,20,10,.85)', color: 'white', padding: '10px 18px', borderRadius: '10px', font: '600 20px system-ui, sans-serif',
      maxWidth: '80%', textAlign: 'center', pointerEvents: 'none', display: 'none' })
    document.body.appendChild(caption)
  }
  if (document.body) ready(); else addEventListener('DOMContentLoaded', ready)
})()`

async function scene(name, run) {
  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: outDir, size: SIZE }, acceptDownloads: true })
  await context.addInitScript(OVERLAY)
  const page = await context.newPage()
  page.setDefaultTimeout(120000)
  const say = async (text, ms = 1800) => {
    await page.evaluate((t) => { const c = document.getElementById('demo-caption'); if (c) { c.textContent = t; c.style.display = t ? 'block' : 'none' } }, text)
    await page.waitForTimeout(ms)
  }
  const pause = (ms = 700) => page.waitForTimeout(ms)
  const hover = async (locator) => {
    const box = await locator.boundingBox()
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 })
  }
  const click = async (locator) => { await locator.scrollIntoViewIfNeeded(); await hover(locator); await pause(250); await locator.click() }
  const drag = async (from, to) => {
    await page.mouse.move(from.x, from.y, { steps: 15 }); await page.mouse.down(); await pause(200)
    await page.mouse.move(to.x, to.y, { steps: 30 }); await pause(150); await page.mouse.up()
  }
  try {
    await run({ page, say, pause, hover, click, drag })
    await say('', 600)
  } catch (error) {
    console.error(`scene ${name} failed:`, error.message)
    await page.screenshot({ path: join(outDir, `${name}-failure.png`) })
  }
  const video = page.video()
  await context.close()
  const target = join(outDir, `${name}.webm`)
  if (existsSync(target)) rmSync(target)
  renameSync(await video.path(), target)
  console.log('recorded', target)
}

const editBox = (page, n) => page.locator('[data-testid="edit-box"]').nth(n)
async function centre(locator, dx = 0, dy = 0) {
  const b = await locator.boundingBox()
  return { x: b.x + b.width / 2 + dx, y: b.y + b.height / 2 + dy }
}
const tracing = (page) => page.locator('img[alt="HT 13 tracing"]')
async function draw(page, strokes) {
  const box = await page.getByTestId('sketch-canvas').first().boundingBox()
  for (const points of strokes) {
    await page.mouse.move(box.x + points[0][0] * box.width, box.y + points[0][1] * box.height)
    await page.mouse.down()
    for (const [x, y] of points.slice(1)) await page.mouse.move(box.x + x * box.width, box.y + y * box.height, { steps: 10 })
    await page.mouse.up()
  }
}
async function myEdition(page) {
  const response = await page.request.get(`${BASE}/api/tablets/HT-13/versions`)
  const items = (await response.json()).items
  const mine = items.find((v) => v.kind === 'edition' && v.mine)
  return mine ? mine.key.slice(5) : null
}
const only = process.argv[4]?.split(',')
const lesson = (name, fn) => (!only || only.includes(name) ? scene(name, fn) : null)

await lesson('getting-around', async ({ page, say, hover }) => {
  await page.goto(`${BASE}/`)
  await say('Welcome! This tour shows where everything lives.', 2600)
  const nav = page.locator('nav[aria-label="Main"]')
  const stops = [
    ['Analysis', 'Analysis: upload a photo or drawing of a tablet and let the reader find its signs.'],
    ['Tablets', 'Tablets: every published tablet in the corpus, with the scholars’ sign boxes.'],
    ['Signs', 'Signs: look up any sign by number, reading or a quick sketch.'],
    ['Community', 'Community: discuss readings with other scholars.'],
    ['Benchmarks', 'Benchmarks: how accurate the reader is, sign by sign.'],
    ['Tutorials', 'Tutorials: short videos like this one, whenever you need a refresher.'],
  ]
  for (const [name, text] of stops) {
    await hover(nav.getByRole('link', { name }))
    await say(text, 2600)
  }
  await hover(page.getByTestId('bell'))
  await say('The bell tells you when someone shares, mentions or replies to you.', 2600)
  await hover(page.getByTestId('account-menu'))
  await say('Your account menu has your profile, shared work and work queues.', 2600)
})

await lesson('read-a-tablet', async ({ page, say, pause, hover }) => {
  await page.goto(`${BASE}/analysis`)
  await say('Read a tablet: start on the Analysis page.', 2200)
  await say('Upload a photo or drawing of a tablet, as PNG or JPEG.', 1600)
  await page.locator('input[type="file"]').setInputFiles(tablet)
  await page.getByTestId('correct-boxes').waitFor()
  await pause(800)
  await say('The reader draws a box around each sign it finds, coloured by kind of sign.', 2800)
  const box = page.locator('[data-testid="sign-box"]').nth(3)
  await hover(box)
  await say('Point at a box to see the sign, its reading and how sure the reader is.', 3000)
  await page.mouse.move(5, 5)
  await page.mouse.wheel(0, 700)
  await say('Below, the transliteration and a check that the fractions add up.', 3000)
})

await lesson('browse-the-corpus', async ({ page, say, pause, click }) => {
  await page.goto(`${BASE}/tablets`)
  await say('Browse the corpus: every published tablet is on the Tablets page.', 2400)
  await click(page.locator('#tablet-search'))
  await page.locator('#tablet-search').pressSequentially('HT 13', { delay: 140 })
  await page.keyboard.press('Enter')
  await pause(900)
  await click(page.getByTestId('tablet-list').getByRole('button', { name: /^HT 13\s/ }))
  await tracing(page).waitFor()
  await say('The tracing shows the scholars’ published sign boxes.', 2600)
  await click(page.getByTestId('source-model'))
  await page.waitForResponse((r) => r.url().includes('source=model'))
  await say('Switch to the model’s boxes to see what the reader thinks.', 2800)
  await click(page.getByTestId('bookmark'))
  await say('Star a tablet to bookmark it; it stays at the top of your list.', 2600)
})

await lesson('find-a-sign', async ({ page, say, click, pause }) => {
  await page.goto(`${BASE}/signs`)
  await say('Find a sign: type its number, its reading or its name.', 2200)
  await click(page.locator('#signs-search'))
  await page.keyboard.type('ku', { delay: 150 })
  await say('Every result shows the sign’s most typical drawing.', 2400)
  await page.locator('#signs-search').fill('')
  await say('Only remember the shape? Draw it in the box.', 1800)
  await draw(page, [[[0.7, 0.15], [0.3, 0.15], [0.3, 0.85], [0.7, 0.85]], [[0.3, 0.5], [0.55, 0.5]]])
  await page.getByTestId('sketch-result').first().waitFor()
  await say('The closest signs appear as you draw.', 2400)
  await click(page.getByTestId('sketch-result').first())
  await page.getByTestId('occurrences').waitFor()
  await say('A sign’s page shows where it occurs across the corpus.', 3000)
  await page.mouse.wheel(0, 500)
  await pause(1200)
})

await lesson('correct-the-boxes', async ({ page, say, pause, click, drag }) => {
  await page.goto(`${BASE}/tablets/HT-13`)
  await tracing(page).waitFor()
  await say('Correct the boxes: you work on your own copy; the original never changes.', 2600)
  await click(page.getByTestId('correct-boxes'))
  await page.getByTestId('box-editor').waitFor()
  await pause(800)
  await say('Click a box to select it. Its sign appears on the right.', 1400)
  await click(editBox(page, 3))
  await pause(1400)
  await say('Drag a box to move it, or a corner to resize it.', 1200)
  const box = editBox(page, 5)
  await click(box)
  const from = await centre(box)
  await drag(from, { x: from.x + 14, y: from.y + 8 })
  await pause(900)
  await say('Draw a box adds a new one: drag on the tablet.', 1400)
  await click(page.getByTestId('mode-draw'))
  const surface = await page.getByTestId('box-editor').boundingBox()
  await drag({ x: surface.x + surface.width * 0.62, y: surface.y + surface.height * 0.55 },
    { x: surface.x + surface.width * 0.72, y: surface.y + surface.height * 0.62 })
  await say('Name it by searching the sign list.', 1200)
  await click(page.locator('#sign-search'))
  await page.locator('#sign-search').pressSequentially('ku', { delay: 160 })
  await pause(700)
  await click(page.getByTestId('sign-matches').locator('button').first())
  await pause(900)
  await say('Nothing is saved until you press Save. Undo is always one click away.', 2400)
  await click(page.getByTestId('save'))
  await page.getByText('All changes saved').waitFor()
  await say('Saved. Every change is kept in the history, so you can always go back.', 2800)
})

// Epigraphic marks, told so the result is visible: mark two signs, save, then show the transliteration.
const label = (locator) => locator.locator('xpath=ancestor::label[1]')
async function marksStory({ page, say, pause, click }) {
  await page.goto(`${BASE}/tablets/HT-13`)
  await page.locator('img[alt="HT 13 tracing"]').waitFor()
  const fresh = page.getByTestId('new-copy')
  await click((await fresh.count()) ? fresh : page.getByTestId('correct-boxes'))
  await page.getByTestId('box-editor').waitFor()
  await say('Tablets are often worn. Editions mark how sure each reading is.', 2800)
  await say('The first line of HT 13 reads ka-u-de-ta. Let’s mark two of its signs.', 2800)

  const rows = page.getByTestId('box-row')
  await click(rows.nth(1))
  await page.getByTestId('marks').scrollIntoViewIfNeeded()
  await say('Select the sign u. Under Reading, choose Uncertain.', 1800)
  await click(label(page.getByTestId('certainty-uncertain')))
  await pause(1600)

  await click(rows.nth(2))
  await page.getByTestId('marks').scrollIntoViewIfNeeded()
  await say('Now select de. It is lost on the tablet and restored by the editor: choose Lost, restored.', 2200)
  await click(label(page.getByTestId('damage-restored')))
  await pause(1400)
  await say('A word ends after de, so tick “A word ends after this sign”.', 1800)
  await click(label(page.getByTestId('word-end')))
  await pause(1400)

  await say('Save, and the reading is worked out again.', 1400)
  await click(page.getByTestId('save'))
  await page.getByText('All changes saved').waitFor()

  const line = page.locator('#reading-h').locator('xpath=following-sibling::p[span[contains(., "Transliteration")]]').first()
  await line.evaluate((el) => {
    el.style.cssText += ';font-size:30px;line-height:1.4;background:#fff7d6;outline:4px solid #cc6f00;outline-offset:6px;border-radius:8px;padding:6px 10px'
    el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  })
  await pause(1200)
  await say('The transliteration now reads ka-ụ-[de] ta.', 3000)
  await say('ụ: the dot under u marks an uncertain sign.', 3000)
  await say('[de]: square brackets mark a sign that is lost and restored.', 3000)
  await say('The space after [de] is the word end you marked.', 3000)
}
await lesson('mark-damage', marksStory)

await lesson('work-faster', async ({ page, say, click, pause }) => {
  await page.goto(`${BASE}/tablets/HT-13`)
  await click(page.getByTestId('correct-boxes'))
  await page.getByTestId('box-editor').waitFor()
  await say('Zoom in on small or faint signs.', 1400)
  for (let i = 0; i < 3; i++) await click(page.getByTestId('zoom-in'))
  await say('Invert the drawing when strokes are hard to see.', 1400)
  await click(page.getByTestId('invert'))
  await pause(900)
  await say('N and P jump to the next and previous sign.', 1200)
  await page.keyboard.press('n'); await pause(500); await page.keyboard.press('n'); await pause(500)
  await page.keyboard.press('?')
  await page.getByTestId('shortcut-help').waitFor()
  await say('Press ? any time to see every shortcut.', 3000)
})

await lesson('compare-versions', async ({ page, say, click }) => {
  await page.goto(`${BASE}/tablets/HT-13`)
  await page.getByTestId('versions').waitFor()
  await say('Compare versions: scholars, the reader and colleagues often read a tablet differently.', 2800)
  const rows = page.getByTestId('version')
  await click(rows.nth(0).locator('input'))
  await click(rows.nth(2).locator('input'))
  await say('Tick two or more versions, then Compare.', 1600)
  await click(page.getByTestId('compare-versions'))
  await page.getByTestId('agreement').waitFor()
  await say('Each version has its own colour; the summary says how often they agree.', 3000)
  await click(page.getByTestId('only-differences'))
  await click(page.getByTestId('place-row').first())
  await say('Show only the differences, and click one to find it on the tablet.', 3000)
})

await lesson('merge-an-edition', async ({ page, say, click, pause }) => {
  await page.goto(`${BASE}/tablets/HT-13/compare?v=scholar&v=copy:2&v=copy:1`)
  await page.getByTestId('agreement').waitFor()
  await say('Merge an edition: combine the best of several versions into one.', 2400)
  await click(page.getByTestId('merge-link'))
  await page.getByTestId('create-edition').waitFor()
  await say('Where versions disagree, choose whose sign to keep. Agreements are kept for you.', 3000)
  await click(page.getByTestId('merge-place').first().getByTestId('merge-option').first())
  await pause(800)
  await click(page.getByTestId('create-edition'))
  await page.getByTestId('merged-from').waitFor()
  await say('Your edition opens in the editor. Every box remembers whose it was.', 3000)
})

await lesson('release-and-vote', async ({ page, say, click, pause }) => {
  const id = await myEdition(page)
  await page.goto(`${BASE}/box-sets/${id}`)
  await page.getByTestId('release-open').waitFor()
  await page.getByTestId('release-open').scrollIntoViewIfNeeded()
  await say('Release and vote: when an edition is ready, release it for others to vote on.', 2800)
  await click(page.getByTestId('release-open'))
  await say('A release is a fixed snapshot: later edits never change it.', 2200)
  await click(page.getByTestId('release-confirm'))
  await page.getByTestId('release').first().waitFor()
  await pause(1000)
  await page.goto(`${BASE}/tablets/HT-13`)
  await page.getByTestId('editions').waitFor()
  await page.getByTestId('editions').scrollIntoViewIfNeeded()
  await say('On the tablet, back the release you think is best: one vote per tablet.', 2600)
  await click(page.getByTestId('back').first())
  await say('The most-backed release becomes the community edition.', 3000)
})

await lesson('cite-and-export', async ({ page, say, click, pause }) => {
  await page.goto(`${BASE}/editions/1`)
  await page.getByTestId('citation').waitFor()
  await say('Cite and export: every release has a permanent page.', 2400)
  await page.getByTestId('citation').scrollIntoViewIfNeeded()
  await say('Copy a ready-made citation for your paper.', 1400)
  await click(page.getByTestId('copy-citation'))
  await pause(1200)
  await page.getByTestId('export-xml').hover()
  await say('Or download it as TEI-EpiDoc, SVG, PNG, CSV or JSON.', 3000)
})

await lesson('discuss', async ({ page, say, click, pause }) => {
  await page.goto(`${BASE}/signs/AB81`)
  await page.getByTestId('discussion-links').waitFor()
  await say('Discuss: signs, glyphs and editions list the discussions that mention them.', 2800)
  await click(page.getByTestId('discussion-links').locator('a').first())
  await page.locator('#community-comment').waitFor()
  await page.locator('#community-comment').scrollIntoViewIfNeeded()
  await say('Type @ to mention a colleague, a sign or an edition.', 1600)
  await click(page.locator('#community-comment'))
  await page.locator('#community-comment').pressSequentially('Agreed with @an', { delay: 90 })
  await pause(1200)
  await page.keyboard.press('Enter')
  await page.locator('#community-comment').pressSequentially(' here: the top stroke is clear.', { delay: 45 })
  await click(page.getByRole('button', { name: 'Post comment' }))
  await say('They get a notification and a link straight to your comment.', 3000)
})

await lesson('stay-up-to-date', async ({ page, say, click }) => {
  await page.goto(`${BASE}/tablets/HT-13`)
  await tracing(page).waitFor()
  await say('Stay up to date: the bell collects shares, replies, mentions and votes.', 1800)
  await click(page.getByTestId('bell'))
  await page.getByTestId('notification').first().waitFor()
  await say('Click one to go straight to it.', 2600)
  await page.keyboard.press('Escape')
  await click(page.getByTestId('account-menu'))
  await click(page.getByTestId('activity-toggle').locator('input'))
  await page.keyboard.press('Escape')
  await page.getByTestId('glyph-badge').first().waitFor()
  await say('Turn on activity bubbles to see which signs have news since you last looked.', 3200)
})

await lesson('search-sequences', async ({ page, say, click }) => {
  await page.goto(`${BASE}/tablets`)
  await say('Search sign sequences: find every tablet with a word or formula.', 2200)
  await click(page.getByTestId('search-sequence'))
  await click(page.locator('#tablet-search'))
  await page.keyboard.type('KU-RO', { delay: 140 })
  await click(page.locator('form[role="search"] button[type="submit"]'))
  await page.getByTestId('sequence-count').waitFor()
  await say('Use readings or sign numbers; * matches any one sign.', 2800)
  await click(page.getByTestId('sequence-results').getByText('HT 13', { exact: true }))
  await tracing(page).waitFor()
  await say('Open a tablet and the matches are highlighted.', 3200)
})

await lesson('find-work', async ({ page, say, click }) => {
  await page.goto(`${BASE}/queues`)
  await page.getByTestId('queue-row').first().waitFor()
  await say('Find work: queues show where your help matters most.', 2400)
  await say('Tablets where the scholars and the reader disagree most...', 2400)
  await click(page.getByTestId('queue-tab-low-confidence'))
  await page.getByTestId('queue-row').first().waitFor()
  await say('...signs the reader is unsure about...', 2200)
  await click(page.getByTestId('queue-tab-no-edition'))
  await page.getByTestId('queue-row').first().waitFor()
  await say('...and tablets that still need an edition.', 2400)
  await click(page.getByTestId('queue-tab-disagreement'))
  await page.getByTestId('queue-row').first().waitFor()
  await say('Each row takes you straight to the right page.', 2000)
  await click(page.getByTestId('queue-action').first())
  await page.getByTestId('agreement').waitFor()
  await say('Each row takes you straight to the right page.', 2600)
})

await browser.close()
