/**
 * 密钥/凭据门禁（与 check-encoding / check-mojibake 同族）。
 *
 * 背景：`E4` 只清了数据库口令，但仓库里仍长期存在真实 API key（`sk-…`）与
 * 明文数据库口令，且**同一把 key 被复制到 45 个已跟踪文件**（含一个被整体提交
 * 进仓库的 `apps/medqc-web - 副本/` 目录）。没有门禁时，这类问题只能靠人偶然发现。
 *
 * 设计原则：
 * 1. **只报位置与掩码，绝不打印完整密钥**——门禁日志会被到处粘贴。
 * 2. **默认扫暂存区**（pre-commit 用），`--all` 扫本应用目录下的全部已跟踪文件。
 * 3. **git 读取失败即硬失败**，不静默通过（与 check-encoding 同一条教训）。
 * 4. 允许清单必须写明理由；不提供"忽略此文件"之类的宽泛开关。
 */

import fs from 'node:fs/promises'
import path from 'node:path'
import { execSync } from 'node:child_process'

const ROOT = process.cwd()

const TEXT_EXTS = new Set([
  '.vue', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json',
  '.md', '.yml', '.yaml', '.html', '.css', '.scss', '.less',
  '.sql', '.py', '.sh', '.ps1', '.txt', '.env', '.ini', '.toml',
])

const SKIP_DIRS = new Set([
  '.git', '.husky', '.tmp', '.release-packages', 'coverage',
  'dist', 'node_modules', '__pycache__',
])

/** 占位符口令：这些不是真实凭据，不报。 */
const PLACEHOLDER_PASSWORDS = new Set([
  'password', 'pass', 'pwd', 'yourpassword', 'your_password', 'xxx', 'xxxx',
  'changeme', 'secret', '123456', 'admin', 'test', 'example', 'mypassword',
  'passw0rd', 'yourpass', 'ci_user', 'user', 'username',
])

/**
 * 允许清单：仅收录**可公开**的示例值与有明确理由的误报。
 * 每条必须有 reason，避免这里变成"忽略一切"的后门。
 */
const ALLOWLIST = [
  {
    pattern: /AKIAIOSFODNN7EXAMPLE/,
    reason: 'AWS 官方文档示例 Access Key ID（非真实凭据）',
  },
  {
    pattern: /sk-(?:your|test|example|xxx|placeholder|dummy)[A-Za-z0-9_-]*/i,
    reason: '明显的占位符形态',
  },
]

