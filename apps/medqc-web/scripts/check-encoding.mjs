import fs from 'node:fs/promises'
import path from 'node:path'
import { execSync } from 'node:child_process'

const ROOT = process.cwd()

const TEXT_EXTS = new Set([
  '.vue',
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.json',
  '.md',
  '.yml',
  '.yaml',
  '.html',
  '.css',
  '.scss',
  '.less',
  '.sql',
  '.py',
  '.sh',
  '.ps1',
])

const SKIP_DIRS = new Set([
  '.git',
  '.husky',
  '.tmp',
  '.release-packages',
  'coverage',
  'dist',
  'node_modules',
  '__pycache__',
])

const decoder = new TextDecoder('utf-8', { fatal: true })

function toPosix(p) {
  return p.split(path.sep).join('/')
}

function getRepoRoot() {
  try {
    const out = execSync('git rev-parse --show-toplevel', {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    })
    return out.trim() || ROOT
  } catch {
    return ROOT
  }
}

// 所有 git 调用统一在仓库根执行：git ls-files 在子目录下输出 cwd 相对路径，
// 而 git diff --cached --name-only 输出仓库根相对路径；混用会产生双重前缀或
// 找不到文件，导致门禁静默空转（历史故障）。这里统一成「仓库根相对」。
const REPO_ROOT = getRepoRoot()
const SELF_PATHSPEC = toPosix(path.relative(REPO_ROOT, ROOT)) || '.'

function toAbsolute(relPaths) {
  return relPaths
    .map((rel) => path.join(REPO_ROOT, rel))
    .filter((abs) => abs === ROOT || abs.startsWith(ROOT + path.sep))
}

function gitOutput(args) {
  try {
    return execSync(`git ${args}`, {
      cwd: REPO_ROOT,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    })
  } catch {
    return ''
  }
}

function toAbsoluteFromGit(args) {
  const out = gitOutput(args)
  return toAbsolute(
    out
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
  )
}

function getStagedFiles() {
  return toAbsoluteFromGit('diff --cached --name-only --diff-filter=ACMRTUXB')
}

function getTrackedFiles() {
  // 限定本应用目录，避免把 monorepo 其它应用的问题算到本门禁头上。
  return toAbsoluteFromGit(`ls-files -- ${SELF_PATHSPEC}`)
}

async function walk(dir, out) {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue
      await walk(path.join(dir, entry.name), out)
      continue
    }
    if (!entry.isFile()) continue
    const ext = path.extname(entry.name).toLowerCase()
    if (!TEXT_EXTS.has(ext)) continue
    out.push(path.join(dir, entry.name))
  }
}

async function existingTextFiles(candidates) {
  const files = []
  for (const abs of candidates) {
    if (!TEXT_EXTS.has(path.extname(abs).toLowerCase())) continue
    try {
      const st = await fs.stat(abs)
      if (st.isFile()) files.push(abs)
    } catch {
      // ignore deleted/moved files
    }
  }
  return files
}

async function collectFiles(mode) {
  if (mode === 'all') {
    // 只扫「仓库内容」（已跟踪文件）：工作目录树包含 .release-packages 等被
    // gitignore 的本地发布快照，把它们算作存量债会让该门禁永远红、无人理会。
    const tracked = getTrackedFiles()
    if (tracked.length === 0) {
      // git 不可用时退回目录遍历
      const files = []
      await walk(ROOT, files)
      return files
    }
    return existingTextFiles(tracked)
  }

  const candidates = getStagedFiles()
  const files = await existingTextFiles(candidates)
  const textCandidates = candidates.filter((abs) =>
    TEXT_EXTS.has(path.extname(abs).toLowerCase())
  )
  if (textCandidates.length > 0 && files.length === 0) {
    // 静默空转是危险的：此前路径解析失效时该门禁永远报 passed。
    throw new Error(
      `staged 模式解析到 ${textCandidates.length} 个暂存文本文件，但 0 个可读；` +
        '路径解析可能失效，禁止静默通过'
    )
  }
  return files
}

function hasUtf8Bom(buffer) {
  return buffer.length >= 3 && buffer[0] === 0xef && buffer[1] === 0xbb && buffer[2] === 0xbf
}

async function main() {
  const mode = process.argv.includes('--all') ? 'all' : 'staged'
  const files = await collectFiles(mode)

  const issues = []

  for (const abs of files) {
    const rel = toPosix(path.relative(ROOT, abs))
    const buf = await fs.readFile(abs)

    if (hasUtf8Bom(buf)) {
      issues.push(`${rel}: UTF-8 BOM found (use UTF-8 without BOM)`)
    }

    let text
    try {
      text = decoder.decode(buf)
    } catch {
      issues.push(`${rel}: not valid UTF-8`)
      continue
    }

    if (text.includes('\uFFFD')) {
      issues.push(`${rel}: contains replacement char (U+FFFD), possible mojibake`)
    }

    if (text.includes('\u0000')) {
      issues.push(`${rel}: contains NUL byte, possible wrong encoding/binary`)
    }
  }

  if (issues.length > 0) {
    console.error(`encoding check failed: ${issues.length} issue(s)`)
    for (const line of issues) {
      console.error(`- ${line}`)
    }
    process.exit(1)
  }

  console.log(`encoding check passed (${mode}): ${files.length} text file(s) scanned`)
}

main().catch((err) => {
  console.error('encoding check crashed:', err)
  process.exit(2)
})
