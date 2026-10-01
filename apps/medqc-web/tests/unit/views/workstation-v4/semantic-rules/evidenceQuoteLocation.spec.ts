import { describe, expect, it } from 'vitest'
import { locateUniqueEvidenceQuote } from '@/views/workstation-v4/semantic-rules/evidenceQuoteLocation'

describe('已保存证据原文唯一定位', () => {
  it('短摘录与补充字符映射回原文 UTF-16 坐标', () => {
    const body = '入院：患者\u{1f600}腹痛3天，神志清楚'
    const result = locateUniqueEvidenceQuote(body, '患者\u{1f600}腹痛3天')
    expect(result.state).toBe('matched')
    expect(body.slice(result.range!.start, result.range!.end)).toBe('患者\u{1f600}腹痛3天')
    expect(locateUniqueEvidenceQuote(body, '腹痛3天').state).toBe('matched')
  })

  it('授权摘录合并空白后仍映射真实正文，不能凭删除空白拼词', () => {
    const body = '主诉：胸痛\n  3天'
    const result = locateUniqueEvidenceQuote(body, '胸痛 3天')
    expect(body.slice(result.range!.start, result.range!.end)).toBe('胸痛\n  3天')
    expect(locateUniqueEvidenceQuote('胸痛3天', '胸痛 3天').state).toBe('not_found')
  })

  it.each(['腹痛。腹痛', '腹腹腹'])('重复和重叠命中不得选择首个 %s', (body) => {
    expect(locateUniqueEvidenceQuote(body, body === '腹腹腹' ? '腹腹' : '腹痛').state).toBe(
      'ambiguous',
    )
  })

  it.each(['证据说明：腹痛3天', '腹痛3天。另有未保存原文', '腹痛3天…', '腹痛3天...'])(
    '不裁剪或拆句猜测 %s',
    (quote) => {
      expect(locateUniqueEvidenceQuote('腹痛3天。', quote).state).toBe(
        quote.endsWith('…') ? 'truncated' : 'not_found',
      )
    },
  )

  it('保留字面大小写、全半角及缺正文语义', () => {
    expect(locateUniqueEvidenceQuote('ABC123', 'abc123').state).toBe('not_found')
    expect(locateUniqueEvidenceQuote('ＡＢＣ', 'ABC').state).toBe('not_found')
    expect(locateUniqueEvidenceQuote('', '腹痛').state).toBe('no_content')
    expect(locateUniqueEvidenceQuote('腹痛', '').state).toBe('no_excerpt')
  })
})