const RULES = [
  {
    name: 'api_key_sk',
    // 前置边界避免把 `task-management-…` 这类正常标识符误判为密钥。
    pattern: /(?:^|[^A-Za-z0-9_-])(sk-[A-Za-z0-9]{24,})/g,
    detail: 'OpenAI/DeepSeek 形态的 API key',
  },
  {
    name: 'aws_access_key_id',
    pattern: /(?:^|[^A-Za-z0-9])(AKIA[0-9A-Z]{16})/g,
    detail: 'AWS Access Key ID',
  },
  {
    name: 'github_token',
    pattern: /(?:^|[^A-Za-z0-9_-])((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,})/g,
    detail: 'GitHub token',
  },
  {
    name: 'google_api_key',
    pattern: /(?:^|[^A-Za-z0-9_-])(AIza[0-9A-Za-z_-]{30,})/g,
    detail: 'Google API key',
  },
  {
    name: 'private_key_block',
    pattern: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g,
    detail: '私钥文件内容',
  },
  {
    name: 'database_password',
    pattern: /postgresql(?:\+\w+)?:\/\/([^:/@\s"']+):([^@/\s"']+)@/g,
    detail: '明文数据库口令（口令须由 backend/.env 提供）',
    /** 口令是第 2 个捕获组；命中占位符则不算违规。 */
    passwordGroup: 2,
  },
]

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

const REPO_ROOT = getRepoRoot()

/** null = git 执行失败，与"输出为空"严格区分。 */
function gitOutput(args) {
  try {
    return execSync(`git ${args}`, {
      cwd: REPO_ROOT,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
      // 本仓库已跟踪文件达数万个（含被误提交的副本目录与 vendored venv），
      // `ls-files` 输出远超 execSync 默认 1MB 缓冲——缓冲不足会抛错，被下面的
      // catch 当成"git 执行失败"，从而让门禁硬失败。这里显式放大。
      maxBuffer: 64 * 1024 * 1024,
    })
  } catch {
    return null
  }
}

/**
 * 注意：**不做应用目录过滤**。密钥泄露不是"本应用的问题"——实测最严重的一处
 * 在仓库根的 `REAL_LLM_QC_VERIFICATION_REPORT.md`，另一处在与本应用**同级**的
 * `apps/medqc-web - 副本/` 目录。任何"仅限本应用"的过滤都会漏掉这两处。
 */
function toAbsolute(list) {
  return list.map((rel) => path.join(REPO_ROOT, rel))
}

function filesFromGit(args) {
  const out = gitOutput(args)
  if (out === null) return null
  return toAbsolute(
    out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
  )
}

/** 掩码：保留前 4 位与长度，其余打码。绝不返回完整值。 */
function mask(value) {
  if (value.length <= 6) return '*'.repeat(value.length)
  return `${value.slice(0, 4)}${'*'.repeat(Math.min(value.length - 4, 12))}(len=${value.length})`
}

function allowed(value) {
  return ALLOWLIST.some((entry) => entry.pattern.test(value))
}

async function collectFiles(mode) {
  if (mode === 'all') {
    // 全仓已跟踪文件（不按应用过滤，理由见 toAbsolute 注释）
    const tracked = filesFromGit('ls-files')
    if (tracked === null) {
      throw new Error('all 模式无法读取已跟踪文件清单（git 执行失败），禁止静默通过')
    }
    return tracked
  }
  const staged = filesFromGit('diff --cached --name-only --diff-filter=ACMRTUXB')
  if (staged === null) {
    throw new Error(
      'staged 模式无法读取 git 暂存区（git 执行失败，或当前目录不是 git 仓库、索引不可读）；禁止静默通过'
    )
  }
  return staged
}

async function scanFile(abs) {
  const rel = toPosix(path.relative(REPO_ROOT, abs))
  let text
  try {
    text = await fs.readFile(abs, 'utf8')
  } catch {
    return []
  }
  const issues = []
  const lines = text.split(/\r?\n/)
  for (const rule of RULES) {
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index]
      rule.pattern.lastIndex = 0
      let match
      while ((match = rule.pattern.exec(line)) !== null) {
        const value = rule.passwordGroup
          ? match[rule.passwordGroup]
          : match[1]
        if (!value) continue
        if (rule.passwordGroup && PLACEHOLDER_PASSWORDS.has(value.toLowerCase())) continue
        if (rule.passwordGroup && value.startsWith('$') ) continue
        if (allowed(value)) continue
        issues.push(
          `${rel}:${index + 1}: ${rule.name} — ${rule.detail}（${mask(value)}）`
        )
      }
    }
  }
  return issues
}

async function main() {
  const mode = process.argv.includes('--all') ? 'all' : 'staged'
  const candidates = await collectFiles(mode)
  const files = []
  for (const abs of candidates) {
    if (!TEXT_EXTS.has(path.extname(abs).toLowerCase())) continue
    try {
      const st = await fs.stat(abs)
      if (st.isFile()) files.push(abs)
    } catch {
      // 已删除/移动的文件跳过
    }
  }

  const issues = []
  for (const abs of files) {
    issues.push(...(await scanFile(abs)))
  }

  if (issues.length > 0) {
    console.error(`secret check failed: ${issues.length} issue(s) in ${files.length} file(s)`)
    for (const line of issues.slice(0, 200)) console.error(`- ${line}`)
    if (issues.length > 200) console.error(`- …其余 ${issues.length - 200} 条省略`)
    console.error('')
    console.error('处理方式：源码与文档中一律改为从环境变量读取（backend/.env 或 CI 变量）；')
    console.error('注意：从 HEAD 删除≠从历史删除，已提交的真实密钥必须轮换。')
    process.exit(1)
  }

  if (files.length === 0) {
    console.log(
      mode === 'staged'
        ? 'secret check passed (staged): 本次暂存区没有本应用的文本文件，无需检查'
        : 'secret check passed (all): 没有可检查的已跟踪文本文件'
    )
    return
  }
  console.log(`secret check passed (${mode}): ${files.length} text file(s) scanned`)
}

main().catch((err) => {
  console.error('secret check crashed:', err)
  process.exit(2)
})
