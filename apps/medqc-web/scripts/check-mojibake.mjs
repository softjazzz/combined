import fs from 'node:fs/promises'
import path from 'node:path'

const ROOT = process.cwd()

const TEXT_EXTS = new Set([
  '.vue',
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.py',
  '.md',
  '.json',
  '.yml',
  '.yaml',
  '.sql',
  '.html',
  '.css',
  '.less',
  '.scss'
])

const SKIP_DIRS = new Set([
  'node_modules',
  'dist',
  'coverage',
  '.git',
  '.idea',
  '.vscode',
  '.tmp',
  '__pycache__'
])

const MOJIBAKE_TOKENS = [
  '鍖',
  '鐥',
  '闄',
  '锛',
  '櫌',
  '涓�',
  '鏈坄',
  '鐪',
  '甯',
  '鍏ラ櫌',
  '鍑洪櫌'
]

const TAG_BROKEN_RE = /\?\/(?:span|div|th|td|b|u|h[1-6])>|\?br\/>/i
const REPLACEMENT_CHAR_RE = /\uFFFD/
const NUL_CHAR_RE = /\u0000/

function toPosix(p) {
  return p.split(path.sep).join('/')
}

async function walk(dir, out) {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  for (const entry of entries) {
    const abs = path.join(dir, entry.name)
    const rel = path.relative(ROOT, abs)
    const relPosix = toPosix(rel)
    if (!rel || relPosix === '') continue
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue
      await walk(abs, out)
      continue
    }
    if (!entry.isFile()) continue
    if (!TEXT_EXTS.has(path.extname(entry.name).toLowerCase())) continue
    out.push(abs)
  }
}

async function loadAllowlist() {
  const configPath = path.join(ROOT, 'scripts', 'mojibake-allowlist.json')
  try {
    const raw = await fs.readFile(configPath, 'utf8')
    const parsed = JSON.parse(raw)
    const items = Array.isArray(parsed?.allowlist) ? parsed.allowlist : []
    return new Set(items.map(toPosix))
  } catch {
    return new Set()
  }
}

function findLineHits(content, relPath) {
  const lines = content.split(/\r?\n/)
  const hits = []

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    let reasons = []

    if (REPLACEMENT_CHAR_RE.test(line)) reasons.push('replacement-char')
    if (TAG_BROKEN_RE.test(line)) reasons.push('broken-tag')

    const tokenCount = MOJIBAKE_TOKENS.reduce((acc, token) => {
      let idx = line.indexOf(token)
      let c = 0
      while (idx !== -1) {
        c += 1
        idx = line.indexOf(token, idx + token.length)
      }
      return acc + c
    }, 0)

    if (tokenCount >= 2) reasons.push(`mojibake-token(${tokenCount})`)

    if (reasons.length > 0) {
      hits.push({
        file: relPath,
        line: i + 1,
        reasons,
        text: line.slice(0, 180)
      })
    }
  }

  return hits
}

async function main() {
  const allowlist = await loadAllowlist()
  const files = []
  await walk(ROOT, files)

  const allHits = []

  for (const abs of files) {
    const rel = toPosix(path.relative(ROOT, abs))
    if (rel === 'scripts/check-mojibake.mjs') continue
    if (allowlist.has(rel)) continue
    let content = ''
    try {
      content = await fs.readFile(abs, 'utf8')
    } catch {
      continue
    }
    if (NUL_CHAR_RE.test(content)) {
      // likely UTF-16 / binary-like content, skip from this UTF-8 heuristic check
      continue
    }
    const hits = findLineHits(content, rel)
    if (hits.length) allHits.push(...hits)
  }

  if (allHits.length === 0) {
    console.log('mojibake check passed: no suspicious lines found')
    process.exit(0)
  }

  const byFile = new Map()
  for (const hit of allHits) {
    if (!byFile.has(hit.file)) byFile.set(hit.file, [])
    byFile.get(hit.file).push(hit)
  }

  console.error(`mojibake check failed: ${byFile.size} file(s), ${allHits.length} suspicious line(s)`)
  for (const [file, hits] of byFile.entries()) {
    console.error(`\n- ${file}`)
    for (const h of hits.slice(0, 20)) {
      console.error(`  L${h.line} [${h.reasons.join(', ')}] ${h.text}`)
    }
    if (hits.length > 20) {
      console.error(`  ... ${hits.length - 20} more line(s)`)
    }
  }

  process.exit(1)
}

main().catch(err => {
  console.error('mojibake check crashed:', err)
  process.exit(2)
})
