import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  buildExamLabEventPresentation,
  NOT_APPLICABLE_NEGATIVE_TEXT,
  NOT_APPLICABLE_UNKNOWN_TEXT,
  NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT,
} from '../examLabEventPresentation'
import type { SingleRecordQcResultItem } from '../single-record-result-model'

const REPORT_TIME = '2026-08-10 09:30:00'

/** 与前端同目录结构对应的后端真值源（apps/medqc-web 根下的相对路径）。 */
const BACKEND_RENDERER_RELATIVE_PATH = 'backend/app/services/luxian_0609/customer_renderer.py'
const BACKEND_RENDERER_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../',
  BACKEND_RENDERER_RELATIVE_PATH,
)

function buildItem(
  eventResults: Record<string, unknown>[],
  ruleId = 'LX0609-06-01-05',
): SingleRecordQcResultItem {
  return {
    rule_id: ruleId,
    rule_name: 'CT/MRI 阳性结果 24 小时内分析',
    status: 'not_applicable',
    customer_display_facts: {
      requirement: 'positive_result_analysis_within_24h',
      subject: 'ct_mri',
      threshold_hours: 24,
      event_count: eventResults.length,
      event_results: eventResults.map((override, index) => ({
        event_position: index + 1,
        report_time: REPORT_TIME,
        event_status: 'not_applicable',
        response_record_count: 0,
        ...override,
      })),
    },
  }
}

/** 显式三字段行，参数不设默认值，便于用 `undefined` 覆盖生产校验。 */
function buildRow(
  eventStatus: unknown,
  positiveState: unknown,
  responseRecordCount: unknown,
): Record<string, unknown> {
  return {
    event_status: eventStatus,
    positive_state: positiveState,
    response_record_count: responseRecordCount,
  }
}

function singleRow(eventStatus: unknown, positiveState: unknown) {
  return buildExamLabEventPresentation(buildItem([buildRow(eventStatus, positiveState, 0)]))
}

describe('LX0609-06-01-05/LX0609-06-03-04 逐次检查 not_applicable 文案', () => {
  it('positive_state=positive 输出「评价窗口尚未届满」且正面标记为真', () => {
    const presentation = singleRow('not_applicable', 'positive')

    expect(presentation?.events).toHaveLength(1)
    expect(presentation?.events[0]).toMatchObject({
      eventPosition: 1,
      reportTime: REPORT_TIME,
      positive: true,
      eventStatus: 'not_applicable',
      tone: 'neutral',
      statusLabel: '不适用',
      description: '报告后 24 小时评价窗口尚未届满，暂不判定',
    })
    expect(presentation?.events[0].description).toBe(NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT)
  })

  it('positive_state=negative 输出「未检出需分析的阳性结果」且正面标记为假', () => {
    const presentation = singleRow('not_applicable', 'negative')

    expect(presentation?.events).toHaveLength(1)
    expect(presentation?.events[0]).toMatchObject({
      positive: false,
      eventStatus: 'not_applicable',
      tone: 'neutral',
      statusLabel: '不适用',
      description: '按报告结果判定为未检出需分析的阳性结果，本项不适用',
    })
    expect(presentation?.events[0].description).toBe(NOT_APPLICABLE_NEGATIVE_TEXT)
  })

  it('positive_state=unknown 输出「未确认目标事件」', () => {
    const presentation = singleRow('not_applicable', 'unknown')

    expect(presentation?.events[0]).toMatchObject({
      positive: false,
      eventStatus: 'not_applicable',
      tone: 'neutral',
      statusLabel: '不适用',
      description: '未确认本次检查为需分析的目标事件，本项不适用',
    })
    expect(presentation?.events[0].description).toBe(NOT_APPLICABLE_UNKNOWN_TEXT)
  })

  it('三种 positive_state 的 description 互不相同，且分别命中三个导出常量', () => {
    const descriptions = (['positive', 'negative', 'unknown'] as const).map(
      (state) => singleRow('not_applicable', state)?.events[0].description,
    )

    expect(new Set(descriptions).size).toBe(3)
    expect(descriptions).toEqual([
      NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT,
      NOT_APPLICABLE_NEGATIVE_TEXT,
      NOT_APPLICABLE_UNKNOWN_TEXT,
    ])
  })

  it('positive=true 的行绝不出现「未明确阳性」措辞', () => {
    const statuses = [
      'not_applicable',
      'non_compliant',
      'compliant',
      'data_gap',
      'evaluation_unknown',
      'uncertain',
      'technical_error',
    ]
    const presentation = buildExamLabEventPresentation(
      buildItem(statuses.map((status) => buildRow(status, 'positive', 2))),
    )

    const positiveRows = presentation?.events.filter((event) => event.positive) ?? []
    expect(positiveRows).toHaveLength(statuses.length)
    for (const row of positiveRows) {
      expect(row.description).not.toContain('未明确阳性')
    }
  })
})

