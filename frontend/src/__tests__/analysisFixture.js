// An /analysis response shaped like HT 13's: two entries with J, then KU-RO J.
const J = '\u{10746}'
const box = (x, y) => ({ x, y, w: 0.1, h: 0.08 })
const sign = (id, reading, role, x, y, extra = {}) => ({
  id, reading, role, label: reading, sign: reading, confidence: 90, box: box(x, y),
  candidates: [], crop: '', glyph: null, meaning: null, ...extra,
})

export const signs = [
  sign(1, 'ta', 'syllabogram', 0.1, 0.1, { sign: 'AB59', glyph: '\u{1062B}' }),
  sign(2, 'J', 'fraction', 0.3, 0.1, { sign: 'A707', glyph: J, meaning: '1/2', confidence: 74 }),
  sign(3, 'VIN', 'logogram', 0.1, 0.3, {
    sign: 'AB131a', glyph: '\u{1064D}', meaning: 'wine',
    candidates: [
      { sign: 'AB131a', label: 'AB131a (VIN)', roles: ['logogram'], probability: 81 },
      { sign: 'AB131b', label: 'AB131b (VIN)', roles: ['logogram'], probability: 12 },
      { sign: 'A706', label: 'A706 (H)', roles: ['fraction'], probability: 0.2 },
    ],
  }),
  sign(4, 'J', 'fraction', 0.3, 0.3, { sign: 'A707', glyph: J, meaning: '1/2' }),
  sign(5, 'ku', 'syllabogram', 0.1, 0.5, { sign: 'AB81', glyph: '\u{10642}', meaning: 'total (KU-RO)' }),
  sign(6, 'ro', 'syllabogram', 0.2, 0.5, { sign: 'AB02', glyph: '\u{10601}', meaning: 'total (KU-RO)' }),
  sign(7, 'J', 'fraction', 0.3, 0.5, { sign: 'A707', glyph: J, meaning: '1/2', confidence: 61 }),
  sign(8, 'N800', 'syllabogram', 0.7, 0.7, { sign: 'N800' }), // no Unicode character
]

const term = (id, line) => ({ id, sign: 'A707', label: 'J', glyph: J, value: '1/2', tentative: false, line })

export const mismatch = {
  kind: 'total',
  lines: [0, 1, 2],
  sign_ids: [1, 2, 3, 4, 5, 6, 7],
  marker_ids: [5, 6],
  box: { x: 0.1, y: 0.1, w: 0.3, h: 0.48 },
  entries: [term(2, 0), term(4, 1)],
  total: [term(7, 2)],
  entries_sum: '1', total_value: '1/2',
  verdict: 'mismatch', difference: '1/2', carried: 0, tentative: false,
  steps: ['J = 1/2', 'Entries: J + J = 1/2 + 1/2 = 1', 'KU-RO total: J = 1/2', 'The fractions are off by 1/2'],
  note: 'Whole numbers (tally strokes) are not read, so the check is on fractions only.',
}

export const analysis = {
  symbol_interpretation: 'ta J / VIN J / ku-ro J',
  confidence: 83,
  time_taken: 2.7,
  summary: '8 signs found: 4 syllabograms, 3 fractions, 1 logogram. KU-RO total found: the fractions are off by 1/2.',
  width: 1000, height: 2000, trained: true,
  signs,
  lines: [
    { index: 0, sign_ids: [1, 2], text: 'ta J', gloss: 'ta 1/2' },
    { index: 1, sign_ids: [3, 4], text: 'VIN J', gloss: 'wine 1/2' },
    { index: 2, sign_ids: [5, 6, 7], text: 'ku-ro J', gloss: 'total 1/2' },
    { index: 3, sign_ids: [8], text: 'N800', gloss: 'N800' },
  ],
  formulas: [mismatch],
}
