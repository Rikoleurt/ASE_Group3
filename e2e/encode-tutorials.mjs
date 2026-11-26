// Encodes recorded lessons for the Tutorials page: each <lesson>.webm from record-tutorials.mjs, with its
// narration (<lesson>.cues.json) mixed in at the moment each caption appears, becomes
// frontend/public/tutorials/<lesson>.mp4, plus a poster <lesson>.jpg. Needs ffmpeg on the PATH.
//
//   cd e2e && node encode-tutorials.mjs <recordings dir> [lesson,lesson]
import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const [dir, only] = process.argv.slice(2)
const OUT = resolve(import.meta.dirname, '../frontend/public/tutorials')
const wanted = only?.split(',')
const ffmpeg = (args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: 'inherit' })
const duration = (file) =>
  Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).toString())

for (const file of readdirSync(dir).filter((name) => name.endsWith('.webm'))) {
  const lesson = file.slice(0, -5)
  if (wanted && !wanted.includes(lesson)) continue
  const video = join(dir, file)
  const cuesFile = join(dir, `${lesson}.cues.json`)
  const length = duration(video) // the voice is padded to exactly this (an open-ended pad buffers the whole video)
  const cues = existsSync(cuesFile) ? JSON.parse(readFileSync(cuesFile, 'utf8')) : []
  // Two threads each way: the default (one per core) runs out of memory on small machines.
  const inputs = ['-threads', '2', '-i', video, ...cues.flatMap((cue) => ['-i', cue.wav])]
  const picture = ['-c:v', 'libx264', '-threads', '2', '-preset', 'slow', '-crf', '30', '-r', '15', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
  if (cues.length) {
    // Each caption's voice starts when the caption appears; together they make one mono track.
    const delays = cues.map((cue, i) => `[${i + 1}:a]adelay=${Math.round(cue.at * 1000)}:all=1[a${i}]`)
    const mix = `${cues.map((_, i) => `[a${i}]`).join('')}amix=inputs=${cues.length}:normalize=0:dropout_transition=0,apad=whole_dur=${length}[voice]`
    ffmpeg([...inputs, '-filter_complex', [...delays, mix].join(';'), '-map', '0:v', '-map', '[voice]',
      ...picture, '-c:a', 'aac', '-b:a', '64k', '-ac', '1', '-t', String(length), join(OUT, `${lesson}.mp4`)])
  } else {
    ffmpeg(['-threads', '2', '-i', video, ...picture, '-an', join(OUT, `${lesson}.mp4`)])
  }
  ffmpeg(['-ss', String(Math.round(length * 0.45 * 100) / 100), '-i', video, '-frames:v', '1', '-q:v', '8',
    '-vf', 'scale=800:-1', join(OUT, `${lesson}.jpg`)])
  console.log(`${lesson}: ${cues.length} spoken captions`)
}