describe('LX0609-06-01-05/LX0609-06-03-04 逐次检查 not_applicable 缺失 positive_state 的现状（与任务书预期不同）', () => {
  // 任务书要求「positive_state 缺失 → 未确认本次检查为需分析的目标事件，本项不适用」，
  // 但现有实现对 positive_state 做白名单校验：缺失（undefined）会被判为非法输入，
  // 整个 presentation 返回 null（客户侧表现为整块「逐次检查核对」消失），而不是退化为
  // unknown 文案。后端 customer_renderer.py 用 `str(item.get("positive_state") or "")`
  // 落到 else 分支，会渲染 unknown 文案 —— 两端在该输入上不一致。
  // 本次任务白名单只允许抽常量、禁止改分支，故此处固化现状并记录为待处置项。
  it('positive_state 键缺失时整块 presentation 返回 null（现状，非任务书预期）', () => {
    const presentation = buildExamLabEventPresentation(
      buildItem([{ event_status: 'not_applicable', response_record_count: 0 }]),
    )

    expect(presentation).toBeNull()
  })

  it('该缺失输入在后端会被渲染为 unknown 文案（证明两端确实不一致）', () => {
    const source = readFileSync(BACKEND_RENDERER_PATH, 'utf8')

    expect(source).toContain('positive_state = str(item.get("positive_state") or "")')
    expect(source).toContain(`conclusion = "${NOT_APPLICABLE_UNKNOWN_TEXT}"`)
  })
})

describe('LX0609-06-01-05/LX0609-06-03-04 逐次检查其余分支口径保持不变', () => {
  it('non_compliant 保持既有 danger / 未完成分析 文案', () => {
    const presentation = singleRow('non_compliant', 'positive')

    expect(presentation?.events[0]).toMatchObject({
      eventStatus: 'non_compliant',
      tone: 'danger',
      statusLabel: '未完成分析',
      description: '阳性结果未在 24 小时内找到临床分析记录',
    })
  })

  it('non_compliant 展示本次未分析的具体 CT/MRI 报告结果', () => {
    const presentation = buildExamLabEventPresentation(
      buildItem([
        {
          ...buildRow('non_compliant', 'positive', 0),
          report_result_texts: ['L4/5 椎间盘突出，椎管狭窄。'],
        },
      ]),
    )

    expect(presentation?.events[0]).toMatchObject({
      statusLabel: '未完成分析',
      description: '下列 CT/MRI 阳性结果未在 24 小时内找到临床分析记录',
      reportResultLabel: '未分析的 CT/MRI 阳性结果',
      reportResultTexts: ['L4/5 椎间盘突出，椎管狭窄。'],
    })
  })

  it('报告结果明细只对 CT/MRI 阳性分析事件开放', () => {
    const event = {
      ...buildRow('non_compliant', 'positive', 0),
      report_result_texts: ['阳性报告结果。'],
    }

    expect(buildExamLabEventPresentation(buildItem([event], 'LX0609-06-03-04'))).toBeNull()
    expect(
      buildExamLabEventPresentation(
        buildItem([{ ...event, positive_state: 'negative' }], 'LX0609-06-01-05'),
      ),
    ).toBeNull()
  })

  it('compliant 保持既有 success / 已完成分析 文案并带分析记录条数', () => {
    const presentation = buildExamLabEventPresentation(
      buildItem([buildRow('compliant', 'positive', 3)]),
    )

    expect(presentation?.events[0]).toMatchObject({
      eventStatus: 'compliant',
      tone: 'success',
      statusLabel: '已完成分析',
      description: '阳性结果已找到 3 条临床分析记录',
    })
  })

  it('compliant 且分析记录为 0 条时仍是 success 分支（边界不变）', () => {
    const presentation = buildExamLabEventPresentation(
      buildItem([buildRow('compliant', 'positive', 0)]),
    )

    expect(presentation?.events[0]).toMatchObject({
      tone: 'success',
      statusLabel: '已完成分析',
      description: '阳性结果已找到 0 条临床分析记录',
    })
  })

  it.each(['data_gap', 'evaluation_unknown', 'uncertain', 'technical_error'])(
    '%s 保持既有 warning / 待核实 文案',
    (eventStatus) => {
      const presentation = singleRow(eventStatus, 'negative')

      expect(presentation?.events[0]).toMatchObject({
        eventStatus,
        tone: 'warning',
        statusLabel: '待核实',
        description: '当前资料不足，暂无法完成分析记录核对',
      })
    },
  )
})

