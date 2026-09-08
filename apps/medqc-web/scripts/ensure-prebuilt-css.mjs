import { existsSync, readdirSync, statSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const appRoot = resolve(__dirname, '..')
const output = resolve(appRoot, 'src/styles/index.prebuilt.css')

const styleRoot = resolve(appRoot, 'src/styles')
const latestSourceTime = Math.max(
  ...readdirSync(styleRoot)
    .filter((name) => /\.(css|less)$/.test(name) && name !== 'index.prebuilt.css')
    .map((name) => statSync(resolve(styleRoot, name)).mtimeMs),
  statSync(resolve(appRoot, 'tailwind.config.js')).mtimeMs,
)

if (existsSync(output) && statSync(output).mtimeMs >= latestSourceTime) {
  console.log('[predev] using existing prebuilt css:', output)
  process.exit(0)
}

const tailwindBin = resolve(appRoot, 'node_modules/tailwindcss/lib/cli.js')

execFileSync(
  process.execPath,
  [
    tailwindBin,
    '-i',
    './src/styles/index.css',
    '-o',
    './src/styles/index.prebuilt.css',
    '--minify',
  ],
  {
    cwd: appRoot,
    stdio: 'inherit',
  },
)
