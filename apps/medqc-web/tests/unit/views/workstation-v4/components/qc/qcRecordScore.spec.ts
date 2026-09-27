import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QcRecordResultTable, {
  type QcRecordResultRow,
} from '@/views/workstation-v4/components/qc/QcRecordResultTable.vue'
import { resolveScoreCell } from '@/views/workstation-v4/components/qc/qcRecordScore'
import { normalizeRecord, normalizeScoreStandards } from '@/views/workstation-v4/normalize'

function summaryOf(latest: Record<string, unknown>) {
  return normalizeRecord({ id: 'V', latest_qc_summary: latest }).latestQcSummary
}

const configured = { status: 'configured' as const, standardId: 's1', standardName: '标准', standardUpdatedAt: null }

describe('得分列映射', () => {
  it('normalize 只搬运可识别的 score_state，scored 缺分数降级为 unavailable', () => {
    expect(summaryOf({ status: 'ready', score_state: { status: 'scored', score: 88, grade: '乙', veto_hit: true, standard_id: 's1', reason_code: null } })?.scoreState)
      .toEqual({ status: 'scored', score: 88, grade: '乙', vetoHit: true, standardId: 's1', reasonCode: null })
    expect(summaryOf({ status: 'ready', score_state: { status: 'scored', score: null } })?.scoreState)
      .toMatchObject({ status: 'unavailable', score: null, reasonCode: 'score_missing' })
    expect(summaryOf({ status: 'ready', score_state: { status: 'weird' } })?.scoreState).toBeNull()
    expect(summaryOf({ status: 'ready' })?.scoreState).toBeNull()
    expect(summaryOf({ status: 'not_run', score_state: { status: 'scored', score: 90 } })).toEqual({ status: 'not_run' })
  })

  it('normalizeScoreStandards 只保留合法场景与状态', () => {
    expect(normalizeScoreStandards({
      running: { status: 'no_standard', standard_id: null },
      final: { status: 'configured', standard_id: 's2', standard_name: '终末', standard_updated_at: '2026-09-27T01:00:00' },
      outpatient: { status: 'bogus' },
      other: { status: 'configured' },
    })).toEqual({
      running: { status: 'no_standard', standardId: null, standardName: null, standardUpdatedAt: null },
      final: { status: 'configured', standardId: 's2', standardName: '终末', standardUpdatedAt: '2026-09-27T01:00:00' },
    })
    expect(normalizeScoreStandards(null)).toEqual({})
  })

  it('resolveScoreCell：非 ready 不显示；场景无标准整列未配置；缺状态为暂不可用', () => {
    const scored = summaryOf({ status: 'ready', score_state: { status: 'scored', score: 70, grade: '丙', veto_hit: false } })
    expect(resolveScoreCell(summaryOf({ status: 'not_run' }), configured)).toBeUndefined()
    expect(resolveScoreCell(summaryOf({ status: 'technical_error' }), configured)).toBeUndefined()
    expect(resolveScoreCell(scored, configured)).toEqual({ kind: 'scored', score: 70, grade: '丙', vetoHit: false })
    expect(resolveScoreCell(scored, { ...configured, status: 'no_standard' })).toEqual({ kind: 'no_standard' })
    expect(resolveScoreCell(summaryOf({ status: 'ready' }), configured)).toEqual({ kind: 'unavailable' })
    expect(resolveScoreCell(summaryOf({ status: 'ready', score_state: { status: 'no_standard' } }), undefined))
      .toEqual({ kind: 'no_standard' })
  })
})

describe('QcRecordResultTable 得分列', () => {
  const base: QcRecordResultRow = {
    recordKey: 'r1', instituteId: 'H', patientId: 'P', visitId: 'V1', patientName: '患者甲',
    resultStatus: 'completed', resultLabel: '已完成', issueSummary: '无确定问题', reviewState: 'approved',
  }

  it('默认不显示得分列，保持原列数', () => {
    const wrapper = mount(QcRecordResultTable, { props: { carePhase: 'inpatient', compactReview: true, rows: [base] } })
    expect(wrapper.findAll('thead th')).toHaveLength(5)
    expect(wrapper.find('[data-testid="qc-record-score"]').exists()).toBe(false)
  })

  it('开启后在最近质控之后显示得分 / 等级、否决标记与说明文案', () => {
    const rows: QcRecordResultRow[] = [
      { ...base, recordKey: 'scored', score: { kind: 'scored', score: 91.256, grade: '甲', vetoHit: false } },
      { ...base, recordKey: 'veto', score: { kind: 'scored', score: 95, grade: '丙', vetoHit: true } },
      { ...base, recordKey: 'unknown-grade', score: { kind: 'scored', score: 50, grade: null, vetoHit: false } },
      { ...base, recordKey: 'none', score: { kind: 'no_standard' } },
      { ...base, recordKey: 'down', score: { kind: 'unavailable' } },
      { ...base, recordKey: 'not-run', resultStatus: 'not-run', reviewState: undefined },
    ]
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', compactReview: true, showScore: true, rows },
    })
    expect(wrapper.findAll('thead th').map((item) => item.text())).toEqual([
      '', '患者 / 科室', '问题摘要', '最近质控', '得分 / 等级', '预览',
    ])
    const text = (key: string) => wrapper.get(`[data-record-key="${key}"] [data-testid="qc-record-score"]`).text()
    expect(text('scored')).toBe('91.26 / 甲')
    expect(text('veto')).toContain('95 / 丙')
    expect(wrapper.get('[data-record-key="veto"] [data-testid="qc-record-score-veto"]').text()).toBe('单项否决')
    expect(text('unknown-grade')).toBe('50 / 未知')
    expect(text('none')).toBe('未配置评分标准')
    expect(text('down')).toBe('得分暂不可用')
    expect(text('not-run')).toBe('')
    expect(wrapper.get('[data-record-key="scored"] [data-testid="qc-record-review-state"]').text()).toBe('审核通过')
  })

  it('空表 colspan 计入得分列', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', compactReview: true, showScore: true, rows: [] },
    })
    expect(wrapper.get('tbody td').attributes('colspan')).toBe('6')
  })
})
