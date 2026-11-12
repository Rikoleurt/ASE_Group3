import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import BenchmarksView from '../views/BenchmarksView.vue'
import { accuracyColor, bestVersion, contrast, gridMode, rampRgb, rankVersions, textRgb, worstToBest } from '../components/benchmarks/benchmarkData'

let wrapper

const both = { detection: true, identification: true }
const signs = [
  { sign: 'AB01', glyph: 'A', n: 10, id_correct: 9, e2e_n: 10, e2e_correct: 5, role: 'syllabogram', bucket: '5+', confused_with: [{ sign: 'AB02', count: 1 }] },
  { sign: 'AB02', glyph: null, n: 4, id_correct: 1, e2e_n: 4, e2e_correct: 1, role: 'syllabogram', bucket: '2-4', confused_with: [] },
  { sign: 'A100', glyph: 'B', n: 2, id_correct: 2, e2e_n: 2, e2e_correct: 2, role: 'logogram', bucket: '1', confused_with: [] },
  { sign: 'AB10', glyph: 'C', n: 0, id_correct: 0, e2e_n: 3, e2e_correct: 0, role: 'logogram', bucket: 'unseen', confused_with: [] },
]
const tablets = [
  { tablet: 'T1', truths: 10, found: 9, named: 9, read_top1: 9, identified: 10, id_correct: 5 },
  { tablet: 'T2', truths: 4, found: 0, named: 0, read_top1: 0, identified: 4, id_correct: 4 },
]
function doc(version, over = {}) {
  return {
    version, description: `${version} description`, kind: 'two_stage', stages: both, split: 'val', tablets: 131, reference: 'ref',
    metrics: { read_top1: 0.5, id_top1: 0.6, recall: 0.9, id_ece: 0.1 },
    ci95: { read_top1: [0.4, 0.6], id_top1: [0.5, 0.7], recall: [0.8, 0.95], id_ece: [0.05, 0.2] },
    vs_reference: { read_top1: { diff: -0.1, lo: -0.2, hi: 0, verdict: 'worse' }, recall: { diff: 0.02, lo: -0.01, hi: 0.05, verdict: 'tie' } },
    by_role: { syllabogram: 0.7, logogram: 0.3 }, by_bucket: { unseen: 0, 1: 0.1, '2-4': 0.5, '5+': 0.8 },
    bucket_counts: { unseen: 3, 1: 2, '2-4': 4, '5+': 10 }, cost: { latency_s: 0.62, weights_mb: 9.4, train_minutes: 128.3 },
    coverage_curve: [{ coverage: 0.5, id_top1: 0.9 }, { coverage: 1, id_top1: 0.6 }], signs, tablet_results: tablets, ...over,
  }
}
const docs = {
  alpha: doc('alpha', { metrics: { read_top1: 0.4, id_top1: 0.5, recall: 0.9, id_ece: 0.1 } }),
  beta: doc('beta', { metrics: { read_top1: 0.7, id_top1: 0.8, recall: 0.95, id_ece: 0.05 }, vs_reference: { read_top1: { diff: 0.1, lo: 0.05, hi: 0.15, verdict: 'better' } } }),
  idonly: doc('idonly', {
    kind: 'shape_knn', stages: { detection: false, identification: true },
    metrics: { id_top1: 0.65, id_ece: 0.07 }, ci95: { id_top1: [0.6, 0.7] }, vs_reference: {}, coverage_curve: [],
  }),
  detonly: doc('detonly', { kind: 'detector', stages: { detection: true, identification: false }, metrics: { recall: 0.5 }, by_role: {}, by_bucket: {}, bucket_counts: {}, coverage_curve: [] }),
}
const index = {
  versions: ['alpha', 'beta', 'idonly'].map((v) => ({ version: v, kind: docs[v].kind, stages: docs[v].stages, description: `${v} description`, read_top1: docs[v].metrics.read_top1 ?? null, id_top1: docs[v].metrics.id_top1 ?? null })),
}

