// Pure helpers for the Benchmarks page: scores, ordering, accuracy colours.

export const pct = (x, digits = 1) => (x == null ? '—' : `${(x * 100).toFixed(digits)}%`)

/** Can the version name signs on the boxes it finds? A plain detector (kind "generic") cannot, so its read rate is meaningless. */
export const readsEndToEnd = (v) => !!v?.stages?.detection && (!!v.stages.identification || v.kind === 'one_stage')
export const identifiesSigns = (v) => !!v?.stages?.identification

/** What the per-sign and per-tablet grids can show: 'id', 'e2e', or null (nothing measured). */
export function gridMode(v) {
  if (identifiesSigns(v)) return 'id'
  return readsEndToEnd(v) ? 'e2e' : null
}

/** The score a version is ranked by: signs read end to end, else signs named on true boxes (a separate tier). */
export function headline(entry) {
  if (entry?.read_top1 != null && readsEndToEnd(entry)) return { key: 'read_top1', value: entry.read_top1, label: 'signs read correctly', fallback: false }
  if (entry?.id_top1 != null) return { key: 'id_top1', value: entry.id_top1, label: 'signs named correctly', fallback: true }
  return { key: null, value: null, label: 'no score', fallback: true }
}

/** Tiers: end-to-end versions, then versions only scored on true boxes (not comparable), then unscored ones. Each worst first. */
export function rankVersions(versions) {
  const tiers = { endToEnd: [], idOnly: [], unscored: [] }
  versions.forEach((entry, index) => {
    const h = headline(entry)
    ;(h.value == null ? tiers.unscored : h.fallback ? tiers.idOnly : tiers.endToEnd).push({ entry, index, score: h.value ?? 0 })
  })
  const sort = (list) => list.sort((a, b) => a.score - b.score || a.index - b.index).map((item) => item.entry)
  return { endToEnd: sort(tiers.endToEnd), idOnly: sort(tiers.idOnly), unscored: sort(tiers.unscored) }
}

/** The playback order: end-to-end tier worst to best, then the true-box tier worst to best. Unscored versions are left out. */
export function worstToBest(versions) {
  const t = rankVersions(versions)
  return [...t.endToEnd, ...t.idOnly]
}

/** The best end-to-end version; only when there is none does it fall back to the best true-box one. */
export function bestVersion(versions) {
  const t = rankVersions(versions)
  const pool = t.endToEnd.length ? t.endToEnd : t.idOnly
  return pool.length ? pool[pool.length - 1] : (versions[0] ?? null)
}

/** What a sign tile shows. mode: 'id' (named on the true boxes) or 'e2e'; anything else means not measured. */
export function signAccuracy(sign, mode) {
  if (mode !== 'id' && mode !== 'e2e') return { n: 0, correct: 0, rate: null }
  const n = mode === 'id' ? sign.n : sign.e2e_n
  const correct = mode === 'id' ? sign.id_correct : sign.e2e_correct
  return { n: n ?? 0, correct: correct ?? 0, rate: n ? correct / n : null }
}

export function tabletRate(tablet, mode) {
  if (mode === 'id') return { n: tablet.identified, correct: tablet.id_correct, rate: tablet.identified ? tablet.id_correct / tablet.identified : null, what: 'named correctly' }
  if (mode === 'e2e') return { n: tablet.named, correct: tablet.read_top1, rate: tablet.named ? tablet.read_top1 / tablet.named : null, what: 'read correctly' }
  return { n: 0, correct: 0, rate: null, what: 'not measured' }
}

// One sequential hue (blue), light for low accuracy to dark for high.
const STOPS = [
  [0, [230, 240, 248]],
  [0.25, [179, 211, 236]],
  [0.5, [111, 169, 214]],
  [0.75, [47, 120, 179]],
  [1, [15, 63, 110]],
]
export const NO_DATA = { bg: 'rgb(217, 212, 196)', fg: 'rgb(77, 42, 0)' }
export const GRADIENT = `linear-gradient(to right, ${STOPS.map(([p, c]) => `rgb(${c.join(',')}) ${p * 100}%`).join(', ')})`
export const BAR_FILL = 'rgb(47, 120, 179)'

const TEXT_CHOICES = [[77, 42, 0], [255, 255, 255], [0, 0, 0]]
const channel = (v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
const luminance = ([r, g, b]) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
/** WCAG contrast ratio of two [r, g, b] colours. */
export function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
function bestText(rgb) {
  const best = TEXT_CHOICES.reduce((m, c) => (contrast(c, rgb) > contrast(m, rgb) ? c : m))
  return `rgb(${best.join(', ')})`
}
export const rampRgb = (rate) => accuracyColor(rate).bg.match(/\d+/g).map(Number)
export const textRgb = (rate) => accuracyColor(rate).fg.match(/\d+/g).map(Number)

/** Colour for an accuracy in [0, 1]; text colour flips to white on dark fills. null means no data. */
export function accuracyColor(rate) {
  if (rate == null) return NO_DATA
  const r = Math.min(1, Math.max(0, rate))
  let i = 0
  while (i < STOPS.length - 2 && r > STOPS[i + 1][0]) i++
  const [p0, c0] = STOPS[i]
  const [p1, c1] = STOPS[i + 1]
  const t = (r - p0) / (p1 - p0)
  const rgb = c0.map((v, k) => Math.round(v + (c1[k] - v) * t))
  return { bg: `rgb(${rgb.join(', ')})`, fg: bestText(rgb) }
}

export const BUCKET_ORDER = ['unseen', '1', '2-4', '5+']
export const BUCKET_LABELS = { unseen: 'Never seen in training', 1: '1 training example', '2-4': '2–4 examples', '5+': '5 or more examples' }

export function naturalSignCompare(a, b) {
  return a.localeCompare(b, 'en', { numeric: true })
}

export function sortSigns(rows, how) {
  const out = [...rows]
  if (how === 'sign') return out.sort((a, b) => naturalSignCompare(a.sign, b.sign))
  if (how === 'accuracy') {
    return out.sort((a, b) => (b.rate ?? -1) - (a.rate ?? -1) || b.n - a.n || naturalSignCompare(a.sign, b.sign))
  }
  return out.sort((a, b) => b.n - a.n || naturalSignCompare(a.sign, b.sign))
}

export const HEADLINE_TILES = [
  { key: 'read_top1', title: 'Signs read correctly', hint: 'found and named correctly, end to end', needs: 'detection and identification' },
  { key: 'id_top1', title: 'Named correctly on true boxes', hint: 'given the right box, is the sign right', needs: 'identification' },
  { key: 'recall', title: 'Signs found', hint: 'detection recall', needs: 'detection' },
  { key: 'id_ece', title: 'Calibration error', hint: 'lower is better; confidence vs how often right', needs: 'identification' },
]

export function missingNote(tile, stages) {
  const d = stages?.detection
  const i = stages?.identification
  if (tile.key === 'read_top1') return d && i ? 'not measured' : `needs a reader that finds and names signs; this version only ${d ? 'finds signs' : 'names signs on given boxes'}`
  if (tile.key === 'recall') return 'this version does not detect signs'
  return 'this version does not identify signs'
}
