import { execFileSync } from 'node:child_process'
import { posix } from 'node:path'
import { pathToFileURL } from 'node:url'

const webDir = 'apps/medqc-web/'
const srcDir = webDir + 'src/'
const workstationDir = srcDir + 'views/workstation-v4/'
const protectedRoots = new Set(['.', 'apps/medqc-web', 'apps/medqc-web/backend'])
const rootConfigs = new Set(['eslint.config.js', 'vite.config.mjs', 'index.html', 'dev-env.sh'])
const logicModules = new Set([
  ...['caseRecordKey.ts', 'qcTaskTime.ts', 'clinicalTime.ts'].map(name => srcDir + 'utils/' + name),
  ...['caseRecordKey.ts', 'qcTaskTime.ts', 'clinicalTime.ts'].map(name => workstationDir + 'utils/' + name),
])
const gitReadEnv = { ...process.env }
// 从调用目录发现工作树，并保留 hook 用于定位暂存区的 GIT_INDEX_FILE。
delete gitReadEnv.GIT_DIR
delete gitReadEnv.GIT_WORK_TREE

function isRootArtifact(file) {
  const name = posix.basename(file)
  return protectedRoots.has(posix.dirname(file)) &&
    !rootConfigs.has(name) &&
    !/^requirements.*\.txt$/i.test(name) &&
    /(?:\.(?:py|js|sh|ps1|csv|xlsx|txt|log|html|pdf)|_(?:REPORT|SUMMARY)\.md)$/i.test(name)
}

function isWebArtifact(file) {
  return file.startsWith(webDir) &&
    (/(?:^|\/)\.(?:logs|tmp)-/.test(file) || /\.(?:legacy\.vue|vue\.ts)$/i.test(file))
}

