// Runs before every test file: shared caches start empty in each test.
import { afterEach } from 'vitest'
import { forgetCatalogue } from './composables/useCatalogue'

afterEach(() => forgetCatalogue())
