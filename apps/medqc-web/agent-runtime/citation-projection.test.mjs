import test from 'node:test'
import assert from 'node:assert/strict'
import { projectTurns } from './runtime.mjs'

const official = 'https://example.org/norm/2010.html'
function events(answer, references = [], offset = 0, search = true) {
  const turn = offset + 1
  return [
    {
      type: 'agent/inbox/spliced',
      data: { inserted: [{ source: { kind: 'user', run_id: `run-${turn}` }, content: [] }] },
    },
    { type: 'turn/start', time: 0, data: { turn } },
    ...(search ? [{ type: 'tool/call', data: { turn, name: 'weknora_search' } }] : []),
    { type: 'tool/result', data: { turn, meta: { references } } },
    {
      type: 'assistant/message',
      data: { turn, message: { content: [{ type: 'text', text: answer }] } },
    },
    { type: 'turn/end', time: 10, data: { turn, reason: { kind: 'completed' } } },
  ]
}
const source = { id: 'guideline:doc:0', kind: 'guideline', text: `官方出处：${official}。` }

test('规范回答仅展示来源中的完整链接，保留正文和原始事件', () => {
  const answer = `应在8小时内。官方链接：https://example.org/wjj，全文：[规范](${official})。`
  const input = events(answer, [source])
  const original = JSON.stringify(input)
  const [turn] = projectTurns(input)
  assert.ok(!turn.answer.includes('https://example.org/wjj'))
  assert.ok(turn.answer.includes(official))
  assert.ok(turn.answer.includes('链接未在已读取来源中核实'))
  assert.ok(turn.answer.includes('应在8小时内'))
  assert.equal(JSON.stringify(input), original)
})

test('无命中不能编链接，历史来源可沿用但不能借用未来来源', () => {
  assert.ok(!projectTurns(events(official))[0].answer.includes(official))
  const history = events('已检索', [source])
  const restored = projectTurns([...history, ...events(official, [], 1, false)])
  assert.equal(restored[1].answer, official)
  assert.equal(
    projectTurns([...events(official), ...events('来源', [source], 1)])[0].answer.includes(
      official,
    ),
    false,
  )
  assert.ok(
    !projectTurns(events(`${official}?invented=1`, [source]))[0].answer.includes('?invented=1'),
  )
})

test('普通保存结果回答和工具来源正文不被规范链接过滤重写', () => {
  const [turn] = projectTurns(events(official, [], 0, false))
  assert.equal(turn.answer, official)
  assert.deepEqual(projectTurns(events('依据不足', [source]))[0].references, [source])
})

test('声称原文的长摘录仅空白不同则恢复来源原样，文字改变则明确改称转述', () => {
  const original =
    '首次病程记录是指患者入院后由经治医师或值 班 医师书写的第一次病程记录，应当在 患者入院 8 小时内完成。'
  const reference = { ...source, text: `${source.text}\n${original}` }
  const compact = original.replace(/\s/g, '')
  const [matched] = projectTurns(events(`原文节选："${compact}"`, [reference]))
  assert.equal(matched.answer, `原文节选："${original}"`)
  const changed = compact.replace('8小时', '24小时')
  const [unmatched] = projectTurns(events(`原文节选："${changed}"`, [reference]))
  assert.ok(unmatched.answer.includes('回答转述（未逐字核实）'))
  assert.ok(!unmatched.answer.includes('原文节选'))
  assert.equal(
    projectTurns(events(`原文节选：“${original}”`, [reference]))[0].answer,
    `原文节选：“${original}”`,
  )
  const conflict = { ...source, id: 'guideline:other:0', text: compact }
  const spacedDifferently = original.replace('值 班', '值班')
  assert.ok(
    projectTurns(events(`原文节选：“${' '.repeat(40)}”`, [reference]))[0].answer.includes(
      '未逐字核实',
    ),
  )
  assert.ok(
    projectTurns(
      events(`原文节选：“${spacedDifferently}”`, [reference, conflict]),
    )[0].answer.includes('未逐字核实'),
  )
})
