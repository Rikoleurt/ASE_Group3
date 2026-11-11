// Pure helpers for the Benchmarks page: scores, ordering, accuracy colours.

export const pct = (x, digits = 1) => (x == null ? '—' : `${(x * 100).toFixed(digits)}%`)

/** The score a version is ranked by: signs read end to end, else signs named on true boxes. */
export function headline(entry) {
  if (entry?.read_top1 != null) return { key: 'read_top1', value: entry.read_top1, label: 'signs read correctly', fallback: false }
  if (entry?.id_top1 != null) return { key: 'id_top1', value: entry.id_top1, label: 'signs named correctly', fallback: true }
  return { key: null, value: null, label: 'no score', fallback: true }
}

/** Versions ordered by headline score, worst first (versions without any score go first). */
export function worstToBest(versions) {
  return versions
    .map((entry, index) => ({ entry, index, score: headline(entry).value ?? -1 }))
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .map((item) => item.entry)
}

export function bestVersion(versions) {
  const ordered = worstToBest(versions)
  return ordered.length ? ordered[ordered.length - 1] : null
}

/** What a sign tile shows: identification on the true boxes when the version has it, else end to end. */
export function signAccuracy(sign, identifies) {
  const n = identifies ? sign.n : sign.e2e_n
  const correct = identifies ? sign.id_correct : sign.e2e_correct
  return { n: n ?? 0, correct: correct ?? 0, rate: n ? correct / n : null }
}

export function tabletRate(tablet, identifies) {
  if (identifies) return { n: tablet.identified, correct: tablet.id_correct, rate: tablet.identified ? tablet.id_correct / tablet.identified : null, what: 'named correctly' }
  return { n: tablet.named, correct: tablet.read_top1, rate: tablet.named ? tablet.read_top1 / tablet.named : null, what: 'read correctly' }
}

// One sequential hue (blue), light for low accuracy to dark for high.
const STOPS = [
  [0, [230, 240, 248]],
  [0.25, [179, 211, 236]],
  [0.5, [111, 169, 214]],
  [0.75, [47, 120, 179]],
  [1, [15, 63, 110]],
]
export const NO_DATA = { bg: '#d9d4c4', fg: '#4d2a00' }
export const GRADIENT = `linear-gradient(to right, ${STOPS.map(([p, c]) => `rgb(${c.join(',')}) ${p * 100}%`).join(', ')})`
export const BAR_FILL = 'rgb(47, 120, 179)'

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
  return { bg: `rgb(${rgb.join(", ")})`, fg: r >= 0.6 ? '#ffffff' : '#4d2a00' }
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
  if (tile.key === 'read_top1') return d && i ? 'not measured' : `needs a reader that does both; this version only ${d ? 'detects' : 'identifies'}`
  if (tile.key === 'recall') return 'this version does not detect signs'
  return 'this version does not identify signs'
}
