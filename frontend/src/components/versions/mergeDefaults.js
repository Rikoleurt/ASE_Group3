// The default choice for each place when merging versions (workbench, story D): the sign most
// versions agree on; between equally common signs, the scholars' if they have one there, else
// the earliest version's. Among the versions with the chosen sign, the scholars' box is kept,
// else the earliest version's.
export function defaultPick(place, keys) {
  const present = keys.filter((key) => place.members[key])
  if (!present.length) return null
  const votes = new Map()
  for (const key of present) {
    const sign = place.members[key].sign ?? ''
    votes.set(sign, (votes.get(sign) ?? 0) + 1)
  }
  const best = Math.max(...votes.values())
  const leaders = new Set([...votes].filter(([, count]) => count === best).map(([sign]) => sign))
  const preferred =
    present.find((key) => key === 'scholar' && leaders.has(place.members[key].sign ?? '')) ??
    present.find((key) => leaders.has(place.members[key].sign ?? ''))
  return preferred
}

export function majorityPicks(places, keys) {
  return places.map((place) => defaultPick(place, keys))
}

// Take every place's box from one version; places it has no box in keep their current choice.
export function takeAllFrom(places, picks, key) {
  return places.map((place, index) => (place.members[key] ? key : picks[index]))
}
