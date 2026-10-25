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
