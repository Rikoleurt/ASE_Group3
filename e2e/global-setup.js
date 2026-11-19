// Runs once before the tests: the journeys need the database, the trained sign
// reader and the tablet fixture. A missing piece fails the run with a reason,
// instead of letting the tablet journey pass on the generic fallback model.
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { deleteLeftoverAccounts } from './helpers/database.js'
import { FIXTURE, FIXTURE_DIR, SECRETS, SOURCE } from './helpers/fixture.js'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const MODELS = ['models/linear_a_signs.pt', 'models/linear_a_classifier.pt', 'models/linear_a_classifier.json']

export default async function globalSetup() {
  const missing = MODELS.filter((path) => !existsSync(new URL(`../${path}`, import.meta.url)))
  if (missing.length) {
    throw new Error(`The trained sign reader is missing (${missing.join(', ')}). `
      + 'Run `uv run --project backend python scripts/fetch_models.py --tag signs-v1` first.')
  }

  try {
    await deleteLeftoverAccounts()
  } catch (error) {
    throw new Error(`MySQL is not reachable (${error.message}). Start it with \`docker compose up -d --wait mysql\`.`)
  }

  // The app accepts PNG and JPEG; the repository keeps HT 13 as WebP.
  mkdirSync(FIXTURE_DIR, { recursive: true })
  writeFileSync(SECRETS, '')
  execFileSync('uv', ['run', '--project', 'backend', ...(process.env.CI ? ['--no-sync'] : []), 'python', '-c',
    'import sys; from PIL import Image; Image.open(sys.argv[1]).convert("RGB").save(sys.argv[2], "PNG")',
    SOURCE, FIXTURE], { cwd: ROOT, stdio: 'inherit' })
}
