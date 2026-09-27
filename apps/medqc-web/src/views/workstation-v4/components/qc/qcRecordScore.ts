/**
 * V5 运行/终末列表得分列的展示映射（合同第 5 节）。
 * 只搬运服务端 score_state 与顶层 score_standards，不在前端计分、不推断；
 * 非 ready 行不显示得分，未知值显示“未知”，不伪造 0 分或通过。
 */

import type { RecordLatestQcSummary, ScoreStandardOverview } from '../../types'

export type QcRecordScoreScene = 'running' | 'final'

export type QcRecordScoreCell =
  | { kind: 'scored'; score: number; grade: string | null; vetoHit: boolean }
  | { kind: 'no_standard' }
  | { kind: 'unavailable' }

export const SCORE_NO_STANDARD_TEXT = '未配置评分标准'
export const SCORE_UNAVAILABLE_TEXT = '得分暂不可用'

export function scoreSceneForCarePhase(carePhase: 'inpatient' | 'discharged'): QcRecordScoreScene {
  return carePhase === 'inpatient' ? 'running' : 'final'
}

/**
 * ready 行才有得分；场景概况为 no_standard 时整列显示“未配置评分标准”；
 * 行上缺少得分状态时按“暂不可用”处理。
 */
export function resolveScoreCell(
  summary: RecordLatestQcSummary | undefined,
  overview: ScoreStandardOverview | undefined,
): QcRecordScoreCell | undefined {
  if (summary?.status !== 'ready') return undefined
  if (overview?.status === 'no_standard') return { kind: 'no_standard' }
  const state = summary.scoreState
  if (!state) return { kind: 'unavailable' }
  if (state.status === 'no_standard') return { kind: 'no_standard' }
  if (state.status === 'scored' && state.score !== null) {
    return { kind: 'scored', score: state.score, grade: state.grade, vetoHit: state.vetoHit === true }
  }
  return { kind: 'unavailable' }
}

export function formatScoreValue(score: number): string {
  return String(Number(score.toFixed(2)))
}
