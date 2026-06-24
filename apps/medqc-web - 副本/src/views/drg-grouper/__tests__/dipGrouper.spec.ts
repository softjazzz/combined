import { describe, expect, it } from 'vitest'

import { performDipGrouping } from '../dipGrouper'

describe('performDipGrouping', () => {
  it('返回泸州 DIP 病种目录的分值、病种属性和基层病种标识', () => {
    const result = performDipGrouping({ zdList: ['G43.9'], ssList: [] })

    expect(result.status).toBe('分组成功')
    expect(result.dipCode).toBe('G43.9')
    expect(result.score).toBe(460.32)
    expect(result.diseaseAttribute).toBe('正常组')
    expect(result.primaryCareFlag).toBe('是')
  })

  it('模糊匹配医保扩展编码时仍返回目录属性', () => {
    const result = performDipGrouping({ zdList: ['I25.103'], ssList: ['88.5500'] })

    expect(result.status).toBe('分组成功')
    expect(result.dipCode).toBe('I25.1+88.5500')
    expect(result.score).toBe(1391.14)
    expect(result.diseaseAttribute).toBe('正常组')
    expect(result.primaryCareFlag).toBe('')
  })
})
