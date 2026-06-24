import { describe, expect, it } from 'vitest'

import {
  extractApiErrorMessage,
  isApiEnvelope,
  normalizeApiSuccess,
  unwrapApiEnvelope,
} from '@/utils/api-envelope'

describe('api-envelope', () => {
  it('识别标准响应壳', () => {
    expect(isApiEnvelope({ success: true, data: { id: 1 } })).toBe(true)
    expect(isApiEnvelope({ data: { id: 1 } })).toBe(false)
  })

  it('解包 success 响应', () => {
    const payload = unwrapApiEnvelope<{ id: number }>({ success: true, data: { id: 7 } })
    expect(payload.id).toBe(7)
  })

  it('兼容非壳响应', () => {
    const payload = unwrapApiEnvelope<{ id: number }>({ id: 9 })
    expect(payload.id).toBe(9)
  })

  it('失败响应壳不再被静默解包为空对象', () => {
    const payload = unwrapApiEnvelope<{ success: boolean; error?: string }>({
      success: false,
      error: 'forbidden',
    })
    expect(payload.success).toBe(false)
    expect(payload.error).toBe('forbidden')
  })

  it('归一化成功响应', () => {
    const normalized = normalizeApiSuccess<{ value: string }>({ success: true, data: { value: 'ok' } })
    expect(normalized.success).toBe(true)
    expect(normalized.data?.value).toBe('ok')
  })

  it('归一化失败响应', () => {
    const normalized = normalizeApiSuccess<{ value: string }>({
      success: false,
      error: 'forbidden',
      code: 'HTTP_403',
    })
    expect(normalized.success).toBe(false)
    expect(normalized.data).toBeUndefined()
  })

  it('提取错误消息优先级 detail > error > message > fallback', () => {
    expect(extractApiErrorMessage({ detail: 'd' }, 'f')).toBe('d')
    expect(extractApiErrorMessage({ error: 'e' }, 'f')).toBe('e')
    expect(extractApiErrorMessage({ message: 'm' }, 'f')).toBe('m')
    expect(extractApiErrorMessage({}, 'f')).toBe('f')
  })
})
