// One colour per sign role, from the Okabe–Ito palette (safe for colour-blind viewers).
export const ROLES = {
  syllabogram: { color: '#0072B2', label: 'Syllable' },
  logogram: { color: '#CC79A7', label: 'Logogram' },
  fraction: { color: '#E69F00', label: 'Fraction' },
  total: { color: '#009E73', label: 'KU-RO (total)' },
  other: { color: '#7A7A7A', label: 'Other' },
}

// Verdicts reuse the page's confidence colours (assets/main.css).
export const VERDICTS = {
  balances: { color: 'var(--color-confidence-high)', label: 'The fractions balance' },
  mismatch: { color: 'var(--color-confidence-low)', label: 'The fractions do not balance' },
  incomplete: { color: 'var(--color-confidence-mid)', label: 'Cannot be checked' },
  no_fractions: { color: 'var(--color-confidence-mid)', label: 'No fractions to check' },
}

export const GROUP_COLOR = '#7A7A7A'

/** The legend key for a sign: KU-RO signs get their own colour, whatever their role. */
export function roleKey(sign, markerIds) {
  if (markerIds.has(sign.id)) return 'total'
  return ROLES[sign.role] ? sign.role : 'other'
}

export function formulaColor(formula) {
  return formula.verdict ? VERDICTS[formula.verdict].color : GROUP_COLOR
}

/** True when the viewer asked the system for less motion. */
export function prefersStill() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}
