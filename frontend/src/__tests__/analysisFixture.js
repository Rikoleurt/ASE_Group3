// An /analysis response shaped like HT 13's: two entries with J, then KU-RO J.
const box = (x, y) => ({ x, y, w: 0.1, h: 0.08 })
const sign = (id, label, role, x, y, confidence = 90) => ({
  id, label, role, confidence, sign: label, reading: label, box: box(x, y), candidates: [], crop: '', glyph: null,
})

export const signs = [
  sign(1, 'ta', 'syllabogram', 0.1, 0.1),
  sign(2, 'J', 'fraction', 0.3, 0.1, 74),
  sign(3, 'VIN', 'logogram', 0.1, 0.3),
  sign(4, 'J', 'fraction', 0.3, 0.3),
  sign(5, 'ku', 'syllabogram', 0.1, 0.5),
  sign(6, 'ro', 'syllabogram', 0.2, 0.5),
  sign(7, 'J', 'fraction', 0.3, 0.5, 61),
]

export const mismatch = {
  kind: 'total',
  lines: [0, 1, 2],
  sign_ids: [1, 2, 3, 4, 5, 6, 7],
  marker_ids: [5, 6],
  box: { x: 0.1, y: 0.1, w: 0.3, h: 0.48 },
  entries: [], total: [],
  entries_sum: '1', total_value: '1/2',
  verdict: 'mismatch', difference: '1/2', carried: 0, tentative: false,
  steps: ['J = 1/2', 'Entries: J + J = 1/2 + 1/2 = 1', 'KU-RO total: J = 1/2', 'The fractions are off by 1/2'],
  note: 'Whole numbers (tally strokes) are not read, so the check is on fractions only.',
}

export const analysis = {
  symbol_interpretation: 'ta J / VIN J / ku-ro J',
  confidence: 83,
  time_taken: 2.7,
  summary: '7 signs found: 3 syllabograms, 3 fractions, 1 logogram. KU-RO total found: the fractions are off by 1/2.',
  width: 1000, height: 2000, trained: true,
  signs,
  lines: [],
  formulas: [mismatch],
}