function stubFetch(overrides = {}) {
  const fetch = vi.fn(async (url) => {
    if (overrides[url]) return overrides[url]
    const body = url === '/api/benchmarks' ? index : docs[decodeURIComponent(url.split('/').pop())]
    return body ? { ok: true, status: 200, json: async () => body } : { ok: false, status: 404, json: async () => ({ detail: 'Unknown benchmark version.' }) }
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}
function stubMotion(matches) {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
}
async function render() {
  wrapper = mount(BenchmarksView, { attachTo: document.body })
  await flushPromises()
  return wrapper
}
const select = () => wrapper.get('[data-testid="version-select"]')
const tile = (key) => wrapper.get(`[data-metric="${key}"]`)
const signIds = () => wrapper.findAll('[data-testid="glyph-grid"] button').map((b) => b.attributes('data-sign'))
async function tick(ms) {
  await vi.advanceTimersByTimeAsync(ms)
}

beforeEach(() => stubMotion(false))
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Benchmarks page', () => {
  it('selects the best version by read rate and shows its facts', async () => {
    stubFetch()
    await render()
    expect(select().element.value).toBe('beta')
    expect(wrapper.get('[data-testid="meta"]').text()).toContain('val split')
    expect(wrapper.get('[data-testid="meta"]').text()).toContain('131 tablets')
    expect(select().attributes('title')).toContain('131 tablets')
    expect(select().findAll('option').every((o) => o.attributes('title'))).toBe(true)
    expect(wrapper.text()).toContain('beta description')
    expect(tile('read_top1').text()).toContain('70.0%')
    expect(tile('read_top1').text()).toContain('95% interval 40% to 60%')
    expect(tile('read_top1').text()).toContain('+10.0 points vs ref')
    expect(tile('read_top1').text()).toContain('better')
  })

  it('switches versions from the dropdown', async () => {
    const fetch = stubFetch()
    await render()
    await select().setValue('alpha')
    await flushPromises()
    expect(wrapper.text()).toContain('alpha description')
    expect(tile('read_top1').text()).toContain('40.0%')
    expect(tile('read_top1').text()).toContain('worse')
    expect(tile('recall').text()).toContain('tie')
    expect(fetch).toHaveBeenCalledWith('/api/benchmarks/alpha')
  })

  it('shows a dash and a reason for metrics a version does not have', async () => {
    stubFetch()
    await render()
    await select().setValue('idonly')
    await flushPromises()
    expect(tile('read_top1').text()).toContain('—')
    expect(tile('read_top1').text()).toContain('names signs on given boxes')
    expect(tile('recall').text()).toContain('does not detect')
    expect(tile('id_top1').text()).toContain('65.0%')
    expect(tile('id_top1').text()).toContain('No comparison with ref')
    expect(wrapper.find('[data-testid="coverage"]').exists()).toBe(false)
  })

  it('shows empty group bars for a detection-only version', async () => {
    const withDetOnly = { versions: [...index.versions, { version: 'detonly', kind: 'generic', stages: docs.detonly.stages, description: '', read_top1: null, id_top1: null }] }
    stubFetch({ '/api/benchmarks': { ok: true, status: 200, json: async () => withDetOnly } })
    await render()
    await select().setValue('detonly')
    await flushPromises()
    expect(wrapper.text()).toContain('This version does not identify signs.')
    expect(tile('id_top1').text()).toContain('—')
    expect(tile('recall').text()).toContain('50.0%')
  })

  it('shows buckets with counts, roles, cost and the coverage chart', async () => {
    stubFetch()
    await render()
    expect(wrapper.get('[data-bar="5+"]').text()).toContain('(10)')
    expect(wrapper.get('[data-bar="unseen"]').text()).toContain('Never seen')
    expect(wrapper.get('[data-bar="logogram"]').text()).toContain('(2)')
    expect(wrapper.get('[data-testid="cost"]').text()).toContain('0.62 s')
    expect(wrapper.get('[data-testid="cost"]').text()).toContain('9.4 MB')
    expect(wrapper.get('[data-testid="cost"]').text()).toContain('128 min')
    expect(wrapper.find('[data-testid="coverage"]').exists()).toBe(true)
  })

  it('points the arrow the way the number moved, with the verdict beside it', async () => {
    stubFetch()
    await render()
    expect(tile('read_top1').get('[data-testid="delta"]').text()).toContain('▲ +10.0')
    expect(tile('read_top1').get('[data-verdict="better"]').classes()).toContain('text-better')
    expect(tile('recall').find('[data-verdict]').exists()).toBe(false) // no comparison: no colour
  })

  it('reports a failed index load and retries', async () => {
    stubFetch({ '/api/benchmarks': { ok: false, status: 503, json: async () => ({ detail: 'Benchmark results are not available on this server.' }) } })
    await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('not available on this server')
    stubFetch()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(select().element.value).toBe('beta')
  })

  it('says so when nothing is published', async () => {
    stubFetch({ '/api/benchmarks': { ok: true, status: 200, json: async () => ({ versions: [] }) } })
    await render()
    expect(wrapper.text()).toContain('No benchmark results have been published yet.')
  })
})

