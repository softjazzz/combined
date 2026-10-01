export type EvidenceQuoteLocation =
  | { state: 'matched'; range: { start: number; end: number } }
  | { state: 'ambiguous' | 'not_found' | 'no_content' | 'no_excerpt' | 'truncated'; range: null }

/** 授权摘录会合并空白；只规范化空白，并保留每个 UTF-16 字符对应的原文坐标。 */
function mappedText(value: string) {
  let text = ''
  const starts: number[] = []
  const ends: number[] = []
  for (let offset = 0; offset < value.length; offset += 1) {
    const character = value[offset]!
    if (/\s/u.test(character)) {
      if (!text) continue
      if (text.endsWith(' ')) {
        ends[ends.length - 1] = offset + 1
        continue
      }
      text += ' '
    } else text += character
    starts.push(offset)
    ends.push(offset + 1)
  }
  if (text.endsWith(' ')) {
    text = text.slice(0, -1)
    starts.pop()
    ends.pop()
  }
  return { text, starts, ends }
}

export function locateUniqueEvidenceQuote(content: string, quote: string): EvidenceQuoteLocation {
  const body = mappedText(content)
  const excerpt = mappedText(quote).text
  if (!body.text) return { state: 'no_content', range: null }
  if (!excerpt) return { state: 'no_excerpt', range: null }
  if (excerpt.endsWith('…')) return { state: 'truncated', range: null }
  const index = body.text.indexOf(excerpt)
  if (index < 0) return { state: 'not_found', range: null }
  if (body.text.indexOf(excerpt, index + 1) >= 0) return { state: 'ambiguous', range: null }
  return {
    state: 'matched',
    range: { start: body.starts[index]!, end: body.ends[index + excerpt.length - 1]! },
  }
}
