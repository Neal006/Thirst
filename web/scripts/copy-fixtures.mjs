// Copies the backend's API fixtures into the web app (plan 6.1.b): npm run fixtures.
// The fixtures are produced by the real engine (make fixtures), so the mocks can never drift from
// the API without a test failing. Run it after the engine output changes and commit the result.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = resolve(here, '..', '..', 'tests', 'fixtures')
const target = resolve(here, '..', 'src', 'api', 'mocks', 'fixtures')

if (!existsSync(source)) {
  console.error(`Fixtures folder not found: ${source}`)
  process.exit(1)
}
mkdirSync(target, { recursive: true })
const wanted = readdirSync(source).filter((name) => name.endsWith('_response.json'))
if (wanted.length === 0) {
  console.error('No *_response.json fixtures found. Run `make fixtures` first.')
  process.exit(1)
}
for (const name of wanted) copyFileSync(join(source, name), join(target, name))
console.log(`Copied ${wanted.length} fixtures to ${target}`)