describe('Glyph grid', () => {
  it('colours by accuracy, falls back to the sign ID and greys out signs without data', async () => {
    stubFetch()
    await render()
    const ab01 = wrapper.get('[data-sign="AB01"]')
    expect(ab01.find('.linear-a').text()).toBe('A')
    expect(ab01.attributes('title')).toContain('90% named correctly')
    expect(ab01.attributes('title')).toContain('AB02 (1)')
    expect(ab01.element.style.backgroundColor).toBe(accuracyColor(0.9).bg)
    const noGlyph = wrapper.get('[data-sign="AB02"]')
    expect(noGlyph.find('.linear-a').exists()).toBe(false)
    expect(noGlyph.text()).toBe('AB02')
    const empty = wrapper.get('[data-sign="AB10"]')
    expect(empty.classes()).toContain('border-dashed')
    expect(empty.attributes('title')).toContain('no examples')
  })

  it('scores read end to end for versions that do not identify', async () => {
    stubFetch()
    docs.alpha.stages = { detection: true, identification: false }
    docs.alpha.kind = 'one_stage'
    await render()
    await select().setValue('alpha')
    await flushPromises()
    expect(wrapper.get('[data-sign="AB01"]').attributes('title')).toContain('50% read correctly end to end')
    expect(wrapper.get('[data-sign="AB10"]').classes()).not.toContain('border-dashed')
    docs.alpha.stages = both
    docs.alpha.kind = 'two_stage'
  })

  it('sorts by frequency, accuracy and sign ID', async () => {
    stubFetch()
    await render()
    expect(signIds()).toEqual(['AB01', 'AB02', 'A100', 'AB10'])
    const sort = wrapper.findAll('select')[1]
    await sort.setValue('accuracy')
    expect(signIds()).toEqual(['A100', 'AB01', 'AB02', 'AB10'])
    await sort.setValue('sign')
    expect(signIds()).toEqual(['A100', 'AB01', 'AB02', 'AB10'])
    await sort.setValue('frequency')
    expect(signIds()[0]).toBe('AB01')
  })

  it('filters by role and training bucket', async () => {
    stubFetch()
    await render()
    const [, , roleSelect, bucketSelect] = wrapper.findAll('select')
    await roleSelect.setValue('logogram')
    expect(signIds().sort()).toEqual(['A100', 'AB10'])
    await bucketSelect.setValue('1')
    expect(signIds()).toEqual(['A100'])
    expect(wrapper.get('[data-testid="glyph-count"]').text()).toBe('1 of 4 signs')
    await roleSelect.setValue('syllabogram')
    expect(signIds()).toEqual([])
    expect(wrapper.text()).toContain('No signs match these filters.')
  })

  it('shows the detail line on focus', async () => {
    stubFetch()
    await render()
    await wrapper.get('[data-sign="AB02"]').trigger('focus')
    expect(wrapper.get('[data-testid="glyph-detail"]').text()).toContain('AB02: 25%')
  })
})

