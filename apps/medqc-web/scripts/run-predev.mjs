import { existsSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const appRoot = resolve(__dirname, '..')

function runNodeScript(relativePath) {
  execFileSync(process.execPath, [resolve(appRoot, relativePath)], {
    cwd: appRoot,
    stdio: 'inherit',
  })
}

const prepareRuntime = resolve(appRoot, 'scripts/prepare-dev-runtime.cjs')
if (existsSync(prepareRuntime)) {
  runNodeScript('scripts/prepare-dev-runtime.cjs')
}

runNodeScript('scripts/ensure-prebuilt-css.mjs')
