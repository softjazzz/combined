import { describe, expect, it } from 'vitest'
import {
  buildCaseRecordKey,
  serializeCaseRecordKey,
} from '@/views/workstation-v4/utils/caseRecordKey'

describe('病例三键', () => {
  it('序列化时保留字段顺序及原值', () => {
    expect(serializeCaseRecordKey(' 机构 ', '患者,甲', '就诊')).toBe('[" 机构 ","患者,甲","就诊"]')
    expect(serializeCaseRecordKey('', 123, undefined)).toBe('["",123,null]')
  })

  it('标准化时裁剪空白并拒绝缺失坐标', () => {
    expect(buildCaseRecordKey(' 机构 ', ' 患者 ', ' 就诊 ')).toBe('["机构","患者","就诊"]')
    expect(buildCaseRecordKey('机构', '患者', ' ')).toBeUndefined()
  })
})
