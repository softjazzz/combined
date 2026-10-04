import test from 'node:test'
import assert from 'node:assert/strict'
import { verifiedSourceQuotes } from './runtime.mjs'
const claim = '以上为检索到的节选原文照录'
const refs = (...texts) =>
  texts.map((text, index) => ({ id: `source-${index}`, kind: 'guideline', text }))
test('无引号重组只降格声明，正文和来源不变', () => {
  const body = '应在8小时完成；内容包括诊断（含鉴别诊断）。'
  const source = refs('应在8小时完成。内容包括诊断、鉴别诊断。')
  const before = JSON.stringify(source)
  const result = verifiedSourceQuotes(`${body}${claim}。`, source)
  assert.equal(result, `${body}以上为回答转述（未逐字核实），请打开来源卡查看原文。`)
  assert.equal(JSON.stringify(source), before)
})
test('连续原文及明确引导语可保留，普通原文提及不受影响', () => {
  const body = '应在8小时完成。'
  for (const text of [body + claim, `**要求**\n\n《规范》写明：${body}${claim}`])
    assert.equal(verifiedSourceQuotes(text, refs(body)), text)
  const mention = '本次未读取原文，请打开来源卡查看原文。'
  assert.equal(verifiedSourceQuotes(mention, []), mention)
})
test('跨来源拼接和无可定位前文降格，单来源连续多段保持', () => {
  const body = '第一条要求。\n\n第二条要求。'
  assert.ok(
    verifiedSourceQuotes(body + claim, refs('第一条要求。', '第二条要求。')).includes('回答转述'),
  )
  assert.equal(verifiedSourceQuotes(body + claim, refs(body)), body + claim)
  assert.ok(verifiedSourceQuotes(claim, refs(body)).includes('回答转述'))
})
test('有引号原样长引用继续保持', () => {
  const body =
    '首次病程记录是指患者入院后由经治医师或值班医师书写的第一次病程记录，应当在患者入院8小时内完成。'
  const text = `原文节选：“${body}”`
  assert.equal(verifiedSourceQuotes(text, refs(body)), text)
})

test('历史规范混合保存证据或当前规则时，真实连续照录保持', () => {
  const sources = [
    ...refs('此前检索的规范正文。'),
    { id: 'saved', kind: 'saved_result', text: '当前保存证据的连续原句。' },
    { id: 'rule', kind: 'rule', text: '当前规则实施口径的连续原句。' },
  ]
  for (const item of sources.slice(1)) {
    const answer = item.text + claim
    assert.equal(verifiedSourceQuotes(answer, sources), answer)
  }
  const combined = sources[1].text + sources[2].text
  assert.equal(
    verifiedSourceQuotes(combined + claim, sources),
    combined + '以上为回答转述（未逐字核实），请打开来源卡查看原文',
  )
})