function hasIgnoreComment(line) {
  // 先跳过字符串，避免把用户可见文案当作豁免。
  const tokens = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|<!--.*?-->|\/\*.*?\*\/|\/\/.*|(?:^|\s)#\s*hygiene-ignore:.*/g
  for (const [token] of line.matchAll(tokens)) {
    const directive = token.match(/^\s*(?:<!--|\/\*|\/\/|#)\s*hygiene-ignore:\s*(.*)$/)
    if (directive?.[1].replace(/(?:\*\/|-->)\s*$/, '').trim()) return true
  }
  return false
}

function hasHexDeclaration(line, inline = false) {
  const source = line
    .replace(/url\(\s*(?:"[^"]*"|'[^']*'|[^)]*)\s*\)/gi, '')
    .replace(/&#(?:x[0-9a-f]+|\d+);/gi, '')
  const declarations = /(?:^|[;{])\s*['"]?[$\w-]+['"]?\s*:\s*([^;{}<>]+?)(?=[;}]|$)/g

  for (const [, value] of source.matchAll(declarations)) {
    const colorValue = inline ? value : value.replace(/"[^"]*"|'[^']*'/g, '')
    if (/#[\da-f]{3,8}\b/i.test(colorValue)) return true
  }
  return false
}

function hasHardCodedColor(line) {
  const styleAttrs = /(?:^|\s)(?::style|v-bind:style|style)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi
  for (const [, doubleQuoted, singleQuoted] of line.matchAll(styleAttrs)) {
    if (hasHexDeclaration(doubleQuoted ?? singleQuoted, true)) return true
  }
  return hasHexDeclaration(line.replace(/<\/?style\b[^>]*>/gi, ''))
}

function* contiguousBlocks(lines) {
  let block = []
  for (const line of lines) {
    if (block.length && line.lineNumber !== block.at(-1).lineNumber + 1) {
      yield block
      block = []
    }
    block.push(line)
  }
  if (block.length) yield block
}

function analyzeSource(file, lines, newFile) {
  const violations = []
  const checkStyles = file.startsWith(workstationDir) || (newFile && /\.(?:vue|css|scss)$/i.test(file))
  const checkLogic = !logicModules.has(file)

  for (const block of contiguousBlocks(lines)) {
    const add = (line, message) => {
      if (!hasIgnoreComment(line.text)) violations.push({ file, lineNumber: line.lineNumber, message })
    }
    for (const line of block) {
      if (checkStyles && (line.text.includes('--workstation-') || hasHardCodedColor(line.text))) {
        add(line, '样式请使用 --mq-* 变量，避免硬编码色值和旧 --workstation-* 变量')
      }
      if (/\b(?:Modal|window)\s*\.\s*confirm\s*\(/.test(line.text)) {
        add(line, '请使用工作台统一确认交互')
      }
      if (checkLogic && /\b(?:function\s+formatDate|const\s+formatDateTime)\b/.test(line.text)) {
        add(line, '请复用 qcTaskTime.ts 中的时间格式化逻辑')
      }
    }

    // 支持跨行写法，但不能跨过未修改的行来组成违规。
    const source = block.map(line => line.text).join('\n')
    const lineAt = index => block[source.slice(0, index).split('\n').length - 1]
    const dateInputs = /<input(?=\s|\/?>)(?:[^"'<>]|"[^"]*"|'[^']*')*?(\s+type\s*=\s*(['"])date\2)/gi
    for (const match of source.matchAll(dateInputs)) {
      const typeOffset = match[0].lastIndexOf(match[1]) + match[1].search(/\S/)
      add(lineAt(match.index + typeOffset), '日期输入请使用 DatePicker')
    }
    if (!checkLogic) continue
    const arrays = /\bJSON\s*\.\s*stringify\s*\(\s*\[([^[\]]*(?:\[[^[\]]*\][^[\]]*)*)\]/g
    for (const match of source.matchAll(arrays)) {
      if (['institute', 'patient', 'visit'].every(key => match[1].toLowerCase().includes(key))) {
        add(lineAt(match.index), '病例三键请复用 caseRecordKey.ts 中的生成方法')
      }
    }
  }

  return violations.sort((left, right) => left.lineNumber - right.lineNumber)
}

/**
 * Git 路径相对仓库根目录。addedLinesByFile 为路径到新增行的 Map，
 * 每行包含 lineNumber（目标文件行号）和 text。
 */
export function analyzeDiff({ addedFiles, addedLinesByFile }) {
  const violations = []
  const newFiles = new Set(addedFiles)
  for (const file of newFiles) {
    const rootArtifact = isRootArtifact(file)
    if (!rootArtifact && !isWebArtifact(file)) continue
    if (addedLinesByFile.get(file)?.some(line => hasIgnoreComment(line.text))) continue
    const message = rootArtifact
      ? '临时脚本和过程报告请放到本地未跟踪的 .tmp/ 目录'
      : '请勿提交临时日志、临时文件、旧 Vue 文件或 Vue TS 镜像'
    violations.push({ file, message })
  }
  for (const [file, lines] of addedLinesByFile) {
    if (!file.startsWith(srcDir) || /(?:^|\/)__tests__\/|\.(?:spec|test)\./i.test(file)) continue
    violations.push(...analyzeSource(file, lines, newFiles.has(file)))
  }
  return violations
}

function git(args, cwd) {
  return execFileSync('git', args, {
    cwd,
    env: gitReadEnv,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

function readChangedPaths(statusList) {
  const fields = statusList.split('\0')
  const addedFiles = []
  const patchPaths = new Set()
  for (let index = 0; index < fields.length - 1;) {
    const status = fields[index++][0]
    const firstPath = fields[index++]
    const file = status === 'R' || status === 'C' ? fields[index++] : firstPath
    if (status === 'A') addedFiles.push(file)
    if (file.startsWith(srcDir) || (status === 'A' && (isRootArtifact(file) || isWebArtifact(file)))) {
      patchPaths.add(file)
      // 保留重命名前的路径，让 Git 只输出真正新增的行。
      if (status === 'R') patchPaths.add(firstPath)
    }
  }
  return { addedFiles, patchPaths }
}

function patchDestination(header) {
  if (header.startsWith('b/')) return header.slice(2).split('\t', 1)[0]
  // core.quotePath=false 保留 Unicode，Git 仍会为引号、反斜杠和控制字符加引号。
  const quoted = header.match(/^"b\/(.*)"(?:\t.*)?$/)
  const escapes = { a: '\x07', b: '\b', f: '\f', n: '\n', r: '\r', t: '\t', v: '\v' }
  return quoted?.[1].replace(/\\([0-7]{3}|.)/g, (_, code) =>
    escapes[code] ?? (code.length === 3 ? String.fromCharCode(parseInt(code, 8)) : code))
}

function readAddedLines(patch) {
  const files = new Map()
  let file
  let lineNumber
  for (const line of patch.split('\n')) {
    if (line.startsWith('diff --git ')) {
      file = undefined
      lineNumber = undefined
    } else if (lineNumber === undefined && line.startsWith('+++ ')) {
      file = patchDestination(line.slice(4))
    } else if (line.startsWith('@@ ')) {
      const hunk = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
      lineNumber = hunk ? Number(hunk[1]) : undefined
    } else if (file && lineNumber !== undefined && line.startsWith('+')) {
      if (!files.has(file)) files.set(file, [])
      files.get(file).push({ lineNumber, text: line.slice(1) })
      lineNumber += 1
    } else if (lineNumber !== undefined && line.startsWith(' ')) {
      lineNumber += 1
    }
  }
  return files
}

function main(args) {
  const staged = args.length === 1 && args[0] === '--staged'
  const ref = args.length === 2 && args[0] === '--diff-base' ? args[1] : ''
  if (!staged && !ref) {
    console.error('用法：node check-repo-hygiene.mjs --staged | --diff-base <git-ref>')
    return 2
  }
  const root = git(['rev-parse', '--show-toplevel']).trimEnd()
  let range = '--cached'
  if (ref) {
    try {
      const base = git(['rev-parse', '--verify', '--end-of-options', ref + '^{commit}'], root).trim()
      range = base + '...HEAD'
    } catch {
      console.error('无法解析差异基准 ' + JSON.stringify(ref) + '，请确认 ref 存在并已抓取所需历史。')
      return 2
    }
  }
  const diff = ['--no-relative', '--find-renames', '--no-ext-diff', '--no-textconv', range]
  const changes = git(['diff', '--name-status', '-z', '--diff-filter=ACMRT', ...diff, '--'], root)
  const { addedFiles, patchPaths } = readChangedPaths(changes)
  const patch = patchPaths.size ? git([
    '--literal-pathspecs', '-c', 'core.quotePath=false', 'diff',
    '--patch', '--unified=0', '--no-color', '--src-prefix=a/', '--dst-prefix=b/', '--submodule=short',
    ...diff, '--', ...patchPaths,
  ], root) : ''
  const violations = analyzeDiff({ addedFiles, addedLinesByFile: readAddedLines(patch) })
  for (const { file, lineNumber, message } of violations) {
    const location = lineNumber === undefined ? file : file + ':' + lineNumber
    console.error(location + ' ' + message)
  }
  if (violations.length) return 1
  console.log('仓库增量卫生检查通过。')
  return 0
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    process.exitCode = main(process.argv.slice(2))
  } catch (error) {
    console.error('仓库增量卫生检查无法运行。' + (error.stderr?.trim() || error.message))
    process.exitCode = 2
  }
}