describe('Play worst to best', () => {
  it('orders versions by headline score, worst first, marking identification-only ones', () => {
    expect(worstToBest(index.versions).map((v) => v.version)).toEqual(['alpha', 'beta'])
  })

  it('plays only the end-to-end versions, worst to best, and skips identification-only ones', async () => {
    stubFetch()
    await render()
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await tick(0)
    expect(select().element.value).toBe('alpha')
    expect(wrapper.get('[data-testid="progress"]').text()).toContain('Version 1 of 2: alpha')
    expect(tile('read_top1').text()).toContain('40.0%')
    await tick(1500)
    expect(select().element.value).toBe('beta')
    expect(tile('read_top1').text()).toContain('70.0%')
    await tick(1500)
    expect(wrapper.find('[data-testid="pause"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="progress"]').text()).toContain('done')
    expect(select().element.value).toBe('beta')
    expect(wrapper.text()).not.toContain('Version 3')
    // still selectable by hand
    await select().setValue('idonly')
    await tick(0)
    expect(tile('id_top1').text()).toContain('65.0%')
  })

  it('pauses, resumes and stops back at the starting version', async () => {
    stubFetch()
    await render()
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await tick(0)
    await wrapper.get('[data-testid="pause"]').trigger('click')
    expect(wrapper.get('[data-testid="pause"]').text()).toBe('Resume')
    await tick(10000)
    expect(select().element.value).toBe('alpha')
    await wrapper.get('[data-testid="pause"]').trigger('click')
    await tick(1500)
    expect(select().element.value).toBe('beta')
    await wrapper.get('[data-testid="stop"]').trigger('click')
    await tick(0)
    expect(select().element.value).toBe('beta')
    await tick(5000)
    expect(select().element.value).toBe('beta')
    expect(wrapper.find('[data-testid="progress"]').exists()).toBe(false)
  })

  it('stops playing when the user picks a version', async () => {
    stubFetch()
    await render()
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await tick(0)
    await select().setValue('beta')
    await tick(5000)
    expect(select().element.value).toBe('beta')
    expect(wrapper.find('[data-testid="stop"]').exists()).toBe(false)
  })

  it('steps without transitions under reduced motion', async () => {
    stubMotion(true)
    stubFetch()
    await render()
    expect(wrapper.get('main').classes()).toContain('reduce-motion')
    expect(wrapper.get('[data-sign="AB01"]').classes()).toContain('no-motion')
    expect(wrapper.get('[data-testid="bar-fill"]').classes()).toContain('no-motion')
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await tick(0)
    await tick(1500)
    expect(select().element.value).toBe('beta')
  })

  it('animates by default', async () => {
    stubFetch()
    await render()
    expect(wrapper.get('main').classes()).not.toContain('reduce-motion')
    expect(wrapper.get('[data-sign="AB01"]').classes()).not.toContain('no-motion')
  })
})

// Real shapes from benchmark/history: a plain detector (kind "generic") cannot name signs,
// the one-stage identity baseline names them end to end (badly), shape-knn only names given boxes.
const generic = doc('generic-det', { kind: 'generic', stages: { detection: true, identification: false }, metrics: { read_top1: 0, recall: 0.8 }, ci95: { read_top1: [0, 0] }, vs_reference: {}, by_role: {}, by_bucket: {}, bucket_counts: {}, coverage_curve: [],
  signs: signs.map((x) => ({ ...x, n: 0, id_correct: 0, e2e_correct: 0 })), tablet_results: tablets.map((t) => ({ ...t, read_top1: 0, identified: 0, id_correct: 0 })) })
const oneStage = doc('one-stage', { kind: 'one_stage', stages: { detection: true, identification: false }, metrics: { read_top1: 0.01, recall: 0.05 }, vs_reference: {}, by_role: {}, by_bucket: {}, bucket_counts: {}, coverage_curve: [],
  signs: signs.map((x) => ({ ...x, n: 0, id_correct: 0 })), tablet_results: tablets.map((t) => ({ ...t, identified: 0, id_correct: 0 })) })

function withExtras(extra) {
  const all = { ...docs, 'generic-det': generic, 'one-stage': oneStage }
  const idx = { versions: [...index.versions, ...extra.map((v) => ({ version: v, kind: all[v].kind, stages: all[v].stages, description: '', read_top1: all[v].metrics.read_top1 ?? null, id_top1: null }))] }
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    const body = url === '/api/benchmarks' ? idx : all[decodeURIComponent(url.split('/').pop())]
    return { ok: !!body, status: body ? 200 : 404, json: async () => body }
  }))
}

