import { describe, expect, it } from 'vitest'
import {
  compareEditableOrderDocumentByTimeDesc,
  parseEditableOrderRow,
} from '@/views/workstation-v4/customer-sample-validation/editableCopyPresentation'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'

function buildOrderDoc(
  overrides: Partial<EditableMedicalRecordDocument> = {},
): EditableMedicalRecordDocument {
  return {
    key: 'order-1',
    document_type: 'medical_order',
    title: '临时医嘱',
    record_time: '2026-06-01 08:30:00',
    content: '生理盐水 100ml ivgtt',
    enabled: true,
    ...overrides,
  }
}

describe('editableCopyPresentation', () => {
  it('医嘱时间按北京时间格式化，不会出现 UTC 8 小时偏移', () => {
    const rowFromOffset = parseEditableOrderRow(
      buildOrderDoc({
        order_start_time: '2026-06-01T08:30:00+08:00',
        order_stop_time: '2026-06-02T14:15:00+08:00',
      }),
    )
    expect(rowFromOffset.startTime).toBe('2026-06-01 08:30:00')
    expect(rowFromOffset.stopTime).toBe('2026-06-02 14:15:00')

    const rowFromUtc = parseEditableOrderRow(
      buildOrderDoc({
        order_start_time: '2026-06-01T00:30:00Z',
      }),
    )
    expect(rowFromUtc.startTime).toBe('2026-06-01 08:30:00')

    const rowFromWallClock = parseEditableOrderRow(
      buildOrderDoc({
        order_start_time: '2026-06-01 08:30:00',
      }),
    )
    expect(rowFromWallClock.startTime).toBe('2026-06-01 08:30:00')
  })

  it('医嘱排序在无时区北京时间与显式 UTC/东八区之间按真实时间倒序排列', () => {
    const earlier = buildOrderDoc({ key: 'earlier', order_start_time: '2026-06-01 09:00:00' })
    const later = buildOrderDoc({ key: 'later', order_start_time: '2026-06-01T02:00:00Z' }) // 10:00 +08:00
    const sorted = [earlier, later].sort(compareEditableOrderDocumentByTimeDesc)
    expect(sorted.map((item) => item.key)).toEqual(['later', 'earlier'])
  })

  it('不会将含“呼吸暂停 / 心搏骤停 / 停经”的临床描述误判为停止医嘱', () => {
    for (const content of [
      '睡眠呼吸暂停监测 qn',
      '心搏骤停抢救后持续心电监护',
      '停经42天，查血HCG及妇科彩超',
      '请填写医嘱名称、剂量、频次、用法、开立时间、停止时间及开立医师。',
    ]) {
      const row = parseEditableOrderRow(buildOrderDoc({ content, is_new: true }))
      expect(row.status).toBe('新开')
    }
  })

  it('显式停止/停用/停嘱/已停的医嘱正确识别为停止状态', () => {
    expect(
      parseEditableOrderRow(buildOrderDoc({ content: '头孢曲松 2g ivgtt qd 停止' })).status,
    ).toBe('停止')
    expect(
      parseEditableOrderRow(buildOrderDoc({ content: '长期医嘱\n停用\n阿司匹林 100mg' })).status,
    ).toBe('停用')
    expect(
      parseEditableOrderRow(buildOrderDoc({ content: '生理盐水 500ml 已停' })).status,
    ).toBe('停止')
    expect(
      parseEditableOrderRow(buildOrderDoc({ content: '吸氧 2L/min 停嘱' })).status,
    ).toBe('停止')
  })
})
