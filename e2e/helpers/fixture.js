// The tablet uploaded by the analysis journey: HT 13, the drawing the HT 13 demo
// already ships (backend/app/static/ht13.webp), converted to PNG by global-setup.js.
// From SigLA (E. Salgarella & S. Castellan) via lineara.eu (M. Navarre), CC BY-NC-SA 4.0;
// see backend/app/static/ATTRIBUTION.md.
// With the signs-v1 reader it shows a KU-RO total whose fractions do not balance;
// the tests check that a verdict is shown, not which one.
import { fileURLToPath } from 'node:url'

export const SOURCE = fileURLToPath(new URL('../../backend/app/static/ht13.webp', import.meta.url))
export const FIXTURE_DIR = fileURLToPath(new URL('../.fixtures/', import.meta.url))
export const FIXTURE = `${FIXTURE_DIR}ht13.png`
// Each test account's random password, so redact_diagnostics.py can remove it from
// traces before CI uploads them. Kept out of test-results/, which is uploaded.
export const SECRETS = `${FIXTURE_DIR}secrets.txt`
