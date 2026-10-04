// 模型回答的轻量 Markdown 结构化解析：只识别段落、标题、列表、加粗与行内代码，
// 结果交给 Vue 模板按文本节点渲染，不生成 HTML，模型输出无法注入标签。

export interface AnswerInline {
  text: string
  bold?: boolean
  code?: boolean
}

export type AnswerBlock =
  | { type: 'heading'; inline: AnswerInline[] }
  | { type: 'paragraph'; inline: AnswerInline[] }
  | { type: 'list'; ordered: boolean; items: AnswerInline[][] }

const HEADING = /^\s{0,3}#{1,6}\s+(.*)$/
const BULLET = /^\s*[-*•·]\s+(.*)$/
const ORDERED = /^\s*\d{1,2}[.、)）]\s*(.*)$/
const TABLE_RULE = /^\s*\|?\s*:?-{3,}/

export function parseInline(text: string): AnswerInline[] {
  const result: AnswerInline[] = []
  // 按 **加粗** 与 `代码` 切分；未闭合的标记按原文保留。
  const pattern = /\*\*([^*]+?)\*\*|`([^`]+?)`/g
  let last = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > last) result.push({ text: text.slice(last, index) })
    if (match[1] !== undefined) result.push({ text: match[1], bold: true })
    else result.push({ text: match[2], code: true })
    last = index + match[0].length
  }
  if (last < text.length) result.push({ text: text.slice(last) })
  return result.length ? result : [{ text: '' }]
}

export function parseAnswer(text: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = []
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length)
      blocks.push({ type: 'paragraph', inline: parseInline(paragraph.join('\n')) })
    paragraph = []
  }
  for (const raw of text.replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim() || TABLE_RULE.test(line)) {
      flush()
      continue
    }
    const heading = HEADING.exec(line)
    const bullet = BULLET.exec(line)
    const ordered = bullet ? null : ORDERED.exec(line)
    if (heading) {
      flush()
      blocks.push({ type: 'heading', inline: parseInline(heading[1]) })
    } else if (bullet || ordered) {
      flush()
      const isOrdered = !!ordered
      const content = parseInline((bullet || ordered)![1])
      const previous = blocks.at(-1)
      if (previous?.type === 'list' && previous.ordered === isOrdered) previous.items.push(content)
      else blocks.push({ type: 'list', ordered: isOrdered, items: [content] })
    } else {
      // 表格行去掉竖线后按段落展示，避免原样显示 | 分隔符。
      paragraph.push(
        line.startsWith('|')
          ? line
              .replace(/^\||\|$/g, '')
              .split('|')
              .map((cell) => cell.trim())
              .join('　')
          : line,
      )
    }
  }
  flush()
  return blocks
}
