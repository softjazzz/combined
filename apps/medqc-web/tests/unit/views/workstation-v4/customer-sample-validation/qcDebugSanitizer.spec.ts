import { describe, expect, it } from 'vitest'

import { sanitizeQcDebugPayload } from '@/views/workstation-v4/customer-sample-validation/qcDebugSanitizer'

describe('sanitizeQcDebugPayload 规则身份', () => {
  it('保留四段规则编号的单值和数组', () => {
    const payload = {
      rule_id: 'LX0609-01-01-01',
      ruleCode: 'LX0609-08-01-01',
      primary_execution_rule_id: 'LX0609-03-01-01',
      rule_ids: ['LX0609-01-01-01', 'LX0609-08-01-01'],
      selected_rule_ids: ['LX0609-03-01-01'],
    }

    expect(sanitizeQcDebugPayload(payload)).toEqual(payload)
  })

  it('规则身份字段中的嵌套对象仍脱敏凭据和患者姓名', () => {
    const result = sanitizeQcDebugPayload({
      rule_id: {
        api_key: 'sk-proj-testsecret123456789',
        patient_name: '李庆珍',
        nested: { authorization: 'Bearer nestedsecret123456789' },
      },
      ruleCode: { password: 'identity-field-password' },
    })

    expect(result).toEqual({
      rule_id: {
        api_key: '[访问凭证已脱敏]',
        patient_name: '患者A',
        nested: { authorization: '[访问凭证已脱敏]' },
      },
      ruleCode: { password: '[访问凭证已脱敏]' },
    })
  })

  it.each(['rule_ids', 'selected_rule_ids'])('%s 混合数组逐项保留合法编号并脱敏其余内容', (key) => {
    const result = sanitizeQcDebugPayload({
      [key]: [
        'LX0609-01-01-01',
        '患者李庆珍,性别女 token=mixed-array-secret',
        { patient_name: '李庆珍', credentials: 'nested-credentials' },
        ['LX0609-08-01-01', { password: 'nested-array-password' }],
      ],
    })

    expect(result[key][0]).toBe('LX0609-01-01-01')
    expect(result[key][2]).toEqual({
      patient_name: '患者A',
      credentials: '[访问凭证已脱敏]',
    })
    expect(result[key][3]).toEqual(['LX0609-08-01-01', { password: '[访问凭证已脱敏]' }])
    const serialized = JSON.stringify(result)
    for (const sensitive of [
      '李庆珍',
      'mixed-array-secret',
      'nested-credentials',
      'nested-array-password',
    ]) {
      expect(serialized).not.toContain(sensitive)
    }
  })

  it('含四段编号的非编号文本仍执行脱敏', () => {
    const result = sanitizeQcDebugPayload({
      rule_id: 'LX0609-01-01-01 token=appended-secret',
      rule_code: 'LX0609-08-01-01\n患者李庆珍,性别女',
    })

    expect(result.rule_id).toContain('token=[访问凭证已脱敏]')
    expect(result.rule_code).toContain('患者A')
    expect(JSON.stringify(result)).not.toContain('李庆珍')
  })

  it('其他规则集编号和判据名称继续使用原有脱敏行为', () => {
    const payload = {
      rule_id: 'SICHUAN-001',
      rule_ids: ['SICHUAN-001', 'SICHUAN-002'],
      criterion_id: 'time_window',
      rule_set_id: 'sichuan_hospital',
    }

    expect(sanitizeQcDebugPayload(payload)).toEqual(payload)
  })
})
