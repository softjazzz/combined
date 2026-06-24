/**
 * 规则分段器：基于标题与分页样式将原文切分为段，并返回原文绝对坐标
 * 该模块不依赖 llmService，避免循环依赖
 */

export interface DocSegment {
  title: string
  startIndex: number
  endIndex: number
  typeCode?: string // 可选：admission_record, first_progress_note, ...
}

// 常见标题关键字及映射（可扩展）
const TITLE_PATTERNS: Array<{ re: RegExp; typeCode: string }> = [
  { re: /入\s*院\s*记\s*录|入院记录/, typeCode: 'admission_record' },
  { re: /首次病程记录|术后首次病程记录/, typeCode: 'first_progress_note' },
  { re: /病程记录|查房记录|主治医师查房记录|主任医师查房记录/, typeCode: 'daily_progress_note' },
  { re: /术前小结|术前讨论|术前主刀医师查房记录/, typeCode: 'preoperative_summary' },
  { re: /手术记录|术中记录/, typeCode: 'operation_record' },
  { re: /出院记录|出院小结/, typeCode: 'discharge_record' },
  { re: /阶段小结/, typeCode: 'stage_summary' },
]

// 页眉/页脚与分页标记（被剔除）
const HEADER_FOOTER_LINE = new RegExp(
  [
    '^===\\s*第\\d+页\\s*===\\s*$', // === 第n页 ===
    '^第\\s*\\d+\\s*页/共\\s*\\d+\\s*页$', // 第n页/共m页
    '^第\\s*\\(\\d+\\)\\s*页$', // 第(n)页
    '^(?:.{0,10}医院|病\\s*程\\s*记\\s*录)\\s*$', // 医院名/病 程 记 录 独立行
    '^(?:科室|姓名|性别|年龄|住院号)[:：].*$', // 头部信息行
  ].join('|'),
  'u',
)

function isHeaderFooterLine(line: string): boolean {
  return HEADER_FOOTER_LINE.test(line.trim())
}

/** 将文本按行扫描，识别标题行，生成原文起止索引 */
export function segmentMedicalDocument(text: string): DocSegment[] {
  const segments: DocSegment[] = []
  if (!text) return segments

  const lines = text.split('\n')
  const lineStartOffsets: number[] = []
  {
    let acc = 0
    for (const line of lines) {
      lineStartOffsets.push(acc)
      acc += line.length + 1 // +1 for \n
    }
  }

  const titleLineIdx: Array<{ idx: number; typeCode?: string; title: string }> = []

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.trim()
    if (!line) continue
    // 跳过页眉/脚
    if (isHeaderFooterLine(line)) continue

    for (const { re, typeCode } of TITLE_PATTERNS) {
      if (re.test(line)) {
        titleLineIdx.push({ idx: i, typeCode, title: raw })
        break
      }
    }
  }

  if (titleLineIdx.length === 0) return segments

  for (let k = 0; k < titleLineIdx.length; k++) {
    const cur = titleLineIdx[k]
    const next = titleLineIdx[k + 1]
    // 去除起止端的页眉/脚行
    let s = cur.idx
    while (s < lines.length && isHeaderFooterLine(lines[s])) s++
    let e = next ? next.idx : lines.length
    while (e - 1 > s && isHeaderFooterLine(lines[e - 1])) e--

    const start = lineStartOffsets[s]
    const end = lineStartOffsets[e] ?? text.length

    segments.push({
      title: lines[cur.idx].trim(),
      startIndex: Math.max(0, start),
      endIndex: Math.max(Math.min(text.length, end), start),
      typeCode: cur.typeCode,
    })
  }

  return segments
}

/** 在分段结果中，找到与给定坐标最相近且同类的段 */
export function findNearestSegment(
  segments: DocSegment[],
  approxStart: number,
  typeCode?: string,
): DocSegment | null {
  if (!segments.length) return null
  let best: DocSegment | null = null
  let bestScore = Infinity
  for (const seg of segments) {
    const dist = Math.abs(seg.startIndex - approxStart)
    const penalty = typeCode && seg.typeCode && seg.typeCode !== typeCode ? 10000 : 0
    const score = dist + penalty
    if (score < bestScore) {
      bestScore = score
      best = seg
    }
  }
  return best
}
