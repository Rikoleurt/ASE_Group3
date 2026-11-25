// Ranks catalogue signs for a typed query. A scholar types a reading ("ku"), a sign number
// ("AB81", "81") or part of a name ("VIN"); exact matches come first, then prefixes, then
// anything containing the query. Signs with a reading win ties, then catalogue order.
export const MAX_MATCHES = 12

function number(sign) {
  return sign.replace(/^A[B]?0*/i, '')
}

function rank(sign, query) {
  const id = sign.sign.toLowerCase()
  const reading = (sign.reading || '').toLowerCase()
  const name = (sign.name || '').toLowerCase()
  if (reading === query || id === query) return 0
  if (number(id) === query.replace(/^a[b]?0*/, '')) return 1 // "81", "ab081" or "AB81" for AB81
  if (reading.startsWith(query)) return 2
  if (id.startsWith(query)) return 3
  if (name.includes(query)) return 4
  return null
}

export function searchSigns(catalogue, text, limit = MAX_MATCHES) {
  const query = text.trim().toLowerCase()
  if (!query) return []
  return catalogue
    .map((sign, index) => ({ sign, index, rank: rank(sign, query) }))
    .filter((entry) => entry.rank !== null)
    .sort(
      (a, b) =>
        a.rank - b.rank || Number(!a.sign.reading) - Number(!b.sign.reading) || a.index - b.index,
    )
    .slice(0, limit)
    .map((entry) => entry.sign)
}
