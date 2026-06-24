import { existsSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const appRoot = resolve(__dirname, '..')
const output = resolve(appRoot, 'src/styles/index.prebuilt.css')

if (existsSync(output)) {
  console.log('[predev] using existing prebuilt css:', output)
  process.exit(0)
}

const tailwindBin = process.platform === 'win32'
  ? resolve(appRoot, 'node_modules/.bin/tailwindcss.cmd')
  : resolve(appRoot, 'node_modules/.bin/tailwindcss')

execFileSync(
  tailwindBin,
  ['-i', './src/styles/index.css', '-o', './src/styles/index.prebuilt.css', '--minify'],
  {
    cwd: appRoot,
    stdio: 'inherit',
  },
)
