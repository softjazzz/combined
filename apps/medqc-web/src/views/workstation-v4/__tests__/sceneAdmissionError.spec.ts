import { describe, expect, it } from 'vitest'

import { formatCaseSceneAdmissionError } from '../utils/sceneAdmissionError'

describe('formatCaseSceneAdmissionError', () => {
  it('按 selection_index 映射到具体病历并提示取消勾选后继续质控', () => {
    const message = formatCaseSceneAdmissionError(
      {
        code: 'case_scene_admission_failed',
        message: '所选病例场景未确认或与质控范围不符，请核对逐项原因。',
        cases: [
          {
            selection_index: 1,
            code: 'case_scene_unknown',
            scene: 'unknown',
            discharge_state: 'unknown',
            discharge_time_status: 'missing',
          },
        ],
      },
      [
        { patientName: '范世英', visitId: '2641480' },
        { patientName: '程思明', visitId: '2593457' },
        { patientName: '童世先', visitId: '2607119' },
      ],
      '创建四川规则批量任务失败',
    )

    expect(message).toContain('程思明（2593457）')
    expect(message).toContain('缺少原始出院/死亡时间')
    expect(message).toContain('取消勾选上述病历后')
  })

  it('超过 3 份未通过时截断展示并给出总数，兼容缺失姓名与范围不符', () => {
    const message = formatCaseSceneAdmissionError(
      {
        code: 'case_scene_admission_failed',
        cases: [
          { selection_index: 0, code: 'case_scene_unknown', discharge_time_status: 'conflict' },
          { selection_index: 1, code: 'case_scene_scope_mismatch', scene: 'running' },
          { selection_index: 2, code: 'case_scene_unknown', discharge_time_status: 'missing' },
          { selection_index: 3, code: 'case_scene_unknown', discharge_time_status: 'missing' },
        ],
      },
      [
        { visitId: 'V1' },
        { patientName: '患者乙', visitId: 'V2' },
        { patientName: '患者丙', visitId: 'V3' },
        { patientName: '患者丁', visitId: 'V4' },
      ],
      'fallback',
    )

    expect(message).toContain('4 份病历未通过场景校验')
    expect(message).toContain('就诊号 V1：出院时间存在冲突')
    expect(message).toContain('患者乙（V2）：当前为在院病历，与所选质控范围不符')
    expect(message).toContain('等共 4 份病历')
  })

  it('非 case_scene_admission_failed 错误直接返回 fallback', () => {
    expect(
      formatCaseSceneAdmissionError({ code: 'other_error' }, [], '默认错误提示'),
    ).toBe('默认错误提示')
  })
})
