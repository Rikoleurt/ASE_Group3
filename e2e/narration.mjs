// Spoken narration for the tutorial videos: every caption is read aloud with the Windows voice
// "Microsoft Zira Desktop" (System.Speech), timed to when the caption appears. Windows only; elsewhere
// the videos are recorded silent, as before.
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

export const VOICE = 'Microsoft Zira Desktop'
export const CAN_SPEAK = process.platform === 'win32' && process.env.NARRATION !== 'off'

// How a caption is read: readings, sign numbers and file formats spelt out for the voice.
const SPOKEN = [
  [/ka-ụ-\[de\] ta/g, 'ka, u with a dot under it, de in square brackets, then ta'],
  [/^ụ: the dot under u/, 'The dot under u'],
  [/^\[de\]: square brackets/, 'Square brackets around de'],
  [/\[de\]/g, 'de'],
  [/ka-u-de-ta/g, 'ka, u, de, ta'],
  [/KU-RO/g, 'ku ro'],
  [/\bAB(\d+)/g, 'A B $1'],
  [/\bHT (\d+)/g, 'H T $1'],
  [/TEI-EpiDoc/g, 'T E I, Epi Doc'],
  [/\bSVG\b/g, 'S V G'],
  [/\bPNG\b/g, 'P N G'],
  [/\bCSV\b/g, 'C S V'],
  [/\bJSON\b/g, 'Jason'],
  [/\bJPEG\b/g, 'J peg'],
  [/\* matches/g, 'a star matches'],
  [/Press \? /g, 'Press the question mark key '],
  [/\.\.\./g, ', '],
  [/’/g, "'"],
  [/[“”]/g, ''],
]

export function spoken(text) {
  return SPOKEN.reduce((out, [pattern, replacement]) => out.replace(pattern, replacement), text).trim()
}

// The caption strings written literally in a script: say('...') and say("...").
export function captionsIn(source) {
  const found = new Set()
  for (const match of source.matchAll(/say\(\s*(['"])((?:\\.|(?!\1).)*)\1/g)) {
    // eslint-disable-next-line no-new-func
    const text = Function(`return ${match[1]}${match[2]}${match[1]}`)()
    if (text) found.add(text)
  }
  return [...found]
}

function seconds(wav) {
  const data = readFileSync(wav)
  const byteRate = data.readUInt32LE(28)
  let offset = 12
  while (offset < data.length - 8) {
    const id = data.toString('ascii', offset, offset + 4)
    const size = data.readUInt32LE(offset + 4)
    if (id === 'data') return size / byteRate
    offset += 8 + size
  }
  return (data.length - 44) / byteRate
}

// Speak every text not yet spoken (one PowerShell for all of them) and return text -> {wav, seconds}.
export function prepare(texts, dir) {
  mkdirSync(dir, { recursive: true })
  const items = texts.map((text) => {
    const words = spoken(text)
    const wav = join(dir, `${createHash('sha1').update(`${VOICE}|${words}`).digest('hex').slice(0, 16)}.wav`)
    return { text, words, wav }
  })
  const missing = items.filter((item) => !existsSync(item.wav))
  if (missing.length && CAN_SPEAK) {
    const list = join(dir, 'speak.json')
    writeFileSync(list, JSON.stringify(missing.map(({ words, wav }) => ({ words, wav }))), 'utf8')
    const script = [
      'Add-Type -AssemblyName System.Speech',
      '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer',
      `$s.SelectVoice('${VOICE}')`,
      '$s.Rate = 0',
      `foreach ($item in (Get-Content -Raw -Encoding UTF8 '${list}' | ConvertFrom-Json)) {`,
      '  $s.SetOutputToWaveFile($item.wav); $s.Speak($item.words) }',
      '$s.Dispose()',
    ].join('\n')
    execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', script], { stdio: 'inherit' })
  }
  return Object.fromEntries(items.filter((item) => existsSync(item.wav)).map((item) => [item.text, { wav: item.wav, seconds: seconds(item.wav) }]))
}
