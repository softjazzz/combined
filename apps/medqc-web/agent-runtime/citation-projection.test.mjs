import test from 'node:test'
import assert from 'node:assert/strict'
import { projectTurns } from './runtime.mjs'

const official = 'https://example.org/norm/2010.html'
function events(answer, references = [], offset = 0, tool = 'weknora_search') {
  const turn = offset + 1
  return [
    {
      type: 'agent/inbox/spliced',
      data: { inserted: [{ source: { kind: 'user', run_id: `run-${turn}` }, content: [] }] },
    },
    { type: 'turn/start', time: 0, data: { turn } },
    ...(tool ? [{ type: 'tool/call', data: { turn, name: tool } }] : []),
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

test('规范查询后的保存证据原文按实际业务来源核对，不被历史规范误标为转述', () => {
  const excerpt =
    '合成保存证据：本段是用于回归验证的测试 文书内容，记录时间、病程描述与检查结果均为测试文字，不对应任何真实患者。'
  const businessUrl = 'https://example.org/records/test'
  const saved = {
    id: 'saved-result:test:2',
    kind: 'saved_result',
    text: `已保存结论\n${excerpt}\n${businessUrl}`,
    evidence: [{ evidence_excerpt: excerpt }],
  }
  const answer = `保存证据原文：“${excerpt}”`
  const baseline = projectTurns(events(answer, [saved], 0, 'read_saved_issue'))[0]
  const input = [
    ...events('已查规范', [source]),
    ...events(`${answer}\n规范链接：${businessUrl}`, [saved], 1, 'read_saved_issue'),
  ]
  const original = JSON.stringify(input)
  const [, restored] = projectTurns(input)
  assert.ok(restored.answer.includes(baseline.answer))
  assert.ok(!restored.answer.includes('回答转述'))
  assert.ok(!restored.answer.includes(businessUrl), '业务来源不扩展规范链接允许范围')
  assert.deepEqual(restored.references, [saved])
  assert.equal(JSON.stringify(input), original)
  const compact = excerpt.replace(/\s/gu, '')
  const [, spaced] = projectTurns([
    ...events('已查规范', [source]),
    ...events(`保存证据原文：“${compact}”`, [saved], 1, 'read_saved_issue'),
  ])
  assert.equal(spaced.answer, answer)
})

test('混合来源中的改写长摘录仍明确标为转述，不能借用未来业务证据', () => {
  const excerpt =
    '合成保存证据：本段用于检验来源核对时的时间边界，所有描述均为固定的测试文字，不包含真实患者资料或临床判定。'
  const saved = { id: 'saved-result:test:2', kind: 'saved_result', text: excerpt }
  const changed = excerpt.replace('固定', '变造')
  const [, changedTurn] = projectTurns([
    ...events('已查规范', [source]),
    ...events(`病历原文：“${changed}”`, [saved], 1, 'read_saved_issue'),
  ])
  assert.ok(changedTurn.answer.includes('回答转述（未逐字核实）'))
  const [early] = projectTurns([
    ...events(`原文：“${excerpt}”`, [source]),
    ...events('随后才读取保存证据', [saved], 1, 'read_saved_issue'),
  ])
  assert.ok(early.answer.includes('回答转述（未逐字核实）'))
})

test('保存建议重排标点后不能称原文，逐字结论和来源卡片保持不变', () => {
  const saved = {
    id: 'saved:test',
    kind: 'saved_result',
    conclusion: '合成结论：未找到所需记录。',
    suggestion: '修改对象：测试记录\n需要补充：测试字段\n注意事项：不要编造。',
  }
  const changed = saved.suggestion.replaceAll('\n', '；')
  const answer = `结论原文：${saved.conclusion}\n建议原文：${changed}\n\n下一步：查看下方保存卡片。`
  const input = events(answer, [saved], 0, 'read_saved_results')
  const before = JSON.stringify(input)
  const [turn] = projectTurns(input)
  assert.equal(turn.answer, answer.replace('建议原文：', '建议转述（未逐字核实）：'))
  assert.deepEqual(turn.references, [saved])
  assert.equal(JSON.stringify(input), before)
})

test('保存字段原文支持多行和成对引号，但不能丢否定条件或借用其他类型来源', () => {
  const saved = {
    id: 'saved:test',
    kind: 'saved_result',
    conclusion: '测试结论。',
    suggestion: '补充测试字段。\n不得倒签。',
  }
  for (const body of [saved.suggestion, `“${saved.suggestion}”`]) {
    const answer = `建议原文：${body}\n\n概述：请查保存卡片。`
    assert.equal(projectTurns(events(answer, [saved], 0, 'read_saved_results'))[0].answer, answer)
  }
  for (const [body, refs] of [
    ['补充测试字段。', [saved]],
    ['补充测试字段。可以倒签。', [saved]],
    [saved.suggestion, [{ ...saved, kind: 'guideline', text: saved.suggestion }]],
  ]) {
    const answer = `建议原文：${body}`
    assert.equal(
      projectTurns(events(answer, refs, 0, 'read_saved_results'))[0].answer,
      `建议转述（未逐字核实）：${body}`,
    )
  }
  const answer = `结论原文：${saved.suggestion}`
  assert.equal(
    projectTurns(events(answer, [saved], 0, 'read_saved_results'))[0].answer,
    `结论转述（未逐字核实）：${saved.suggestion}`,
  )
})

test('保存字段原文可使用已读历史但不能借用未来来源，普通概述不改写', () => {
  const saved = { id: 'saved:test', kind: 'saved_result', suggestion: '仅用于测试的保存建议。' }
  const answer = `建议原文：${saved.suggestion}`
  const turns = projectTurns([
    ...events(answer, [], 0, false),
    ...events('已读取保存建议', [saved], 1, 'read_saved_issue'),
    ...events(answer, [], 2, false),
  ])
  assert.equal(turns[0].answer, `建议转述（未逐字核实）：${saved.suggestion}`)
  assert.equal(turns[2].answer, answer)
  const overview = '建议概述：补充相应记录。下方卡片保留建议原文。'
  assert.equal(projectTurns(events(overview, [saved], 0, 'read_saved_results'))[0].answer, overview)
})