describe('LX0609-06-01-05/LX0609-06-03-04 逐次检查非法输入返回 null', () => {
  it.each(['possibly', 'POSITIVE', 'not_relevant', '', undefined, null, 1])(
    '非法 positive_state（%s）返回 null',
    (positiveState) => {
      expect(singleRow('not_applicable', positiveState)).toBeNull()
    },
  )

  it.each(['maybe', 'NOT_APPLICABLE', '', undefined, null, 3])(
    '非法 event_status（%s）返回 null',
    (eventStatus) => {
      expect(singleRow(eventStatus, 'positive')).toBeNull()
    },
  )

  it.each([-1, 1.5, '3', null, undefined, Number.NaN])(
    '非法 response_record_count（%s）返回 null',
    (count) => {
      expect(
        buildExamLabEventPresentation(buildItem([buildRow('compliant', 'positive', count)])),
      ).toBeNull()
    },
  )

  it('非检查检验逐次核对规则返回 null', () => {
    expect(
      buildExamLabEventPresentation(
        buildItem([buildRow('not_applicable', 'positive', 0)], 'LX0609-06-01-02'),
      ),
    ).toBeNull()
  })

  it('event_count 与 event_results 长度不一致时返回 null', () => {
    const item = buildItem([buildRow('not_applicable', 'positive', 0)])
    const facts = item.customer_display_facts as Record<string, unknown>
    facts.event_count = 2

    expect(buildExamLabEventPresentation(item)).toBeNull()
  })
})

describe('LX0609-06-01-04/LX0609-06-03-03 报告结果记录逐次核对', () => {
  it('将多次检查转换为摘要和逐次状态，不再展示一整段编号文本', () => {
    const item = buildItem(
      [
        {
          event_status: 'compliant',
          positive_state: 'not_relevant',
          response_record_count: 1,
          response_record_time: '2025-08-13 11:00:00',
          interval_hours: 16.01,
        },
        {
          event_status: 'non_compliant',
          positive_state: 'not_relevant',
          response_record_count: 0,
        },
        {
          event_status: 'compliant',
          positive_state: 'not_relevant',
          response_record_count: 1,
          response_record_time: '2025-08-16 09:50:01',
          interval_hours: 22.75,
        },
      ],
      'LX0609-06-01-04',
    )
    const facts = item.customer_display_facts as Record<string, unknown>
    facts.requirement = 'result_recording_within_24h'

    const presentation = buildExamLabEventPresentation(item)

    expect(presentation?.headline).toBe(
      '共核对 3 次 CT/MRI 检查；2 次已记录，1 次未在 24 小时内记录。',
    )
    expect(presentation?.positiveLabel).toBe('已记录 2 次')
    expect(presentation?.issueLabel).toBe('未记录 1 次')
    expect(presentation?.events).toMatchObject([
      {
        statusLabel: '已记录',
        tone: 'success',
        description: '已完成报告结果记录；最早相关病程 2025-08-13 11:00:00，间隔 16.01 小时',
      },
      {
        statusLabel: '未记录',
        tone: 'danger',
        description: '报告后 24 小时内未找到报告结果记录',
      },
      {
        statusLabel: '已记录',
        tone: 'success',
        description: '已完成报告结果记录；最早相关病程 2025-08-16 09:50:01，间隔 22.75 小时',
      },
    ])
  })
})

describe('LX0609-06-01-05 多事件 not_applicable 文案与后端 customer_renderer.py 跨端一致', () => {
  it('后端源文件存在', () => {
    expect(existsSync(BACKEND_RENDERER_PATH), `未找到后端渲染器：${BACKEND_RENDERER_PATH}`).toBe(
      true,
    )
  })

  it('后端三句 conclusion 字面量与前端常量逐字相等（任一端改字即失败）', () => {
    const source = readFileSync(BACKEND_RENDERER_PATH, 'utf8')
    const expectedAssignments = [
      `conclusion = "${NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT}"`,
      `conclusion = "${NOT_APPLICABLE_NEGATIVE_TEXT}"`,
      `conclusion = "${NOT_APPLICABLE_UNKNOWN_TEXT}"`,
    ]

    for (const assignment of expectedAssignments) {
      expect(source, `后端缺少与前端常量逐字一致的赋值：${assignment}`).toContain(assignment)
    }
  })

  it('后端源文件仍覆盖 LX0609-06-01-05/LX0609-06-03-04 多事件 not_applicable 分支', () => {
    const source = readFileSync(BACKEND_RENDERER_PATH, 'utf8')

    expect(source).toContain('elif event_status == "not_applicable":')
    expect(source).toContain('if isinstance(event_results, list) and len(event_results) > 1:')
  })
})
