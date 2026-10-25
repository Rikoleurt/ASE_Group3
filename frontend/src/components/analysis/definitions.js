// Plain-language definitions for the colour key, shown when a label is hovered or focused.
export const DEFINITIONS = {
  syllabogram:
    'A sign that stands for a syllable, a sound such as "ku" or "ro". Syllables are joined into words; most Linear A words are names whose meaning is unknown.',
  logogram:
    'A sign that stands for a whole word, usually a commodity being counted, such as VIN (wine) or OLIV (olives).',
  fraction:
    'A sign for part of a unit, written after a whole number, such as J = 1/2 or E = 1/4. Values follow Corazza et al. (2021).',
  total:
    'KU-RO, the word for "total". It closes a list of entries, followed by their sum. PO-TO-KU-RO is a grand total.',
  other: 'A sign whose role the reader could not determine.',
  formula:
    'A section of entries that ends in KU-RO. The check adds up the entries’ fractions and compares them with the total’s fraction.',
}

// Unicode vulgar fractions read better than "1/2" in the equation.
const VULGAR = {
  '1/2': '½', '1/3': '⅓', '2/3': '⅔', '1/4': '¼', '3/4': '¾', '1/5': '⅕', '2/5': '⅖', '3/5': '⅗',
  '4/5': '⅘', '1/6': '⅙', '5/6': '⅚', '1/8': '⅛', '3/8': '⅜', '5/8': '⅝', '7/8': '⅞', '1/10': '⅒',
}

/** "1/2" -> "½", "1 1/2" -> "1½"; other values ("1/16", "?") as they are. */
export function pretty(value) {
  if (value == null) return ''
  const [whole, part] = value.includes(' ') ? value.split(' ') : [null, value]
  const shown = VULGAR[part] ?? part
  return whole ? `${whole}${VULGAR[part] ? '' : ' '}${shown}` : shown
}
