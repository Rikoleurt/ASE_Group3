// Delimiters in labels are escaped; destinations are typed numeric IDs only.
const pattern = /@\[((?:\\[\\\]]|[^\]\\\r\n]){1,255})\]\((user:[0-9]{1,20}|symbol:[0-9]{1,20}:[0-9]{1,20})\)/g

export function parseMentionTokens(body) {
  return [...body.matchAll(pattern)].map((match) => ({
    token: match[0], start: match.index, end: match.index + match[0].length,
    label: match[1].replace(/\\([\\\]])/g, '$1'),
    key: match[2].split(':').map((part, index) => index ? String(BigInt(part)) : part).join(':'),
  }))
}

export function mentionToken(target) {
  const label = target.label.replace(/\\/g, '\\\\').replace(/\]/g, '\\]')
  return `@[${label}](${target.key})`
}

export function decodeDraft(body) {
  let text = ''
  let offset = 0
  const ranges = []
  for (const item of parseMentionTokens(body)) {
    text += body.slice(offset, item.start)
    const start = text.length
    text += `@${item.label}`
    ranges.push({ start, end: text.length, target: { key: item.key, label: item.label } })
    offset = item.end
  }
  return { text: text + body.slice(offset), ranges }
}

export function encodeDraft(text, ranges) {
  let body = ''
  let offset = 0
  for (const range of ranges) {
    body += text.slice(offset, range.start) + mentionToken(range.target)
    offset = range.end
  }
  return body + text.slice(offset)
}

export function updateRanges(previous, next, ranges) {
  let start = 0
  while (start < previous.length && start < next.length && previous[start] === next[start]) start++
  let oldEnd = previous.length
  let newEnd = next.length
  while (oldEnd > start && newEnd > start && previous[oldEnd - 1] === next[newEnd - 1]) { oldEnd--; newEnd-- }
  const shift = next.length - previous.length
  return ranges.flatMap((range) => {
    if (range.end <= start) return [range]
    if (range.start >= oldEnd) return [{ ...range, start: range.start + shift, end: range.end + shift }]
    // Editing any part of a selected mention turns it back into ordinary text.
    return []
  })
}