describe('Versions that cannot name signs', () => {
  it('shows no per-sign or per-tablet zeros for a detector, and no read rate', async () => {
    withExtras(['generic-det'])
    await render()
    await select().setValue('generic-det')
    await flushPromises()
    expect(wrapper.find('[data-testid="glyph-grid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="tablet-grid"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="grid-note"]').text()).toContain('Not measured')
    expect(tile('read_top1').text()).toContain('—')
    expect(tile('read_top1').text()).not.toContain('0.0%')
    expect(tile('recall').text()).toContain('80.0%')
  })

  it('still shows the one-stage detector end to end', async () => {
    withExtras(['one-stage'])
    await render()
    await select().setValue('one-stage')
    await flushPromises()
    expect(wrapper.find('[data-testid="glyph-grid"]').exists()).toBe(true)
    expect(wrapper.get('[data-sign="AB01"]').attributes('title')).toContain('50% read correctly end to end')
    expect(tile('read_top1').text()).toContain('1.0%')
    expect(gridMode(oneStage)).toBe('e2e')
    expect(gridMode(generic)).toBe(null)
    expect(gridMode(docs.idonly)).toBe('id')
  })

  it('lists a detector without a score but leaves it out of playback', async () => {
    withExtras(['generic-det'])
    await render()
    const entry = { version: 'generic-det', kind: 'generic', stages: generic.stages, read_top1: 0, id_top1: null }
    expect(worstToBest([...index.versions, entry]).map((v) => v.version)).not.toContain('generic-det')
    expect(select().findAll('option').map((o) => o.element.value)).toContain('generic-det')
  })
})

describe('Ranking tiers', () => {
  it('ranks end to end first, never mixing true-box scores into that order', () => {
    const e = (version, read, id, kind = 'two_stage', stages = both) => ({ version, kind, stages, read_top1: read, id_top1: id })
    const list = [e('hi-id', null, 0.99, 'shape_knn', { detection: false, identification: true }), e('low', 0.2, 0.3), e('high', 0.6, 0.7), e('none', null, null, 'x', { detection: false, identification: false })]
    const t = rankVersions(list)
    expect(t.endToEnd.map((v) => v.version)).toEqual(['low', 'high'])
    expect(t.idOnly.map((v) => v.version)).toEqual(['hi-id'])
    expect(t.unscored.map((v) => v.version)).toEqual(['none'])
    expect(bestVersion(list).version).toBe('high')
    expect(bestVersion([list[0]]).version).toBe('hi-id')
  })
})

describe('Playback robustness', () => {
  const answer = (url) => ({ ok: true, status: 200, json: async () => docs[url.split('/').pop()] })

  it('does nothing after unmount during the prefetch', async () => {
    let release
    const gate = new Promise((r) => { release = r })
    const fetch = stubFetch()
    await render()
    fetch.mockImplementation(async (url) => {
      if (url.endsWith('/alpha')) await gate
      return answer(url)
    })
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    wrapper.unmount()
    release()
    await tick(0)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('Stop during the prefetch cancels playback', async () => {
    let release
    const gate = new Promise((r) => { release = r })
    const fetch = stubFetch()
    await render()
    fetch.mockImplementation(async (url) => {
      if (url.endsWith('/alpha')) await gate
      return answer(url)
    })
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await wrapper.get('[data-testid="stop"]').trigger('click')
    release()
    await tick(5000)
    expect(select().element.value).toBe('beta')
    expect(wrapper.find('[data-testid="stop"]').exists()).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores a second Play while starting', async () => {
    const fetch = stubFetch()
    await render()
    const before = fetch.mock.calls.length
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="play"]').exists()).toBe(false)
    await tick(0)
    expect(fetch.mock.calls.length - before).toBe(1)
  })

  it('skips a version that fails to load and plays the rest', async () => {
    const fetch = stubFetch()
    await render()
    fetch.mockImplementation(async (url) => (url.endsWith('/alpha') ? { ok: false, status: 500, json: async () => ({ detail: 'boom' }) } : answer(url)))
    vi.useFakeTimers()
    await wrapper.get('[data-testid="play"]').trigger('click')
    await tick(0)
    expect(wrapper.get('[data-testid="skipped"]').text()).toContain('alpha')
    expect(select().element.value).toBe('beta')
    expect(wrapper.get('[data-testid="progress"]').text()).toContain('Version 1 of 1: beta')
  })
})

describe('Colour scale', () => {
  it('keeps text readable on every tile colour', () => {
    for (let i = 0; i <= 200; i++) {
      const r = i / 200
      expect(contrast(rampRgb(r), textRgb(r)), `accuracy ${r}`).toBeGreaterThanOrEqual(4.5)
    }
    expect(contrast(rampRgb(null), textRgb(null))).toBeGreaterThanOrEqual(4.5)
  })

  it('gives focused tiles an outline that clears the fill', async () => {
    stubFetch()
    await render()
    expect(wrapper.get('[data-sign="AB01"]').classes()).toEqual(expect.arrayContaining(['focus-visible:outline-offset-2', 'focus-visible:outline-ink']))
  })
})
